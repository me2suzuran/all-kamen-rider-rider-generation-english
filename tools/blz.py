"""ARM9 backward-LZ (BLZ) compression that reproduces the original binary's exact size.

Loaders such as nds-bootstrap (TWiLight Menu++ on DSi/3DS) find the BLZ footer at the end of the
ARM9 binary as given by the header size, not via the module-params end pointer. The game boots on
emulators either way, but on hardware a shorter ARM9 padded with zeros gives a white screen. So the
recompressed ARM9 must end exactly where the original did, with the footer in its last 8 bytes.

compress_exact() compresses the whole body once, then picks how much of the bottom to leave raw
(the cut point in the token stream) so that raw + compressed + footer == the wanted size.
"""
import struct
from ndspy import _lzCommon

PREFIX = 0x4000          # first 16 KB of ARM9 is never compressed (secure area / crt0)


def _tokens(s):
    """Walk a reversed BLZ stream (top of the data first). Yields (c, d, group_end) after each token:
    compressed bytes consumed, decompressed bytes produced."""
    i = d = 0
    while i < len(s):
        flag = s[i]; i += 1
        for bit in range(8):
            if i >= len(s): return
            if flag & (0x80 >> bit):
                d += (s[i] >> 4) + 3; i += 2
            else:
                d += 1; i += 1
            yield i, d, bit == 7


def decompress_inplace(buf, end):
    """Simulate the in-place hardware decompressor on buf[:end] (buf must have room after end).
    Returns the decompressed length, or raises if the write pointer would overrun unread input."""
    a, inc = struct.unpack_from('<II', buf, end - 8)
    enc_len, hdr_len = a & 0xFFFFFF, a >> 24
    src = end - hdr_len; stop = end - enc_len; dst = end + inc
    while src > stop:
        src -= 1; flag = buf[src]
        for bit in range(8):
            if src <= stop: break
            if flag & (0x80 >> bit):
                src -= 2; hi, lo = buf[src + 1], buf[src]
                n = (hi >> 4) + 3; disp = (((hi & 0xF) << 8) | lo) + 3
                for _ in range(n):
                    dst -= 1; buf[dst] = buf[dst + disp]
            else:
                src -= 1; dst -= 1; buf[dst] = buf[src]
            if dst < src: raise ValueError('in-place overrun at %x' % dst)
    return end + inc


def compress_exact(data, size):
    """Compress ARM9 `data` (decompressed, module params already final) to exactly `size` bytes."""
    body = bytes(data[PREFIX:]); N = len(body); T = size - PREFIX
    s, _, _ = _lzCommon.compress(bytes(reversed(body)), 3, 0x1002, 18, False, True)
    s = bytes(s)
    best = None
    for c, d, gend in _tokens(s):
        hdr = T - (N - d + c)
        if 8 <= hdr <= 11 and (best is None or (gend and not best[2])):
            best = (c, d, gend)
            if gend: break
    if best is None: raise SystemExit('BLZ: no cut point gives exactly %d bytes' % size)
    c, d, _ = best; hdr = T - (N - d + c)
    out = bytearray(data[:PREFIX]) + body[:N - d] + bytes(reversed(s[:c])) + b'\xff' * (hdr - 8)
    out += struct.pack('<II', (c + hdr) | (hdr << 24), d - c - hdr)
    assert len(out) == size
    # verify with the in-place algorithm the hardware uses
    buf = bytearray(out) + bytes(len(data) - size)
    assert decompress_inplace(buf, size) == len(data) and bytes(buf[:len(data)]) == bytes(data), 'BLZ verify failed'
    return bytes(out)
