import struct
import sys
from romhacking.common import BitArray, RingBuffer, Compression, LZSS


class LZANCIENT(LZSS):
    """
        Class to manipulate LZANCIENT Compression

        Games where this compression is found:
            - [SMD] Beyond Oasis
            - [SMD] Streets of Rage 2
    """

    signature = b'\x02\x00\x00\x60\xE7\x18\x06\x40\x00\x03\x02\x01\x00\x1F'

    def __init__(self, input_data):
        super(LZANCIENT, self).__init__(input_data)

    def bitclear(self, value=0x0, index=0):
        if (value >> index) & 0x1:
            return value ^ (1 << index)
        return value

    def rotate_bits_left(self, value=0x0, bits_to_rotate=0, max_bits=8):
        return (value << bits_to_rotate % max_bits) & (2**max_bits-1) | ((value & (2**max_bits-1)) >> (max_bits-(bits_to_rotate % max_bits)))

    def decompress(self, offset=0):
        self._output = bytearray()
        self.DATA.ENDIAN = ">"
        self.DATA.set_offset(offset+2)
        if self.DATA.read_8() == 0x0:
            pass
        else:
            self.DATA.set_offset(offset)
            low, high = self.DATA.read_8(), self.DATA.read_8()
            # to little endian
            compressed_size = ((high << 8) | low)
            while (self.DATA.CURSOR < offset+compressed_size):
                ctrl = self.DATA.read_8()
                if not self.bitclear(ctrl, 7) == ctrl:
                    # LZ From buffer
                    ctrl = self.bitclear(ctrl, 7)
                    repeats = self.rotate_bits_left((ctrl & 0x60), 3) + 4
                    _readed = self.DATA.read_8()
                    position = ((ctrl & 0x1F) << 8) | _readed
                    for i in range(repeats):
                        self._output.append(
                            self._output[len(self._output)-position])

                    ctrl = self.DATA.read_8()
                    while True:
                        if (ctrl & 0xE0) == 0x60:
                            repeats = (ctrl & 0x1F)
                            for i in range(repeats):
                                self._output.append(
                                    self._output[len(self._output)-position])
                        else:
                            self.DATA.CURSOR -= 1
                            break
                        ctrl = self.DATA.read_8()
                elif not self.bitclear(ctrl, 6) == ctrl:
                    # RLE
                    ctrl = self.bitclear(ctrl, 6)
                    if self.bitclear(ctrl, 4) == ctrl:
                        repeats = ctrl + 4
                    else:
                        ctrl = self.bitclear(ctrl, 4)
                        repeats = ((ctrl << 8) | self.DATA.read_8()) + 4
                    _readed = self.DATA.read_8()
                    for i in range(repeats):
                        self._output.append(_readed)
                else:
                    # RAW
                    if self.bitclear(ctrl, 5) == ctrl:
                        length = ctrl
                    else:
                        ctrl = self.DATA.read_8()
                        length = ctrl
                    for i in range(length):
                        self._output.append(self.DATA.read_8())
        return self._output

    def compress(self):
        self.DATA.ENDIAN = '<'
        self._window = RingBuffer(0x2000, 0x00, 0x00)
        self._input = bytearray(self.DATA.read())
        self._output = bytearray()
        self._output.append(0x0)
        self._output.append(0x0)
        self._encoded = 0
        self.LOOKAHEAD = 0b1111
        while self._encoded < self.DATA.SIZE:
            # Search for RLE match
            rle_match = self.find_best_rle_match()
            # Search for LZ matches
            lz_match = self.find_best_lz_match()
            # RAW
            if (rle_match < 4) and (lz_match[0] < 4):
                _readed = self.DATA.read_8()
                self._window.append(_readed)
                if self._window.CURSOR > 0x1FFF:
                    self.flush_window()
                self._encoded += 1
            # RLE
            elif rle_match >= lz_match[0]:
                if self._window.CURSOR > 0:
                    self.flush_window()
                for i in range(rle_match):
                    _readed = self.DATA.read_8()
                self._encoded += rle_match
                rle_match -= 4
                if rle_match > 0xF:
                    self._output.append(0x40 | 0x10 | ((rle_match >> 8) & 0xF))
                    self._output.append(rle_match & 0xFF)
                else:
                    self._output.append(0x40 | (rle_match & 0xF))
                self._output.append(_readed)
            # LZ
            else:
                if self._window.CURSOR > 0:
                    self.flush_window()
                self.DATA.CURSOR += lz_match[0]
                self._encoded += lz_match[0]
                lz_length, lz_offset = lz_match
                lz_length -= 4
                length = 3 if lz_length > 3 else lz_length
                self._output.append(0x80 | (length << 5) |
                                    ((lz_offset >> 8) & 0x1F))
                self._output.append(lz_offset & 0xFF)
                lz_length -= length
                while lz_length > 0:
                    length = 0x1F if lz_length > 0x1F else lz_length
                    self._output.append(0x60 | length)
                    lz_length -= length
        if self._window.CURSOR > 0:
            self.flush_window()
        self._output[0] = len(self._output) & 0xFF
        self._output[1] = len(self._output) >> 8
        self._output.append(0x0)
        return self._output

    def find_best_rle_match(self):
        best_match = 0
        for i in range(min(0xFFF+4, self.DATA.SIZE-self._encoded)):
            best_match = i
            if self._input[self._encoded] != self._input[self._encoded+i]:
                break
        return best_match

    def find_best_lz_match(self):
        best_match_length = 0
        best_match_offset = 0
        for i in range(1, min(0x1FFF, self._encoded)):
            for length in range(self.DATA.SIZE-self._encoded):
                if self._input[self._encoded + length] != self._input[self._encoded - i + length]:
                    break
                if (length+1) >= best_match_length:
                    best_match_length = length + 1
                    best_match_offset = i
        return (best_match_length, best_match_offset)

    def flush_window(self):
        if self._window.CURSOR > 0x1F:
            self._output.append(0x20 | ((self._window.CURSOR >> 8) & 0x1F))
            self._output.append(self._window.CURSOR & 0xFF)
        else:
            self._output.append(self._window.CURSOR)
        for i in range(0, self._window.CURSOR):
            self._output.append(self._window._buffer[i])
        self._window.byte_fill(self._window.BYTE_FILL)
        self._window.CURSOR = 0
