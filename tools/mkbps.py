"""Make / apply BPS patches (pure Python, no dependencies).

  python tools/mkbps.py make  <source.nds> <target.nds> <out.bps>
  python tools/mkbps.py apply <source.nds> <patch.bps> <out.nds>

The encoder copies unchanged data from the source (SourceRead / SourceCopy, found with a block hash
index, so moved files cost almost nothing), run-length encodes padding with TargetCopy, and stores
everything else as literals. Output works with Rom Patcher JS, Floating IPS (flips) and beat.
"""
import struct, sys, zlib

BLOCK = 32          # bytes per hashed source block


def vint(n):
    out = bytearray()
    while True:
        x = n & 0x7F; n >>= 7
        if n == 0: out.append(0x80 | x); return bytes(out)
        out.append(x); n -= 1


def svint(d):
    return vint((abs(d) << 1) | (1 if d < 0 else 0))


def match_len(a, ai, b, bi, limit=None):
    """Length of the common run a[ai:] == b[bi:]."""
    n = min(len(a) - ai, len(b) - bi)
    if limit is not None: n = min(n, limit)
    if n >= 8 and a[ai:ai + 8] != b[bi:bi + 8]:          # cheap reject
        L = 0
        while L < 8 and a[ai + L] == b[bi + L]: L += 1
        return L
    L = 0; step = 64
    while L < n:
        k = min(step, n - L)
        if a[ai + L:ai + L + k] == b[bi + L:bi + L + k]:
            L += k; step = min(step * 2, 1 << 20)
        elif k <= 16:
            while L < n and a[ai + L] == b[bi + L]: L += 1
            return L
        else:
            step = max(16, k // 2)
    return L


def make(src, tgt):
    src = bytes(src); tgt = bytes(tgt)
    index = {}
    for p in range(0, len(src) - BLOCK + 1, BLOCK):
        blk = src[p:p + BLOCK]
        if blk.count(blk[0]) == BLOCK: continue          # padding: handled by RLE instead
        index.setdefault(blk, p)

    out = bytearray(b'BPS1'); out += vint(len(src)) + vint(len(tgt)) + vint(0)
    state = {'srel': 0, 'trel': 0}
    lit_start = 0

    def flush(upto):
        if upto > lit_start:
            n = upto - lit_start
            out.extend(vint(((n - 1) << 2) | 1)); out.extend(tgt[lit_start:upto])

    t = 0; last_delta = 0
    while t < len(tgt):
        best = None
        # 1) same offset as source (SourceRead)
        if t < len(src):
            L = match_len(src, t, tgt, t)
            if L >= 8: best = ('sread', t, L)
        # 2) continue the previous copy's displacement
        if best is None:
            s = t + last_delta
            if 0 <= s < len(src):
                L = match_len(src, s, tgt, t)
                if L >= 8: best = ('scopy', s, L)
        # 3) uniform run -> RLE via TargetCopy
        if best is None and t + BLOCK <= len(tgt):
            blk = tgt[t:t + BLOCK]
            if blk.count(blk[0]) == BLOCK:
                L = BLOCK
                while t + L < len(tgt) and tgt[t + L] == blk[0]: L += 1
                best = ('rle', None, L)
            else:
                s = index.get(blk)
                if s is not None:
                    # extend backwards into pending literals
                    back = 0
                    while t - back > lit_start and s - back > 0 and src[s - back - 1] == tgt[t - back - 1]: back += 1
                    t -= back; s -= back
                    best = ('scopy', s, match_len(src, s, tgt, t))
        if best is None:
            t += 1; continue
        kind, s, L = best
        flush(t)
        if kind == 'sread':
            out.extend(vint(((L - 1) << 2) | 0))
        elif kind == 'scopy':
            out.extend(vint(((L - 1) << 2) | 2)); out.extend(svint(s - state['srel']))
            state['srel'] = s + L; last_delta = s - t
        else:                                             # literal 1 byte, then TargetCopy from it
            out.extend(vint((0 << 2) | 1)); out.append(tgt[t])
            out.extend(vint(((L - 2) << 2) | 3)); out.extend(svint(t - state['trel']))
            state['trel'] = t + (L - 1)
        t += L; lit_start = t
    flush(len(tgt))
    out += struct.pack('<I', zlib.crc32(src)) + struct.pack('<I', zlib.crc32(tgt))
    out += struct.pack('<I', zlib.crc32(bytes(out)))
    return bytes(out)


def rvint(d, p):
    n = 0; shift = 1
    while True:
        x = d[p]; p += 1
        n += (x & 0x7F) * shift
        if x & 0x80: return n, p
        shift <<= 7; n += shift


def apply(src, patch):
    assert patch[:4] == b'BPS1', 'not a BPS patch'
    assert zlib.crc32(patch[:-4]) == struct.unpack('<I', patch[-4:])[0], 'patch is corrupted'
    scrc, tcrc = struct.unpack('<II', patch[-12:-4])
    assert zlib.crc32(src) == scrc, 'wrong source ROM (CRC32 %08X, expected %08X)' % (zlib.crc32(src), scrc)
    p = 4
    ssize, p = rvint(patch, p); tsize, p = rvint(patch, p); msize, p = rvint(patch, p); p += msize
    out = bytearray(); srel = trel = 0; end = len(patch) - 12
    while p < end:
        v, p = rvint(patch, p); mode, L = v & 3, (v >> 2) + 1
        if mode == 0: out += src[len(out):len(out) + L]
        elif mode == 1: out += patch[p:p + L]; p += L
        else:
            o, p = rvint(patch, p); o = -(o >> 1) if o & 1 else (o >> 1)
            if mode == 2: srel += o; out += src[srel:srel + L]; srel += L
            else:
                trel += o
                for _ in range(L): out.append(out[trel]); trel += 1
    assert len(out) == tsize and zlib.crc32(out) == tcrc, 'output CRC mismatch'
    return bytes(out)


if __name__ == '__main__':
    cmd = sys.argv[1]
    a = open(sys.argv[2], 'rb').read(); b = open(sys.argv[3], 'rb').read()
    res = make(a, b) if cmd == 'make' else apply(a, b)
    open(sys.argv[4], 'wb').write(res)
    print('wrote', sys.argv[4], len(res), 'bytes')
