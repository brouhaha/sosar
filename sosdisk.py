import datetime
from enum import Enum, IntEnum, IntFlag
import math
import string
import struct
import sys

def list_to_dict(l):
    return { i: l[i] for i in range(len(l)) }

def invert_dict(d):
    return { v: k for k, v in d.items() }

def compose_dict(d1, d2):
    return { k: d2[v] for k, v in d1.items() }


def reinterleave(src_image, src_interleave, dest_interleave):
    if src_interleave == dest_interleave:
        return src_image  # not a copy!
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


class StorageType(IntEnum):
    unused_entry            = 0x00
    seedling                = 0x01  # no indirect blocks
    sapling                 = 0x02  # one indirect block
    tree                    = 0x03  # two levels of indirect blocks
    pascal_area             = 0x04  # Apple II Pascal area (ProDOS Technical Note #25)
    extended_file           = 0x05  # file with data and resource forks (GS/OS) (ProDOS Technical Note #25)
    subdirectory            = 0x0d
    subdirectory_header     = 0x0e
    volume_directory_header = 0x0f
    

class FileType(IntEnum):
    unk = 0x00   # unknown/typeless
    bad = 0x01   # bad blocks
    pcd = 0x02   # (SOS) Pascal codefile (may be assembly)
    ptx = 0x03   # (SOS) Pascal textfile
    txt = 0x04   # normal ASCII text file
    pda = 0x05   # (SOS) Pascal data
    bin = 0x06   # binary, subtype has load address
    fnt = 0x07   # (SOS) font
    fot = 0x08   # screen image
    ba3 = 0x09   # (SOS) Business BASIC program
    da3 = 0x0a   # (SOS) Business BASIC data
    wpf = 0x0b   # (SOS) word processor
    sos = 0x0c   # (SOS) system file
    # 0x0d..0x0e reserved for SOS
    dir = 0x0f   # subdirectory
    rpd = 0x10   # (SOS) RPS_data
    rpi = 0x11   # (SOS) RPS index
    afd = 0x12   # (SOS) AppleFile discard
    afm = 0x13   # (SOS) AppleFile model
    afr = 0x14   # (SOS) AppleFile report
    scl = 0x15   # (SOS) screen library
    # 0x16..0x18 reserved for SOS
    adb = 0x19   # AppleWorks database
    awp = 0x1a   # AppleWorks word processor
    asp = 0x1b   # AppleWorks spreadsheet
    r16 = 0xee   # (ProDOS) EDASM 816 reolcatable
    par = 0xef   # Apple Pascal area
    cmd = 0xf0   # (ProDOS) added command
    ovl = 0xf1   # (ProDOS) user defined 1, overlay
    ud2 = 0xf2   # (ProDOS) user defined 2
    ud3 = 0xf3   # (ProDOS) user defined 3
    ud4 = 0xf4   # (ProDOS) user defined 4
    bat = 0xf5   # (ProDOS) user defined 5, batch
    ud6 = 0xf6   # (ProDOS) user defined 6
    ud7 = 0xf7   # (ProDOS) user defined 7
    prg = 0xf8   # (ProDOS) user defined 8
    p16 = 0xf9   # (ProDOS 16) system
    int = 0xfa   # (None) Integer BASIC program
    ivr = 0xfb   # (None) Integer BASIC variables
    bas = 0xfc   # (ProDOS) Applesoft BASIC program
    var = 0xfd   # (ProDOS) Applesoft BASIC variables
    rel = 0xfe   # (ProDOS) EDASM relocatable
    sys = 0xff   # (ProDOS) system


class FileAttributes(IntFlag):
    destroy_enable = 0x80  # "D"
    rename_enable  = 0x40  # "RN"
    backup_needed  = 0x20  # "B"
    # bits 4 through 2 are reserved
    write_enable   = 0x02  # "W"
    read_enable    = 0x01  # "R"

    # synthesized attributes - not stored on disk
    sparse         = 0x0100


sos_valid_fn_chars = set(string.ascii_uppercase + string.digits + '.')

def bytes_to_sos_filename(l, b):
    assert len(b) == 15
    assert 1 <= l <= 15
    s = str(b[:l], 'ascii')
    assert all(c in sos_valid_fn_chars for c in s[:l])
    assert all(c == 0 for c in b[l:])
    return s.lower()

def u32_to_sos_timestamp(b):
    if b == 0:
        return None
    ymd = b & 0xffff
    hm = b >> 16
    year = 1900 + (ymd >> 9)
    month = (ymd >> 5) & 0xf
    day = ymd & 0x1f
    hour = hm >> 8
    minute = hm & 0xff
    assert 1 <= month <= 12
    assert 1 <= day <= 31
    assert 0 <= hour <= 23
    assert 0 <= minute <= 59
    return datetime.datetime(year, month, day, hour, minute)
    

class SOSAllocationBitmap:
    def __init__(self, disk, start_block, bitmap_block_count, create = False, volume_block_count = None):
        self.disk = disk
        self.start_block = start_block
        self.bitmap_block_count = bitmap_block_count
        self.data = self.disk.get_blocks(self.start_block, self.bitmap_block_count)
        if create:
            self.__create_new(volume_block_count)

    def __create_new(self, volume_block_count):
        print('creating bitmap')
        print(volume_block_count)
        self.bitmap_block_count = math.ceil(volume_block_count / (8 * self.disk.block_size))
        # mark all blocks as free
        print(self.bitmap_block_count, self.disk.block_size)
        self.data[:] = bytes(self.bitmap_block_count * self.disk.block_size)
        print(len(self.data))
        # mark blocks occupied by boot blocks, volume directory, and
        # volume allocation bitmap as in use
        self[0:self.start_block+self.bitmap_block_count] = [1] * (self.start_block+self.bitmap_block_count)

    def __getitem__(self, key):
        if isinstance(key, slice):
            result = [self.__getitem__(i) for i in range(*key.indices(len(self.data)))]
        else:
            # XXX is bit numbering little-endian or big-endian?
            return bool((self.data[key >> 3] >> (key & 7)) & 1)


    def __setitem__(self, key, value):
        print('setitem(', key, ', ', value, ')')
        if isinstance(key, slice):
            print('slice')
            print(key.indices(len(self.data)))
            for k, v in zip(range(*key.indices(len(self.data))), value):
                print(k, v)
                self.__setitem__(k, v)
                print(self.data)
        else:
            # XXX is bit numbering little-endian or big-endian?
            if value:
                self.data[key >> 3] |= (1 << (key & 7))
            else:
                self.data[key >> 3] &= ~ (1 << (key & 7))


class SOSStorage:
    @staticmethod
    def create(disk, storage_type, key_pointer):
        if storage_type == StorageType.seedling:
            return SOSSeedling(disk, key_pointer)
        elif storage_type == StorageType.sapling:
            return SOSSapling(disk, key_pointer)
        elif storage_type == StorageType.tree:
            return SOSTree(disk, key_pointer)

    def __init__(self, disk, key_pointer):
        self.disk = disk
        self.key_pointer = key_pointer
        self.index = { }
        self.index_blocks = 0
        self.data_blocks = 0
        self.last_block_index = 0

    def is_sparse(self):
        return self.data_blocks != (self.last_block_index + 1)

    def read(self,
             offset = 0,
             length = 0):
        data = bytearray(length)
        while length > 0:
            block_index = offset // self.disk.block_size
            block_offset = offset % self.disk.block_size
            chunk_length = min(length, self.disk.block_size - block_offset)
            if block_index in self.index:
                block_number = self.index[block_index]
                data[offset:offset+chunk_length] = self.disk.get_blocks(block_number)[block_offset:block_offset+chunk_length]
            offset += chunk_length
            length -= chunk_length
        return data


class SOSSeedling(SOSStorage):
    def __init__(self, disk, key_pointer):
        super().__init__(disk, key_pointer)
        self.index[0] = key_pointer
        self.data_blocks += 1

class SOSSapling(SOSStorage):
    def __init__(self, disk, key_pointer):
        super().__init__(disk, key_pointer)
        index_data = self.disk.get_blocks(key_pointer)
        self.index_blocks += 1
        for j in range(256):
            b = index_data[j] + (index_data[j + 256] << 8)
            if b != 0:
                self.index[j] = b
                self.data_blocks += 1
                self.last_block_index = j

class SOSTree(SOSStorage):
    def __init__(self, disk, key_pointer):
        super().__init__(disk, key_pointer)
        top_index_data = self.disk.get_blocks(key_pointer)
        self.index_blocks += 1
        for i in range(256):
            tb = top_index_data[i] + (top_index_data[i + 256] << 8)
            if tb != 0:
                index_data = self.disk.get_blocks(b)
                self.index_blocks += 1
                for j in range(256):
                    b = index_data[j] + (index_data[j + 256] << 8)
                    if b != 0:
                        self.index[j * 256 + i] = b
                        self.data_blocks += 1
                        self.last_block_index = j

class SOSDirectoryEntry:
    def __init__(self, disk):
        self.disk = disk

    @staticmethod
    def create_from_data(disk, entry_data, block_num, first_dir_entry):
        if first_dir_entry:
            if block_num == 2:
                return SOSVolumeDirectoryHeader(disk, entry_data)
            else:
                return SOSSubdirectoryHeader(disk, entry_data)
        else:
            return SOSFileEntry(disk, entry_data)

    def print(self,
              prefix,
              recursive = False,
              long = False,
              file = sys.stdout):
        pass


class SOSDirectoryHeader(SOSDirectoryEntry):
    def __init__(self, disk):
        super().__init__(disk)


class SOSVolumeDirectoryHeader(SOSDirectoryHeader):
    def __init__(self, disk, entry_data):
        super().__init__(disk)
        (storage_nl, name_b, self.reserved, creation_b, self.version, self.min_version, self.access, self.entry_length, self.entries_per_block, self.file_count, self.bitmap_pointer, self.total_blocks) = struct.unpack('<B15s8sLBBBBBHHH', entry_data)
        name_length = storage_nl & 0xf
        self.storage_type = StorageType(storage_nl >> 4)
        self.name = bytes_to_sos_filename(name_length, name_b)
        assert self.storage_type == StorageType.volume_directory_header
        assert self.version == 0
        assert self.min_version == 0
        assert self.entry_length == 39       # XXX compare to SOSDirectory entry_length instead
        assert self.entries_per_block == 13  # XXX compare to SOSDirectory entries_per_block instead
        assert self.total_blocks == disk.block_count
        self.creation = u32_to_sos_timestamp(creation_b)

class SOSSubdirectoryHeader(SOSDirectoryHeader):
    def __init__(self, disk, entry_data):
        super().__init__(disk)
        (storage_nl, name_b, self.reserved, creation_b, self.version, self.min_version, self.access, self.entry_length, self.entries_per_block, self.file_count, self.bitmap_pointer, self.total_blocks) = struct.unpack('<B15s8sLBBBBBHHH', entry_data)
        name_length = storage_nl & 0xf
        self.storage_type = StorageType(storage_nl >> 4)
        self.name = bytes_to_sos_filename(name_length, name_b)
        assert self.storage_type == StorageType.subdirectory_header
        assert self.version == 0
        assert self.min_version == 0
        assert self.entry_length == 0x27
        assert self.entries_per_block == 0x0d
        self.creation = u32_to_sos_timestamp(creation_b)

class SOSFileEntry(SOSDirectoryEntry):
    def __init__(self, disk, entry_data):
        super().__init__(disk)
        (storage_nl, name_b, self.file_type, self.key_pointer, self.blocks_used, eof, creation_b, self.version, self.min_version, self.access, self.aux_type, self.last_mod, self.header_pointer) = struct.unpack('<B15sBHH3sLBBBHLH', entry_data)
        name_length = storage_nl & 0xf
        self.storage_type = StorageType(storage_nl >> 4)
        if self.storage_type == StorageType.unused_entry:
            return
        self.eof = eof [2] << 16 | eof [1] << 8 | eof[0]
        self.name = bytes_to_sos_filename(name_length, name_b)
        self.creation = u32_to_sos_timestamp(creation_b)
        if self.storage_type == StorageType.subdirectory:
            assert self.file_type == FileType.dir
            self.subdir = SOSDirectory(disk, self.key_pointer)
        else:
            assert self.storage_type in set([StorageType.seedling, StorageType.sapling, StorageType.tree])
            assert self.file_type != FileType.dir
            self.storage = SOSStorage.create(self.disk, self.storage_type, self.key_pointer)


    def get_name(self):
        return self.name


    def get_eof(self):
        return self.eof


    def read(self,
             offset = 0,
             length = None):
        return self.storage.read(offset, length)


    def print(self,
              prefix,
              recursive = False,
              long = False,
              file = sys.stdout):
        if self.storage_type == StorageType.unused_entry:
            return
        if long:
            attrchar = 'rw234bnds'
            attr = self.access
            attrs = ''
            if self.storage_type != StorageType.subdirectory and self.storage.is_sparse():
                self.access |= FileAttributes.sparse
            for b in range(8, -1, -1):
                if self.access & (1 << b):
                    attrs += attrchar[b]
                else:
                    attrs += '.'
            try:
                ft = FileType(self.file_type).name
            except ValueError as e:
                ft = '$%02x' % self.file_type
            print('  %s  %s  %s  %6d' % (self.creation, ft, attrs, self.eof), end = '', file = file)
        print('  %s' % (prefix + self.name), file = file)
        if recursive and self.storage_type == StorageType.subdirectory:
            self.subdir.print(prefix + self.name + '/',
                              recursive = recursive,
                              long = long,
                              file = file)
        

class SOSDirectoryBlock:
    def __init__(self,
                 disk,
                 directory,               # the directory containing this block
                 block_num,
                 first_dir_block = False,
                 new = False,
                 directory_name = None,   # if new
                 prev_block = None):      # if new
        self.disk = disk
        self.directory = directory
        self.entries = []
        self.entry_count = (self.disk.block_size - 4) // self.directory.entry_length
        if new:
            self.__create_new(block_num, first_dir_block)
        else:
            self.__read_from_image(block_num, first_dir_block)

    def __read_from_image(self, block_num, first_dir_block = False):
        data = self.disk.get_blocks(block_num)
        self.prev_block, self.next_block = struct.unpack('<HH', data[0:4])
        #print('prev: %d, next: %d' % (self.prev_block, self.next_block))
        for i in range(self.entry_count):
            offset = 4 + self.directory.entry_length * i
            # data is already a memoryview, so slicing it doesn't copy it
            entry_data = data[offset: offset+self.directory.entry_length]
            self.entries.append(SOSDirectoryEntry.create_from_data(self.disk, entry_data, block_num, first_dir_block and (i == 0)))

    def __create_new(self, block_num, first_dir_block = False):
        self.prev_block = prev_block,
        self.next_block = 0  # will be updated later if needed
        data = struct.pack('<HH', self.prev_block, self.next_block) + bytearray(disk.block_size - 4)
        if block_num == 2:
            self.entries.append(SOSVolumeDirectoryHeader(disk, new = True, directory_name = directory_name))
        else:
            self.entries.append(SOSSubdirectoryHeader(disk, new = True, directory_name = directory_name))


class SOSDirectory:
    def __init__(self,
                 disk,
                 first_block = None,
                 new = False,
                 block_count = 1,         # if new
                 directory_name = None):  # if new
        self.disk = disk
        self.growable = first_block != 2
        self.entry_length = 39
        if new:
            self.__create_new(first_block, block_count)
        else:
            # block_count not used
            self.__read_from_image(first_block)

    def __read_from_image(self, first_block):
        self.directory_blocks = [SOSDirectoryBlock(self.disk,
                                                   self,
                                                   first_block,
                                                   first_dir_block = True)]
        while self.directory_blocks[-1].next_block != 0:
            self.directory_blocks.append(SOSDirectoryBlock(self.disk,
                                                           self,
                                                           self.directory_blocks[-1].next_block))
        self.header = self.directory_blocks[0].entries[0]

    def __create_new(self, first_block = None, block_count = 1):
        prev_block_num = 0
        for i in range(block_count):
            if first_block is None:
                block_num = disk.alloc_block()
            else:
                block_num = first_block + i
            
    def files(self,
              path,
              recursive = False):
        for db in self.directory_blocks:
            for entry in db.entries:
                if isinstance(entry, SOSFileEntry) and (entry.storage_type != StorageType.unused_entry) and hasattr(entry, 'storage'):
                    yield entry

    def print(self, prefix,
              recursive = False,
              long = False,
              file = sys.stdout):
        for db in self.directory_blocks:
            for entry in db.entries:
                entry.print(prefix,
                            recursive = recursive,
                            long = long,
                            file = file)


class SOSDisk:
    def __init__(self, f,
                 fmt = 'po',
                 new = False,
                 volume_block_count = 280,           # only for creating new
                 volume_directory_block_count = 4):  # only for creating new 
        self.image_file = f
        self.image_file_fmt = fmt
        self.block_size = 512
        if new:
            self.__create_new(volume_block_count, volume_directory_block_count)
        else:
            self.__read_image_file()

    def __read_image_file(self):
        self.data = self.image_file.read()
        if len(self.data) % self.block_size:
            print('Images must contain an integral number of %d-byte blocks' % self.block_size, file = sys.stderr)
            sys.exit(2)            
        self.dirty = False
        self.block_count = len(self.data) // self.block_size
        if self.image_file_fmt != 'po':
            if len(self.data) != (35 * 8 * self.block_size):
                print('Images other than 16-sector floppy must be in SOS/ProDOS sector order', file = sys.stderr)
                sys.exit(2)
            self.data = reinterleave(self.data, interleave_tables[self.image_file_fmt], interleave_tables['po'])
        self.volume_directory = SOSDirectory(self, 2, new = False)
        self.bitmap_block_count = (self.volume_directory.header.total_blocks + 1) // (self.block_size * 8)
        self.bitmap_start_block = self.volume_directory.header.bitmap_pointer
        self.allocation_bitmap = SOSAllocationBitmap(self, self.bitmap_start_block, self.bitmap_block_count)

    def __create_new(self, volume_block_count = 280, volume_directory_block_count = 4):
        print('create new')
        self.dirty = True
        self.block_count = volume_block_count;
        self.data = bytearray(self.block_count * self.block_size)
        self.bitmap_block_count = (volume_block_count + 1) // (self.block_size * 8)
        self.bitmap_start_block = 2 + volume_directory_block_count
        self.allocation_bitmap = SOSAllocationBitmap(self, self.bitmap_start_block, self.bitmap_block_count, create = True, volume_block_count = self.block_count)
        self.volume_directory = SOSDirectory(self, 2, new = True, block_count = volume_directory_block_count)


    def close(self):
        if self.dirty:
            print('dirty')
            self.image_file.seek(0)
            self.image_file.write(reinterleave(self.data, interleave_tables['po'], interleave_tables[self.image_file_fmt]))
        self.data = None
        self.image_file.close()

    def get_blocks(self, first_block, count = 1):
        offset = first_block * 512
        length = count * 512
        return memoryview(self.data)[offset:offset+length]

    def files(self,
              path,
              recursive = True):
        return self.volume_directory.files(path, recursive)

    def print_directory(self,
                        recursive = False,
                        long = False,
                        file = sys.stdout):
        print('volume /%s:' % self.volume_directory.header.name)
        self.volume_directory.print('',
                                    #prefix = '/' + self.volume_directory.header.name,
                                    recursive = recursive,
                                    long = long,
                                    file = file)


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


if __name__ == '__main__':
    with open('foo.po', 'w') as f:
        disk = SOSDisk(f, new = True)
