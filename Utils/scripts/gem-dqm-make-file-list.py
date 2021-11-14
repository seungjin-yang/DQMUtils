#!/usr/bin/env python3
r"""
"""
from pathlib import Path
import socket
import argparse


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('input_dir', type=Path)
    parser.add_argument('-p', '--pathname', type=str, default='*.root')
    parser.add_argument('-o', '--output-file', type=str)
    args = parser.parse_args()

    if not args.input_dir.is_dir():
        raise IsADirectoryError(args.input_dir)

    file_list = args.input_dir.glob(args.pathname)
    file_list = [str(each) for each in file_list]

    hostname = socket.gethostname()
    if hostname == 'ui20.sdfarm.kr':
        if str(args.input_dir).startswith('/xrootd/'):
            file_list = [each.replace('/xrootd/', 'root://cms-xrdr.private.lo:2094//xrd/') for each in file_list]
        else:
            raise NotImplementedError(f'hostname={hostname} but input_dir={args.input_dir}')
    else:
        raise NotImplementedError(hostname)

    text = '\n'.join(file_list)

    output_path = Path.cwd().joinpath(f'filelist-{args.input_dir.name}').with_suffix('.txt')
    if output_path.exists():
        raise FileExistsError(output_path)

    with open(output_path, 'w') as txt_file:
        txt_file.write(text)


if __name__ == '__main__':
    main()
