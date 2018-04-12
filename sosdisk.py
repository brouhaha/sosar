import struct
import sys

def list_to_dict(l):
    return { i: l[i] for i in range(len(l)) }

def invert_dict(d):
    return { v: k for k, v in d.items() }

def compose_dict(d1, d2):
    return { k: d2[v] for k, v in d1.items() }


def reinterleave(src_image, src_interleave, dest_interleave):
    map = compose_dict(src_interleave, invert_dict(dest_interleave))
    dest_image = bytearray(len(src_image))
    for t in range(35):
        for ss in range(16):
            src_offset = (t * 16 + ss) * 256
            dest_offset = (t * 16 + map[ss]) * 256
            dest_image[dest_offset:dest_offset+256] = src_image[src_offset:src_offset+256]
    return dest_image


half_block_to_phys_sect = list_to_dict([0x00, 0x02, 0x04, 0x06,
                                        0x08, 0x0a, 0x0c, 0x0e,
                                        0x01, 0x03, 0x05, 0x07,
                                        0x09, 0x0b, 0x0d, 0x0f])

dos_to_phys_sect = list_to_dict([0x0, 0xd, 0xb, 0x9, 0x7, 0x5, 0x3, 0x1,
                                 0xe, 0xc, 0xa, 0x8, 0x6, 0x4, 0x2, 0xf])

identity = { k: k for k in range(16) }



interleave_tables = { 'dos':    dos_to_phys_sect,
                      'do':     dos_to_phys_sect,
                      'pascal': half_block_to_phys_sect,
                      'phys':   identity,
                      'po':     half_block_to_phys_sect,
                      'prodos': half_block_to_phys_sect,
                      'sos':    half_block_to_phys_sect }


class SOSDirectoryEntry:
    def __init__(self, disk):
        self.disk = disk

    def print(self, prefix, file):
        pass


class SOSVolumeDirectoryHeader(SOSDirectoryEntry):
    def __init__(self, disk, entry_data):
        super().__init__(disk)
        #print('volume directory header')
        (self.storage, self.filename, self.reserved, self.creation, self.version, self.min_version, self.access, self.entry_length, self.entries_per_block, self.file_count, self.bitmap_pointer, self.total_blocks) = struct.unpack('<B15s8sLBBBBBHHH', entry_data)
        self.name_length = self.storage & 0xf
        self.storage >>= 4
        assert self.storage == 0xf
        assert self.version == 0
        assert self.min_version == 0
        assert self.entry_length == 0x27
        assert self.entries_per_block == 0x0d
        assert self.total_blocks == disk.block_count

class SOSSubdirectoryHeader(SOSDirectoryEntry):
    def __init__(self, disk, entry_data):
        super().__init__(disk)
        #print('subdirectory header')

class SOSFileEntry(SOSDirectoryEntry):
    def __init__(self, disk, entry_data):
        super().__init__(disk)
        (self.storage, self.filename, self.file_type, self.key_pointer, self.blocks_used, self.eof, self.creation, self.version, self.min_version, self.access, self.aux_type, self.last_mod, self.header_pointer) = struct.unpack('<B15sBHH3sLBBBHLH', entry_data)
        name_length = self.storage & 0xf
        self.storage >>= 4
        if self.storage == 0:
            return
        self.name = str(entry_data[1:1+name_length], 'ascii')
        if (self.storage == 0xd):
            self.subdir = SOSDirectory(disk, self.key_pointer)

    def print(self, prefix, file):
        if self.storage == 0:
            return
        print('%s/%s, storage type %x' % (prefix, self.name, self.storage), file = file)
        if (self.storage == 0xd):
            self.subdir.print(prefix + '/' + self.name, file)
        

class SOSDirectoryBlock:
    def __init__(self, disk, block_num, first_dir_block = False):
        self.disk = disk
        data = disk.get_blocks(block_num)
        self.prev_block, self.next_block = struct.unpack('<HH', data[0:4])
        #print('prev: %d, next: %d' % (self.prev_block, self.next_block))
        self.entries = []
        entry_length = 39
        entry_count = 13
        for i in range(entry_count):
            offset = 4 + entry_length * i
            entry_data = data[offset: offset+entry_length]
            if first_dir_block and i == 0:
                if block_num == 2:
                    self.entries.append(SOSVolumeDirectoryHeader(disk, entry_data))
                else:
                    self.entries.append(SOSSubdirectoryHeader(disk, entry_data))
            else:
                self.entries.append(SOSFileEntry(disk, entry_data))


class SOSDirectory:
    def __init__(self, disk, first_block):
        self.disk = disk
        self.directory_blocks = [SOSDirectoryBlock(disk, first_block, first_dir_block = True)]
        while self.directory_blocks[-1].next_block != 0:
            self.directory_blocks.append(SOSDirectoryBlock(disk, self.directory_blocks[-1].next_block))
        self.header = self.directory_blocks[0].entries[0]

    def print(self, prefix, file):
        for db in self.directory_blocks:
            for entry in db.entries:
                entry.print(prefix, file)


class SOSDisk:
    def __init__(self, f, fmt):
        self.data = f.read()
        if len(self.data) % 512:
            print('Images must contain an integral number of 512-byte blocks', file = sys.stderr)
            sys.exit(2)            
        self.block_count = len(self.data) // 512
        self.used = [False] * self.block_count
        if (fmt != 'po'):
            if len(self.data) != (35 * 16 * 256):
                print('Images other than 16-sector floppy must be in SOS/ProDOS sector order', file = sys.stderr)
                sys.exit(2)
            self.data = reinterleave(self.data, interleave_tables[fmt], interleave_tables['po'])
        self.mark_used(0, 2)  # boot blocks
        self.volume_directory = SOSDirectory(self, 2)
        bitmap_block_count = (self.volume_directory.header.total_blocks + 1) // (512 * 8)
        self.mark_used(self.volume_directory.header.bitmap_pointer, bitmap_block_count)

    def mark_used(self, first_block, count = 1):
        for block in range(first_block, first_block + count):
            if self.used[block]:
                print('block %d multiply used' % block)
            self.used[block] = True

    def get_blocks(self, first_block, count = 1):
        self.mark_used(first_block, count)
        offset = first_block * 512
        length = count * 512
        return self.data[offset:offset+length]

    def print_directory(self, file=sys.stdout):
        self.volume_directory.print(prefix = '', file = file)


# blocks 0-1       loader
# blocks 2..2+n-1  volume directory
# blocks 2+n..     volume bit map, one block per 4096 blocks of volume size



# storage type:
#   $1  seedling
#   $2  sapling
#   $3  tree
#   $4  Pascal area
#   $d  subdirectory
#   $e  subdirectory header
#   $f  volume directory headern


# directory entry

#              volume
# offset size  directory header
#     0    1   storage type, name length
#  1-15   15   filename
# 16-23    8   reserved                                   1  file_type
#                                                         2  key.pointer
#                                                         2  blocks used
#                                                         3  EOF
# 24-27    4   creation date & time
#    28    1   version           = 0
#    29    1   min_version       = 0
#    30    1   access
#    31    1   entry length      = $27                    2  aux_type
#    32    1   entries per block = $0d
# 33-34    2   file count                                 4  last_mod
# 35-36    2   bit map pointer        2  parent pointer   
# 37-38    2   total blocks           1  parent_entry_num 2  header_pointer
#                                     1  parent_entry_length = $27
