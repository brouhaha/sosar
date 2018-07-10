#!/usr/bin/env python3

import argparse
import sys

from sosdisk import SOSDisk


def cmd_ls(args, disk):
    disk.print_directory(recursive = args.recursive,
                         long = args.long)

def cmd_mkfs(args, disk):
    print('XXX mkfs')


def cmd_extract(args, disk):
    for sf in disk.files(path = '', recursive = True):
        name = sf.get_name()
        #print(name)
        #print(len(name))
        eof = sf.get_eof()
        data = sf.read(0, eof)
        #print(len(data))
        with open(name, 'wb') as f:
            f.write(data)
        break # XXX for debug, only extract first file


parser = argparse.ArgumentParser()

fmt_group = parser.add_mutually_exclusive_group()

fmt_group.add_argument('--do',
                       dest = 'format',
                       action = 'store_const',
                       const = 'do',
                       help = "image in DOS sector order")

fmt_group.add_argument('--po',
                       dest = 'format',
                       action = 'store_const',
                       const = 'po',
                       help = "image in SOS/ProDOS sector order")

parser.add_argument('image',
                    type = str,
                    help = "SOS/ProDOS disk image")

subparsers = parser.add_subparsers(title = 'commands',
                                   dest = 'cmd')

ls_parser = subparsers.add_parser('ls',
                                  help = 'list files')
ls_parser.set_defaults(cmd_fn = cmd_ls)

ls_parser.add_argument('-r', '--recursive',
                       action = 'store_true',
                       help = 'recursively list subdirectories')

ls_parser.add_argument('-l', '--long',
                       action = 'store_true',
                       help = 'list file attributes')

mkfs_parser = subparsers.add_parser('mkfs',
                                    help = 'make new filesystem')
mkfs_parser.set_defaults(cmd_fn = cmd_mkfs)

mkfs_parser.add_argument('--size',
                         type = int,
                         default = 280,
                         help = 'filesystem size in blocks')

extract_parser = subparsers.add_parser('x',
                                       help = 'extract file(s)')
extract_parser.set_defaults(cmd_fn = cmd_extract)

extract_parser.add_argument('-r', '--recursive',
                       action = 'store_true',
                       help = 'recursively extract subdirectory content')

extract_parser.add_argument('filename',
                            type = str,
                            nargs = '+',
                            help = 'filename(s) to extract',
)

args = parser.parse_args()
#print(args)

if args.format is not None:
    fmt = args.format
elif args.image.endswith('.do') or args.image.endswith('.dsk'):
    fmt = 'do'
elif args.image.endswith('.po'):
    fmt = 'po'
else:
    print('must specify image file format', file = sys.stderr)
    sys.exit(2)

file_mode = { 'mkfs': 'w',
              'ls': 'r',
              'x': 'r' } [args.cmd] + 'b'

image = open(args.image, file_mode)

if args.cmd == 'mkfs':
    disk = SOSDisk(image, fmt, new = True, volume_block_count = args.size)
else:
    disk = SOSDisk(image, fmt)

args.cmd_fn(args, disk)

disk.close()
    
