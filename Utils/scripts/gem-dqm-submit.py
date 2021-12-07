#!/usr/bin/env python3
r"""
CMSSW_12_2_0_pre1
slc7_amd64_gcc900
Python 3.9.6
"""
import sys
import os
import warnings
import importlib
from pathlib import Path
from typing import Union, Optional
from dataclasses import dataclass
import tempfile
import re
import json
import argparse

import htcondor
from XRootD import client
from XRootD.client.flags import MkDirFlags
import git

import FWCore.ParameterSet.Config as cms
from IOMC.RandomEngine.RandomServiceHelper import RandomNumberServiceHelper
from FWCore.ParameterSet.VarParsing import VarParsing


SUBMIT_TEMPLATE = {
    'accounting_group': 'group_cms',
    '+SingularityImage': '\"/cvmfs/singularity.opensciencegrid.org/opensciencegrid/osgvo-el7:latest\"',
    '+SingularityBind': '\"/cvmfs, /cms, /share\"',
    'universe': 'vanilla',
    'getenv': 'True',
    'should_transfer_files': 'YES',
    'when_to_transfer_output': 'ON_EXIT',
}


RUN_TEMPLATE = r"""#!/bin/sh
################################################################################
# start
echo "start: $(date)"
echo "whoami: $(whoami)"
echo "hostname: $(hostname)"
echo "pwd: $(pwd)"
ls -lha ./

################################################################################
# setup
echo "SCRAM_ARCH: ${{SCRAM_ARCH}}"
echo "CMSSW_VERSION: ${{CMSSW_VERSION}}"
echo "CMSSW_BASE: ${{CMSSW_BASE}}"

################################################################################
# argument parsing
OUTPUT_DEST=${{1}}
shift 1
ARGS=${{@}}

echo "OUTPUT_DEST: ${{OUTPUT_DEST}}"
echo "ARGS: ${{ARGS}}"

################################################################################
# run
cmsRun ${{ARGS}}

################################################################################
# transfer output files
xrdcp -v {output_file} ${{OUTPUT_DEST}}

rm -vf {output_file}

################################################################################
# terminate
echo "end: $(date)"
"""


def to_xrootd_url(path):
    path = str(path)
    assert path.startswith('/xrootd/')
    path = path.replace('/xrootd/', 'root://cms-xrdr.private.lo:2094//xrd/')
    return path


@dataclass(frozen=True)
class CfgInfo:
    source_type: str
    output_file: str

    @property
    def has_empty_source(self):
        return self.source_type == 'EmptySource'

    @classmethod
    def from_file(cls,
                  cfg_path: Union[str, Path],
    ):
        if not isinstance(cfg_path, Path):
            cfg_path = Path(cfg_path)
        if not cfg_path.exists():
            raise FileNotFoundError(cfg_path)

        #
        with open(cfg_path, 'r') as cfg_file:
            cfg_text = cfg_file.readlines()
        cfg_text = [each for each in cfg_text if 'parseArguments' not in each]
        cfg_text = ''.join(cfg_text)

        with tempfile.TemporaryDirectory() as tmp_pythonpath:
            test_cfg_name = re.sub(pattern=r'(-|\.)', repl=r'_', string=cfg_path.stem)
            test_cfg_path = Path(tmp_pythonpath).joinpath(test_cfg_name).with_suffix('.py')
            test_cfg_path.write_text(cfg_text)

            print(f'Temporary PYTHONPATH: {tmp_pythonpath}')
            print(f'Temporary cfg: {test_cfg_path.stem}')

            sys.path.append(tmp_pythonpath)
            cfg_module = importlib.import_module(test_cfg_path.stem)

            source_type = cfg_module.process.source.type_()
            if source_type not in ('EmptySource', 'PoolSource'):
                raise ValueError(f'Got unexpected source type: {source_type}')

            output_file = cls.find_attr(cfg_module.process, cms.OutputModule).fileName.value()
            if output_file.startswith('file:'):
                output_file = output_file[len('file:'):]
            else:
                raise NotImplementedError(output_file)

            if source_type == 'EmptySource':
                if not cls.has_attr(cfg_module, RandomNumberServiceHelper):
                    raise RuntimeError('EmptySource but RandomNumberServiceHelper not found')
            elif source_type == 'PoolSource':
                if not cls.has_attr(cfg_module, VarParsing):
                    raise RuntimeError('PoolSource but VarParsing not found')

        return cls(source_type=source_type,
                   output_file=output_file)

    @staticmethod
    def find_attr(module, target_cls):
        candidate_list = []
        for attr in dir(module):
            if attr.startswith('_'):
                continue
            attr = getattr(module, attr)
            if isinstance(attr, target_cls):
                candidate_list.append(attr)

        if len(candidate_list) == 0:
            candidate = None
        elif len(candidate_list) > 1:
            warnings.warn((f'Found {len(candidate_list)} {target_cls.__name__} '
                          'instances. Return the first instance.'),
                           RuntimeWarning)
            candidate = candidate_list[0]
        else:
            candidate = candidate_list[0]
        return candidate

    @classmethod
    def has_attr(cls, module, target_cls):
        return cls.find_attr(module, target_cls) is not None


@dataclass(frozen=True)
class GitInfo:
    user: str
    branch: str
    sha1_hash: str

    @classmethod
    def from_config(cls):
        cmssw_base = os.getenv('CMSSW_BASE')
        if cmssw_base is None:
            raise RuntimeError

        repo = os.path.join(cmssw_base, 'src')
        repo = git.Repo(repo)
        config_reader = repo.config_reader()

        github_user = config_reader.get('user', 'github')
        branch = repo.active_branch.name
        sha1_hash = repo.git.rev_parse('HEAD')
        return cls(github_user, branch, sha1_hash)


def submit(cfg: Path,
           output_dir: Path,
           log_dir: Optional[Path] = None,
           job_batch_name: Optional[str] = None,
           num_jobs: Optional[int] = None,
           input_dir: Optional[Path] = None,
           memory: Union[int, str] = '1GB',
           dry_run: bool = False,
           verbose: bool = False,
) -> None:
    r"""
    """
    ############################################################################
    # setup
    ############################################################################
    cfg = cfg.resolve()
    if not cfg.exists():
        raise FileNotFoundError(cfg)

    cfg_info = CfgInfo.from_file(cfg)
    if verbose:
        print(cfg_info)

    scram_arch = os.getenv('SCRAM_ARCH')
    if scram_arch is None:
        raise RuntimeError('SCRAM_ARCH is not defined')

    cmssw_version = os.getenv('CMSSW_VERSION')
    if cmssw_version is None:
        raise RuntimeError('CMSSW_VERSION is not defined')

    if verbose:
        print(f'CMSSW_VERSION: {cmssw_version}')
        print(f'SCRAM_ARCH: {scram_arch}')

    ############################################################################
    # normalize
    ############################################################################
    if log_dir is None:
        log_dir = Path.cwd() / 'logs' / Path(cfg).stem
    if not log_dir.exists():
        log_dir.mkdir(parents=True)
        if verbose:
            print(f'mkdir: created directory \'{log_dir}\'')

    if job_batch_name is None:
        job_batch_name = cfg.stem

    if cfg_info.source_type == 'EmptySource':
        pass
    elif cfg_info.source_type == 'PoolSource':
        itemdata = [{'input_file': to_xrootd_url(each)} for each in input_dir.glob('*.root')]
        num_jobs = len(itemdata)
    else:
        raise ValueError

    if num_jobs == 0:
        raise ValueError

    # NOTE
    if cfg_info.source_type == 'EmptySource':
        job_type = 'MC'
    elif cfg_info.source_type == 'PoolSource':
        job_type = 'Analysis'
    else:
        raise ValueError

    ############################################################################
    #
    ############################################################################
    if not output_dir.exists():
        xrootd_client = client.FileSystem('root://cms-xrdr.private.lo:2094/')
        output_dir_xrootd_path = str(output_dir).replace('/xrootd/', '/xrd/')
        xrootd_client.mkdir(output_dir_xrootd_path, MkDirFlags.MAKEPATH)
        if verbose:
            print(f'mkdir: created directory \'{output_dir_xrootd_path}\'')

    output_stem = Path(cfg_info.output_file).stem
    output_dir = to_xrootd_url(output_dir)
    output_dest = f'{output_dir}/{output_stem}_$(ProcId).root'

    ############################################################################
    # executable
    ############################################################################
    # NOTE
    if cfg_info.has_empty_source:
        # EmptySource
        arguments = f'$(OutputDest) {cfg.name}'
    else:
        # PoolSource
        arguments = f'$(OutputDest) {cfg.name} inputFiles=$(input_file)'

    ############################################################################
    #
    ############################################################################
    executable_content = RUN_TEMPLATE.format(
        scram_arch=scram_arch,
        cmssw_version=cmssw_version,
        cfg=cfg,
        output_file=cfg_info.output_file)

    executable = log_dir.joinpath('run.sh')
    if verbose:
        print(f'executable: {executable}')

    with open(executable, 'w') as executable_file:
        executable_file.write(executable_content)

    executable.chmod(0o755)
    if verbose:
        print(f"mode of \'{executable}\' changed from 0640 (rw-r-----) to 0755 (rwxr-xr-x)")

    ############################################################################
    #
    ############################################################################
    submit = SUBMIT_TEMPLATE.copy()
    submit.update({
        'executable': str(executable),
        'arguments': arguments,
        'transfer_input_files': str(cfg),
        'OutputDest': output_dest,
        'JobBatchName': job_batch_name,
        'log': str(log_dir / 'condor.log'),
        'output': str(log_dir / 'job_$(ProcId).out'),
        'error': str(log_dir / 'job_$(ProcId).err'),
        'request_memory': memory,
        '+Tag': Path(__file__).name,
        '+JobType': job_type,
    })

    with open(log_dir.joinpath('submit.json'), 'w') as json_file:
        json.dump(submit, json_file, indent=4)

    submit = htcondor.Submit(submit)
    if verbose:
        print(submit)

    ############################################################################
    #
    ############################################################################
    if dry_run:
        return

    schedd = htcondor.Schedd()
    with schedd.transaction() as txn:

        if cfg_info.has_empty_source:
            cluster_id = submit.queue(txn, count=num_jobs)
        else:
            cluster_id = submit.queue_with_itemdata(txn,
                                                    itemdata=iter(itemdata))
            cluster_id = cluster_id.cluster()

    if verbose:
        print(f'{num_jobs} jobs submmited with job id {cluster_id}')


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('cfg', type=Path, help='config')
    parser.add_argument('-o', '--output-dir', type=Path, required=True)
    parser.add_argument('-l', '--log-dir', type=Path)
    parser.add_argument('-n', '--num-jobs', type=int)
    parser.add_argument('-i', '--input-dir', type=Path)
    parser.add_argument('-m', '--memory', type=str, default='1GB')
    parser.add_argument('-d', '--dry-run', action='store_true')
    parser.add_argument('-v', '--verbose', action='store_true')
    args = parser.parse_args()

    submit(cfg=args.cfg,
           output_dir=args.output_dir,
           log_dir=args.log_dir,
           num_jobs=args.num_jobs,
           input_dir=args.input_dir,
           memory=args.memory,
           dry_run=args.dry_run,
           verbose=args.verbose)


if __name__ == '__main__':
    main()
