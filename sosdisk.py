import datetime
from enum import Enum, IntEnum, IntFlag
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
    a2_pascal_area          = 0x04  # Apple II Pascal area
    subdirectory            = 0x0d
    subdirectory_header     = 0x0e
    volume_directory_header = 0x0f
    


class FileType(Enum):
    unknown                 = 0x00, 'UNK'
    bad_blocks              = 0x01, 'BAD'
    code                    = 0x02, 'PCD'  # SOS only
    pascal_text             = 0x03, 'PTX'  # SOS only
    text                    = 0x04, 'TXT'  # normal ASCII text file
    pascal_data             = 0x05, 'PDA'  # SOS only
    binary                  = 0x06, 'BIN'
    font                    = 0x07, 'FNT'  # SOS only
    screen_image            = 0x08, 'FOT'
    business_basic_program  = 0x09, 'BA3'  # SOS only
    business_basic_data     = 0x0a, 'DA3'  # SOS only
    word_processor          = 0x0b, 'WPF'  # SOS only
    sos_system              = 0x0c, 'SOS'  # SOS only
    # 0x0d..0x0e reserved for SOS
    subdirectory            = 0x0f, 'DIR'
    rps_data                = 0x10, 'RPD'  # SOS only
    rps_index               = 0x11, 'RPI'  # SOS only
    applefile_discard       = 0x12, 'AFD'  # SOS only
    applefile_model         = 0x13, 'AFM'  # SOS only
    applefile_report_format = 0x14, 'AFR'  # SOS only
    screen_library          = 0x15, 'SCL'  # SOS only
    # 0x16..0x18 reserved for SOS
    appleworks_data_base    = 0x19, 'ADB'
    appleworks_word_proc    = 0x1a, 'AWP'
    appleworks_spreadsheet  = 0x1b, 'ASP'
    # 0xe0..0xff are ProDOS only
    edasm_816_reolcatable   = 0xee, 'R16'
    pascal_area             = 0xef, 'PAR'
    prodos_ci_added_command = 0xf0, 'CMD'
    # 0xf1..0xf8 are ProDOS user-defined file types 1-8
    user_defined_1          = 0xf1, 'OVL'
    user_defined_2          = 0xf2, 'UD2'
    user_defined_3          = 0xf3, 'UD3'
    user_defined_4          = 0xf4, 'UD4'
    user_defined_5          = 0xf5, 'BAT'
    user_defined_6          = 0xf6, 'UD6'
    user_defined_7          = 0xf7, 'UD7'
    user_defined_8          = 0xf8, 'PRG'
    prodos_16_system        = 0xf9, 'P16'
    integer_basic_program   = 0xfa, 'INT'
    integer_basic_variables = 0xfb, 'IVR'
    applesoft_program       = 0xfc, 'BAS'
    applesoft_variables     = 0xfd, 'VAR'
    relocatable_code        = 0xfe, 'REL'  # EDASM
    prodos_system           = 0xff, 'SYS'

    def __new__(cls, int_value, abbrev):
        obj = object.__new__(cls)
        obj._value_ = int_value
        obj.abbrev = abbrev
        return obj

    def __int__(self):
        return self.value


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
    s = str(b, 'ascii')
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
    

class SOSStorage:
    @classmethod
    def create(cls, disk, storage_type, key_pointer):
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


class SOSSeedling(SOSStorage):
    def __init__(self, disk, key_pointer):
        super().__init__(disk, key_pointer)
        self.disk.mark_used(key_pointer)
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
                self.disk.mark_used(b)
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
                        self.disk.mark_used(b)
                        self.data_blocks += 1
                        self.last_block_index = j

class SOSDirectoryEntry:
    def __init__(self, disk):
        self.disk = disk

    def print(self,
              prefix,
              recursive = False,
              long = False,
              file = sys.stdout):
        pass


class SOSVolumeDirectoryHeader(SOSDirectoryEntry):
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

class SOSSubdirectoryHeader(SOSDirectoryEntry):
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
            assert self.file_type == int(FileType.subdirectory)
            self.subdir = SOSDirectory(disk, self.key_pointer)
        else:
            assert self.storage_type in set([StorageType.seedling, StorageType.sapling, StorageType.tree])
            assert self.file_type != int(FileType.subdirectory)
            self.storage = SOSStorage.create(self.disk, self.storage_type, self.key_pointer)


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
                ft = FileType(self.file_type)
                fts = ft.abbrev
            except ValueError as e:
                fts = '$%02x' % self.file_type
            print('  %s  %s  %s  %6d' % (self.creation, fts, attrs, self.eof), end = '', file = file)
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
            entry_data = memoryview(data[offset: offset+self.directory.entry_length])
            if first_dir_block and i == 0:
                if block_num == 2:
                    self.entries.append(SOSVolumeDirectoryHeader(self.disk, entry_data))
                else:
                    self.entries.append(SOSSubdirectoryHeader(self.disk, entry_data))
            else:
                self.entries.append(SOSFileEntry(self.disk, entry_data))

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
        # if recursive:
        #     for db in self.directory_blocks:
        #         for entry in db.entries:
        #             if hasattr(entry, 'subdir'):
        #                 entry.subdir.print('',
        #                                    recursive = recursive,
        #                                    file = file)


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
        self.used = [False] * self.block_count
        if self.image_file_fmt != 'po':
            if len(self.data) != (35 * 8 * self.block_size):
                print('Images other than 16-sector floppy must be in SOS/ProDOS sector order', file = sys.stderr)
                sys.exit(2)
            self.data = reinterleave(self.data, interleave_tables[self.image_file_fmt], interleave_tables['po'])
        self.mark_used(0, 2)  # boot blocks
        self.volume_directory = SOSDirectory(self, 2, new = False)
        self.bitmap_block_count = (self.volume_directory.header.total_blocks + 1) // (self.block_size * 8)
        self.bitmap_start_block = self.volume_directory.header.bitmap_pointer
        self.mark_used(self.volume_directory.header.bitmap_pointer, self.bitmap_block_count)

    def __create_new(volume_block_count = 280, volume_directory_block_count = 4):
        self.data = bytearray(size * self.block_size)
        self.mark_used(0, 2)  # boot blocks

        self.bitmap_block_count = (volume_block_count + 1) // (self.block_size * 8)
        self.bitmap_start_block = 2 + volume_directory_block_count
        self.mark_used(self.bitmap_start_block, self.bitmap_block_count)  # allocation bitmap
        self.volume_directory = SOSDirectory(self, 2, new = True, block_count = volume_directory_block_count)


    def close(self):
        if self.dirty:
            self.image_file.seek(0)
            self.image_file.write(reinterleave(self.data, interleave_tables['po'], interleave_tables[self.image_file_fmt]))
        self.data = None
        self.image_file.close()

    def mark_used(self, first_block, count = 1):
        for block in range(first_block, first_block + count):
            if self.used[block]:
                print('block %d multiply used' % block)
            self.used[block] = True

    def get_blocks(self, first_block, count = 1):
        self.mark_used(first_block, count)
        offset = first_block * 512
        length = count * 512
        return memoryview(self.data[offset:offset+length])

    def alloc_block(self):
        pass

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
