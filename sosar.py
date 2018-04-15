#!/usr/bin/env python3

import argparse
import sys

from sosdisk import SOSDisk


def cmd_ls(args, disk):
    disk.print_directory(recursive = args.recursive,
                         long = args.long)

def cmd_mkfs(args, disk):
    print('XXX mkfs')


parser = argparse.ArgumentParser()

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

parser.add_argument('image',
                    type = str,
                    help = "SOS/ProDOS disk image")

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

if args.cmd == 'mkfs':
    image = open(args.image, 'wb')
    disk = SOSDisk(image, fmt, new = True, size = args.size)
else:
    image = open(args.image, 'rb')
    disk = SOSDisk(image, fmt)

args.cmd_fn(args, disk)

image.close()

    
