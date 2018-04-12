#!/usr/bin/env python3

import argparse
import sys

from sosdisk import SOSDisk


parser = argparse.ArgumentParser()

parser.add_argument('image',
                    type = argparse.FileType('rb'),
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
print(args)

image_fn = args.image.name

if args.format is not None:
    fmt = args.format
elif image_fn.endswith('.do') or image_fn.endswith('.dsk'):
    fmt = 'do'
elif image_fn.endswith('.po'):
    fmt = 'po'
else:
    print('must specify image file format', file = sys.stderr)
    sys.exit(2)

disk = SOSDisk(args.image, fmt)
disk.print_directory()
