#!/usr/bin/env python3
r"""
CMSSW_12_2_0_pre1
slc7_amd64_gcc900
Python 3.9.6
"""
import sys
sys.path.append('/usr/local/lib64/python3.6/site-packages')

import shutil
import abc
import warnings
import importlib
from pathlib import Path
from typing import Union, Optional
from dataclasses import dataclass
import tempfile
import re
import json
import argparse
import socket

import htcondor


import FWCore.ParameterSet.Config as cms
from IOMC.RandomEngine.RandomServiceHelper import RandomNumberServiceHelper
from FWCore.ParameterSet.VarParsing import VarParsing


# TODO
# class FileSystem(Enum):
#     XROOTD = 1




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

# FIXME
# rsync -az ${{CMSSW_BASE}} ./
# cd ${{CMSSW_VERSION}}/src
# source /cvmfs/cms.cern.ch/cmsset_default.sh
# eval `scramv1 runtime -sh`
# cd -

# FIXME
cd ${{CMSSW_BASE}}/src
eval `scramv1 runtime -sh`
cd -

################################################################################
# argument parsing
PROC_ID=${{1}}
shift 1
ARGS=${{@}}
echo "ARGS: ${{ARGS}}"

################################################################################
# run
cmsRun ${{ARGS}}

################################################################################
# transfer output files
{output_transfer_cmd}

rm -vf {output_file}

################################################################################
# terminate
echo "end: $(date)"
"""


@dataclass(frozen=True)
class CfgInfo:
    source_type: str
    output_file: str

    @classmethod
    def from_file(cls, cfg_path: Union[str, Path]): # TODO typing
        r"""
        """
        cfg_path = Path(cfg_path)
        if not cfg_path.exists():
            raise FileNotFoundError(cfg_path)

        ########################################################################
        with open(cfg_path, 'r') as cfg_file:
            cfg_text = cfg_file.readlines()
        cfg_text = [each for each in cfg_text if 'parseArguments' not in each]
        cfg_text = ''.join(cfg_text)

        ########################################################################
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

            output_file = None

            output_module = cls.find_attr(cfg_module.process, cms.OutputModule)
            if output_module is not None:
                output_file = output_module.fileName.value()
            else:
                # FIXME support both output
                file_service = cls.find_attr(cfg_module.process, cms.Service, type_="TFileService")
                if file_service is not None:
                    output_file = file_service.fileName.value()


            if output_file is None:
                raise RuntimeError('failed to find a output file')

            if output_file.startswith('file:'):
                output_file = output_file[len('file:'):]
            elif output_file.startswith(('root://', 'gsiftp://')):
                raise NotImplementedError(output_file)
            else:
                # FIXME
                if '/' in output_file:
                    # TODO warnings.warn
                    output_file = Path(output_file).name
                else:
                    pass


            if source_type == 'EmptySource':
                if not cls.inspect_attr(cfg_module, RandomNumberServiceHelper):
                    raise RuntimeError('EmptySource but RandomNumberServiceHelper not found')
            elif source_type == 'PoolSource':
                if not cls.inspect_attr(cfg_module, VarParsing):
                    raise RuntimeError('PoolSource but VarParsing not found')

        return cls(source_type=source_type, output_file=output_file)

    @staticmethod
    def find_attr(module, target_cls, type_=None):
        candidate_list = []
        for attr in dir(module):
            if attr.startswith('_'):
                continue
            attr = getattr(module, attr)
            if isinstance(attr, target_cls):
                if type_ is not None:
                    if attr.type_() != type_:
                        continue
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
    def inspect_attr(cls, module, target_cls):
        return cls.find_attr(module, target_cls) is not None



class CondorHelperBase(abc.ABC):

    def __init__(self,
                 cfg_file: str,
                 output_dir: str,
                 output_file: str,
                 source_type: str,
                 log_dir: Optional[str] = None,
                 num_jobs: Optional[int] = None,
                 input_dir: Optional[str] = None,
                 memory: int = 1,
    ) -> None:
        r"""
        """
        self.cfg_file = cfg_file
        self.output_dir = output_dir
        self.num_jobs = num_jobs
        self.input_dir = input_dir
        self.memory = memory

        self.output_file = output_file
        self.source_type = source_type

        self.job_batch_name = cfg_file.stem
        self.log_dir = log_dir or (Path.cwd() / 'logs' / Path(cfg_file).stem)

    @property
    def is_empty_source(self):
        return self.source_type == 'EmptySource'

    def queue(self):
        if self.log_dir.exists():
            shutil.rmtree(self.log_dir)
        self.log_dir.mkdir(parents=True)
        print(f'{self.log_dir=}')

        self.make_output_dir()

        ########################################################################
        output_transfer_cmd = self.make_output_transfer_cmd()
        executable_content = RUN_TEMPLATE.format(
            output_transfer_cmd=output_transfer_cmd,
            output_file=self.output_file)

        executable = self.log_dir.joinpath('run.sh')
        with open(executable, 'w') as executable_file:
            executable_file.write(executable_content)
        executable.chmod(0o755)
        print(f'{executable=}')

        ########################################################################
        if self.is_empty_source:
            arguments = f'$(ProcId) {self.cfg_file.name}'
            job_type = 'MC'
        else:
            # PoolSource
            arguments = f'$(ProcId) {self.cfg_file.name} inputFiles=$(input_file)'
            job_type = 'Analysis'

        ########################################################################
        submit = {
            'universe': 'vanilla',
            'getenv': 'True',
            'should_transfer_files': 'YES',
            'when_to_transfer_output': 'ON_EXIT',
            'executable': str(executable),
            'arguments': arguments,
            'transfer_input_files': str(self.cfg_file),
            'JobBatchName': self.job_batch_name,
            'log': str(self.log_dir / 'condor.log'),
            'output': str(self.log_dir / 'job_$(ProcId).out'),
            'error': str(self.log_dir / 'job_$(ProcId).err'),
            'request_memory': self.memory,
            '+Tag': Path(__file__).name,
            '+JobType': job_type,
        }

        submit |= self.host_dependent_submit_attribute

        with open(self.log_dir.joinpath('submit.json'), 'w') as json_file:
            json.dump(submit, json_file, indent=4)

        submit = htcondor.Submit(submit)
        print(submit)

        ########################################################################
        schedd = htcondor.Schedd()
        with schedd.transaction() as txn:
            if self.is_empty_source:
                cluster_id = submit.queue(txn, count=self.num_jobs)
            else:
                itemdata = self.make_itemdata()
                self.num_jobs = len(itemdata)
                cluster_id = submit.queue_with_itemdata(txn, itemdata=iter(itemdata))
                cluster_id = cluster_id.cluster()

        print(f'{self.num_jobs} jobs submmited with {cluster_id=}')

    @abc.abstractmethod
    def make_output_dir(self) -> None:
        ...

    @abc.abstractmethod
    def make_itemdata(self) -> list[dict[str, str]]:
        ...

    @abc.abstractmethod
    def make_output_transfer_cmd(self) -> str:
        ...

    @property
    @abc.abstractmethod
    def host_dependent_submit_attribute(self) -> dict[str, str]:
        ...

    @property
    def new_output_file(self) -> str:
        output_file = Path(self.output_file)
        return f'{output_file.stem}_${{PROC_ID}}{output_file.suffix}'

class DefaultCondorHelper(CondorHelperBase):
    hostname = None

    def make_output_dir(self) -> None:
        self.output_dir.mkdir()

    def make_output_transfer_cmd(self) -> str:
        # FIXME
        return f'rsync -avzhr {self.output_file} {self.output_dir}{self.new_output_file}'

    def make_input_itemdata(self):
        return [{'input_file': str(each) for each in self.input_dir.glob('*.root')}]

    @property
    def host_dependent_submit_attribute(self) -> dict[str, str]:
        return {}


class KISTICondorHelper(CondorHelperBase):
    hostname = ('ui10.sdfarm.kr', 'ui20.sdfarm.kr')

    def make_output_dir(self) -> None:
        # TODO if output_dir.startswith('/xrootd'):
        from XRootD import client
        from XRootD.client.flags import MkDirFlags

        output_dir = str(self.output_dir)
        assert output_dir.startswith('/xrootd/')

        output_dir = output_dir.replace('/xrootd/', '/xrd/')

        xrootd_client = client.FileSystem('root://cms-xrdr.private.lo:2094/')
        xrootd_client.mkdir(output_dir, MkDirFlags.MAKEPATH)

    def make_output_transfer_cmd(self) -> str:
        output_stem = Path(self.output_file).stem
        output_dir = self.to_xrootd_url(self.output_dir)
        output_dest = f'{output_dir}/{self.new_output_file}'
        return f'xrdcp -v {self.output_file} {output_dest}'

    def make_itemdata(self) -> list[dict[str, str]]:
        return [{'input_file': self.to_xrootd_url(each)} for each in self.input_dir.glob('*.root')]

    @property
    def host_dependent_submit_attribute(self) -> dict[str, str]:
        return {
            'accounting_group': 'group_cms',
            '+SingularityImage': '\"/cvmfs/singularity.opensciencegrid.org/opensciencegrid/osgvo-el7:latest\"',
            '+SingularityBind': '\"/cvmfs, /cms, /share\"',
        }

    def to_xrootd_url(self, path: Union[str, Path]) -> str:
        path = str(path)
        assert path.startswith('/xrootd/')
        path = path.replace('/xrootd/', 'root://cms-xrdr.private.lo:2094//xrd/')
        return path



class GateCondorHelper(CondorHelperBase):
    hostname = ('gate', )

    freenode_list = [
        'kcms00.sscc.uos',
        'kcms09.sscc.uos',
        'kcms10.sscc.uos',
        'kcms20.sscc.uos',
    ]

    freenode_rank = [f"(machine==\"{each}\")" for each in freenode_list]

    @property
    def is_input_dir_hdfs(self):
        return str(self.input_dir).startswith('/hdfs/')

    @property
    def is_output_dir_hdfs(self):
        return str(self.output_dir).startswith('/hdfs/')

    def to_hdfs_path(self, path):
        path = str(path)
        assert path.startswith('/hdfs/')
        return path[len('/hdfs'): ]

    def make_output_dir(self):
        if self.output_dir.exists():
            # TODO remoe contents
            pass
        else:
            if self.is_output_dir_hdfs:
                import pydoop.hdfs
                hdfs_path = self.to_hdfs_path(self.output_dir)
                pydoop.hdfs.mkdir(hdfs_path)
            else:
                self.output_dir.mkdir()

    def make_itemdata(self):
        itemdata = []

        if self.is_input_dir_hdfs:
            import pydoop.hdfs
            hdfs = pydoop.hdfs.hdfs()

            input_dir = self.input_dir[len('/hdfs'):]

            for each in hdfs.walk(input_dir): # FIXME
                if each['kind'] != 'file':
                    continue
                name = each['name']

                fuse_path = "/hdfs" + each["name"][29:] # FIXME
                datanode_list, *_ = hdfs.get_hosts(each["name"], 0, 1)

                rank = [f"(machine==\"{node}\")*3" for node in datanode_list]
                rank += self.freenode_rank

                itemdata.append({"input_file": 'file:' + fuse_path, "rank":rank}) # FIXME file:
        else:
            for each in self.input_dir.glob('*.root'):
                itemdata.append({"input_file": 'file:' + str(each)}) # FIXME file:
        return itemdata

    def make_output_transfer_cmd(self):
        if self.is_output_dir_hdfs:
            output_dest = self.output_dir[len('/hdfs'): ]
            output_transfer_cmd = f'hdfs dfs -put {self.output_file} {output_dest}/{self.new_output_file}'
        else:
            output_transfer_cmd = f'rsync -azv {self.output_file} {self.output_dir}/{self.new_output_file}'
        return output_transfer_cmd

    @property
    def host_dependent_submit_attribute(self) -> dict[str, str]:
        attrs = {}
        if self.is_input_dir_hdfs:
            attrs['Rank'] = "$(rank)",
        return attrs

def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('cfg_file', type=Path, help='config')
    parser.add_argument('-o', '--output-dir', type=Path, required=True)
    parser.add_argument('-l', '--log-dir', type=Path)
    parser.add_argument('-n', '--num-jobs', type=int)
    parser.add_argument('-i', '--input-dir', type=Path)
    parser.add_argument('-m', '--memory', type=str, default='1GB')
    args = parser.parse_args()

    cfg_info = CfgInfo.from_file(args.cfg_file)

    hostname = socket.gethostname()
    if hostname in KISTICondorHelper.hostname:
        helper_cls = KISTICondorHelper
    elif hostname in GateCondorHelper.hostname:
        helper_cls = GateCondorHelper
    else:
        raise NotImplementedError(hostname)

    # or for helper in supported_helper_list:...

    helper = helper_cls(
        cfg_file=args.cfg_file,
        output_dir=args.output_dir,
        log_dir=args.log_dir,
        num_jobs=args.num_jobs,
        input_dir=args.input_dir,
        memory=args.memory,
        output_file=cfg_info.output_file,
        source_type=cfg_info.source_type)

    helper.queue()

if __name__ == '__main__':
    main()
