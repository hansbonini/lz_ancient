import os
import argparse
import textwrap
import sys
from os import SEEK_CUR, SEEK_END, SEEK_SET
from romhacking.common import TBL
from genesis.common import ROM
from genesis.data_compression import LZANCIENT

cmd = argparse.ArgumentParser(
    formatter_class=argparse.RawDescriptionHelpFormatter,
    description=textwrap.dedent('''\
            [SMD] LZANCIENT Compressor / Decompressor
            ----------------------------------------------
            Tool for decompress and recompress graphics
            from games developed by Ancient using LZ+RLE
            algorithm.
            ----------------------------------------------
            List of know compatible games;
                - [SMD] Beyond Oasis
                - [SMD] Streets of Rage 2
            ----------------------------------------------
            For decompress:
                python main.py D rom decompressed_file offset
            For compress:
                python main.py C rom decompressed_file offset_to_be_inserted_in_rom
        ''')
)


def decompress(offset, rom_path, decompressed_data_path, codec=None):
    rom = ROM(rom_path, 'msb')
    algorithm = codec(rom)
    out = open(decompressed_data_path, 'wb')
    data = algorithm.decompress(offset)
    data_len = len(data)
    print('[INFO] Decompressed Size: {:08x}'.format(data_len))
    out.write(data)
    print('[INFO] Finished!')


def compress(offset, rom_path, decompressed_data_path, codec=None):
    rom = open(rom_path, 'r+b')
    input = ROM(decompressed_data_path, 'msb')
    algorithm = codec(input)
    data = algorithm.compress()
    data_len = len(data)
    print('[INFO] Compressed Size: {:08x}'.format(data_len))
    rom.seek(offset, 0)
    rom.write(data)
    rom.close()
    input.close()
    print('[INFO] Finished!')


if __name__ == "__main__":

    cmd.add_argument(
        'option',
        nargs='?',
        type=str,
        default=None,
        help='"C" for Compression / "D" for Decompression'
    )

    cmd.add_argument(
        'rom',
        nargs='?',
        type=argparse.FileType('rb'),
        default=sys.stdin,
        help='Sega Genesis / Sega Mega Drive ROM or Compressed File'
    )

    cmd.add_argument(
        'output',
        nargs='?',
        type=str,
        default=None,
        help='Decompressed file.'
    )

    cmd.add_argument(
        'offset',
        nargs='?',
        type=lambda x: int(x, 0),
        default=None,
        help='Offset'
    )

    args = cmd.parse_args()
    print(cmd.description)
    if args.option not in ['C', 'D']:
        print('[ERROR] Option must be "C" for Compression or "D" for Decompression')
        sys.exit(0)
    if args.rom.name == '<stdin>':
        print(
            '[ERROR] An Sega Genesis / Sega Mega Drive ROM or Compressed File must be specified')
        sys.exit(0)
    if args.output == None:
        print('[ERROR] An Output File must be specified')
        sys.exit(0)
    if args.offset == None:
        print('[ERROR] An Offset must be specified')
        sys.exit(0)
    if (args.option == 'D'):
        print('[INFO] Decompressing at {:08x}...'.format(args.offset))
        decompress(args.offset, args.rom.name, args.output, LZANCIENT)
    else:
        print('[INFO] Compressing and inserting at {:08x}...'.format(
            args.offset))
        compress(args.offset, args.rom.name, args.output, LZANCIENT)
