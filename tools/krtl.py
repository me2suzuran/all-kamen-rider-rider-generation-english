"""All Kamen Rider: Rider Generation (NDS) - English translation tool.

Usage:
  python -I tools/krtl.py extract   # dump Japanese text into tl/*.json (keeps existing English)
  python -I tools/krtl.py check     # validate translations (length, charset)
  python -I tools/krtl.py build     # write translated ROM
"""
import json, os, struct, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import ndspy.rom
from krscript import parse as sc_parse, build as sc_build

SRC_ROM = os.path.join(ROOT, 'All Kamen Rider - Rider Generation (Japan).nds')
OUT_ROM = os.path.join(ROOT, 'All Kamen Rider - Rider Generation (English).nds')
TL = os.path.join(ROOT, 'tl')

SCRIPT_DIR = '_Data/Event/Script/'
SCRIPT_FILES = ['prologue', '01_00', '01_01', '02_00', '02_01', '02_02', '03_00', '03_01',
                '04_00', '04_01', '05_00', '05_01', 'afterboss_02', 'afterboss_03',
                'afterboss_04', 'epilogue']
# record files: u32 n, u32 sizes[n], records of [01 param][len+sjis]...
REC_FILES = ['_Data/WorldMap/narration.bin', '_Data/Bonus/c_bunus.bin',
             '_Data/Bonus/m_bunus_total.bin', '_Data/Bonus/m_bunus_world.bin',
             '_Data/Password/02.bin', '_Data/Password/03.bin', '_Data/Shop/shop_str.bin']
NAME_FILE = '_Data/Event/Script/ScriptName.bin'
WORLD_FILES = ['_Data/WorldMap/world0%d.bin' % i for i in range(1, 6)]

MAX_LINE = 40          # hard cap in chars per dialogue line
MAX_PX = 220           # dialogue box text width in pixels (box clips at ~226px)
ENC = 'cp932'
DLG_FONT = '_Data/font/Font1212R_Base14Lite.NFTR'   # outlined font used by event dialogue
APOS_SLOT = '|'        # dialogue font has no apostrophe glyph: we redraw '|' as one
SPACE_PX = 4


def enc(s, dialogue=False):
    """English text -> game bytes. ASCII is single-byte in the game's SJIS font."""
    s = s.replace('…', '...').replace('’', "'").replace('‘', "'") \
         .replace('“', '"').replace('”', '"').replace('—', '-').replace('–', '-')
    if dialogue: s = s.replace("'", APOS_SLOT)
    return s.encode(ENC)


# ---------------------------------------------------------------- dialogue font
def font_patch(d):
    """Make ASCII glyphs of the dialogue font proportional and add an apostrophe."""
    from nftr import parse, charmap
    d = bytearray(d); info = parse(bytes(d)); cmap = charmap(info)
    cw, ch, ts, bpp = info['cellw'], info['cellh'], info['tilesize'], info['bpp']
    wb = info['cwdh'] + 16                      # 3-byte (left, glyph width, advance) records
    # apostrophe: redraw the '|' cell as a short tick at the top-left
    g = cmap[ord(APOS_SLOT)]
    pix = [[0] * cw for _ in range(ch)]
    for y, row in enumerate([[5, 3], [7, 3], [7, 3], [2, 3]]):
        for x, v in enumerate(row): pix[2 + y][x] = v
    bits = ''.join(format(pix[y][x], '0%db' % bpp) for y in range(ch) for x in range(cw))
    bits = bits.ljust(ts * 8, '0')
    off = info['cglp'] + 16 + g * ts
    d[off:off + ts] = int(bits, 2).to_bytes(ts, 'big')
    d[wb + 3 * g:wb + 3 * g + 3] = bytes([0, 2, 3])
    for c in range(0x20, 0x7f):
        if c not in cmap or chr(c) == APOS_SLOT: continue
        g = cmap[c]; left, gw, adv = d[wb + 3 * g:wb + 3 * g + 3]
        d[wb + 3 * g:wb + 3 * g + 3] = bytes([0, 0, SPACE_PX]) if c == 0x20 else bytes([0, gw, gw + 1])
    return bytes(d)


_FONT = None
def line_px(b):
    """Pixel width of encoded dialogue bytes with the patched font."""
    global _FONT
    from nftr import parse, charmap, widths
    if _FONT is None:
        info = parse(font_patch(load_rom().getFileByName(DLG_FONT)))
        _FONT = (charmap(info), widths(info))
    cmap, w = _FONT; t = 0; i = 0
    while i < len(b):
        c = b[i]
        if c >= 0x80: c = (c << 8) | b[i + 1]; i += 2
        else: i += 1
        t += w[cmap[c]][2] if c in cmap else 12
    return t


def missing_glyphs(b):
    from nftr import charmap
    line_px(b'')
    return sorted({chr(c) for c in b if c < 0x80 and c not in _FONT[0]})


# ---------------------------------------------------------------- record files
def rec_parse(d):
    n = struct.unpack_from('<I', d, 0)[0]
    sizes = struct.unpack_from('<%dI' % n, d, 4)
    p = 4 + 4 * n
    recs = []
    for s in sizes:
        r = d[p:p + s]; p += s
        toks = []; i = 0
        while i < len(r):
            if r[i] == 0x01:           # opcode 01 + 1 param byte
                toks.append(('op', r[i:i + 2])); i += 2
            else:
                L = r[i]; toks.append(('s', r[i + 1:i + 1 + L])); i += 1 + L
        recs.append(toks)
    assert p == len(d)
    return recs


def rec_build(recs):
    blobs = []
    for toks in recs:
        b = b''
        for t, v in toks:
            if t == 'op': b += v
            else:
                assert len(v) >= 2 or len(v) == 0, v
                b += bytes([len(v)]) + v
        blobs.append(b)
    return struct.pack('<I', len(blobs)) + b''.join(struct.pack('<I', len(x)) for x in blobs) + b''.join(blobs)


# ---------------------------------------------------------------- name list
def names_parse(d):
    ver, n = struct.unpack_from('<IH', d, 0)
    p = 6; out = []
    for _ in range(n):
        L = d[p]; out.append(d[p + 1:p + 1 + L]); p += 1 + L
    assert p == len(d)
    return ver, out


def names_build(ver, names):
    return struct.pack('<IH', ver, len(names)) + b''.join(bytes([len(s)]) + s for s in names)


# ---------------------------------------------------------------- world map (fixed-size, in place)
def world_strings(d):
    """Find length-prefixed SJIS strings (may contain CRLF) inside world map binaries."""
    def scan(ascii_lead):
        res = []; i = 0
        while i < len(d) - 2:
            L = d[i]; c0 = d[i + 1]
            lead = (0x30 <= c0 <= 0x5a) if ascii_lead else (0x81 <= c0 <= 0x84 or 0x88 <= c0 <= 0x9f)
            in_crlf = i > 0 and d[i - 1] == 0x0d and L == 0x0a
            if 4 <= L and i + 1 + L <= len(d) and lead and not in_crlf:
                raw = d[i + 1:i + 1 + L]
                try:
                    t = raw.decode(ENC)
                    if all(c in '\r\n' or ord(c) >= 0x20 for c in t) and any('぀' <= c <= 'ヿ' or '０' <= c <= 'ｚ' for c in t):
                        res.append((i, raw)); i += 1 + L; continue
                except UnicodeDecodeError:
                    pass
            i += 1
        return res
    strict = scan(False)
    covered = set()
    for o, r in strict: covered.update(range(o, o + 1 + len(r)))
    loose = [(o, r) for o, r in scan(True) if not covered.intersection(range(o, o + 1 + len(r)))]
    return sorted(strict + loose)


# ---------------------------------------------------------------- io helpers
def jload(p, default):
    if os.path.exists(p):
        with open(p, encoding='utf-8') as f: return json.load(f)
    return default


def jsave(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


def merge(entries, old):
    """entries: list of jp strings (unique, ordered). old: list of {jp,en} -> keep en."""
    prev = {e['jp']: e.get('en', '') for e in old}
    return [{'jp': j, 'en': prev.get(j, '')} for j in entries]


def uniq(seq):
    seen = set(); out = []
    for x in seq:
        if x not in seen: seen.add(x); out.append(x)
    return out


def load_rom():
    return ndspy.rom.NintendoDSRom.fromFile(SRC_ROM)


def fdata(rom, name):
    return rom.getFileByName(name)


# ---------------------------------------------------------------- extract
def extract():
    rom = load_rom()
    for f in SCRIPT_FILES:
        chunks = sc_parse(fdata(rom, SCRIPT_DIR + f + '.dat'))
        jp = uniq(s.decode(ENC) for code, strs in chunks for s in strs)
        p = os.path.join(TL, 'script', f + '.json')
        jsave(p, merge(jp, jload(p, [])))
        # readable context dump: chunk by chunk
        with open(os.path.join(TL, 'script', f + '.context.txt'), 'w', encoding='utf-8', newline='\n') as o:
            for ci, (code, strs) in enumerate(chunks):
                o.write('--- variant %d\n' % ci)
                for s in strs: o.write(s.decode(ENC) + '\n')
    misc = {}
    _, names = names_parse(fdata(rom, NAME_FILE))
    misc[NAME_FILE] = [n.decode(ENC) for n in names]
    for f in REC_FILES:
        recs = rec_parse(fdata(rom, f))
        misc[f] = uniq(v.decode(ENC) for toks in recs for t, v in toks if t == 's' and v)
    p = os.path.join(TL, 'misc.json'); old = jload(p, {})
    jsave(p, {k: merge(v, old.get(k, [])) for k, v in misc.items()})
    world = {}
    for f in WORLD_FILES:
        world[f] = uniq(raw.decode(ENC) for off, raw in world_strings(fdata(rom, f)))
    p = os.path.join(TL, 'world.json'); old = jload(p, {})
    jsave(p, {k: merge(v, old.get(k, [])) for k, v in world.items()})
    print('extracted to', TL)


# ---------------------------------------------------------------- check / build
def table(entries):
    return {e['jp']: e['en'] for e in entries if e.get('en')}


def check(verbose=True):
    errs = []; done = tot = 0
    for f in SCRIPT_FILES:
        for e in jload(os.path.join(TL, 'script', f + '.json'), []):
            tot += 1
            if not e.get('en'): continue
            done += 1
            try: b = enc(e['en'], dialogue=True)
            except UnicodeEncodeError as x: errs.append('%s: non-encodable %r' % (f, e['en'])); continue
            if any(c >= 0x80 for c in b): errs.append('%s: non-ASCII %r' % (f, e['en']))
            if len(e['en']) > MAX_LINE: errs.append('%s: too long (%d) %r' % (f, len(e['en']), e['en']))
            px = line_px(b)
            if px > MAX_PX: errs.append('%s: too wide (%dpx > %d) %r' % (f, px, MAX_PX, e['en']))
            mg = missing_glyphs(b)
            if mg: errs.append('%s: no glyph for %s in %r' % (f, mg, e['en']))
            if len(b) > 255: errs.append('%s: >255 bytes' % f)
    misc = jload(os.path.join(TL, 'misc.json'), {})
    for f, ents in misc.items():
        for e in ents:
            tot += 1
            if e.get('en'):
                done += 1
                try:
                    b = enc(e['en'])
                    if len(b) == 1 and f != NAME_FILE: errs.append('%s: 1-byte string not allowed %r' % (f, e['en']))
                except UnicodeEncodeError: errs.append('%s: non-encodable %r' % (f, e['en']))
    world = jload(os.path.join(TL, 'world.json'), {})
    for f, ents in world.items():
        for e in ents:
            tot += 1
            if e.get('en'):
                done += 1
                n = len(enc(e['en'].replace('\n', '\r\n'))); m = len(e['jp'].encode(ENC))
                if n > m: errs.append('%s: %r is %d bytes, max %d' % (f, e['en'], n, m))
    if verbose:
        for x in errs: print('ERR', x)
        print('translated %d/%d, %d errors' % (done, tot, len(errs)))
    return errs


def build():
    if check(verbose=True):
        print('fix errors first'); sys.exit(1)
    rom = load_rom()
    for f in SCRIPT_FILES:
        name = SCRIPT_DIR + f + '.dat'
        t = table(jload(os.path.join(TL, 'script', f + '.json'), []))
        chunks = sc_parse(fdata(rom, name))
        new = [(code, [enc(t[s.decode(ENC)], dialogue=True) if s.decode(ENC) in t else s for s in strs]) for code, strs in chunks]
        rom.setFileByName(name, sc_build(new))
    misc = jload(os.path.join(TL, 'misc.json'), {})
    t = table(misc.get(NAME_FILE, []))
    ver, names = names_parse(fdata(rom, NAME_FILE))
    rom.setFileByName(NAME_FILE, names_build(ver, [enc(t[n.decode(ENC)], dialogue=True) if n.decode(ENC) in t else n for n in names]))
    for f in REC_FILES:
        t = table(misc.get(f, []))
        recs = rec_parse(fdata(rom, f))
        recs = [[(k, enc(t[v.decode(ENC)]) if k == 's' and v and v.decode(ENC) in t else v) for k, v in toks] for toks in recs]
        rom.setFileByName(f, rec_build(recs))
    world = jload(os.path.join(TL, 'world.json'), {})
    for f in WORLD_FILES:
        t = table(world.get(f, []))
        d = bytearray(fdata(rom, f))
        for off, raw in world_strings(bytes(d)):
            j = raw.decode(ENC)
            if j in t:
                b = enc(t[j].replace('\r\n', '\n').replace('\n', '\r\n'))
                d[off + 1:off + 1 + len(raw)] = b.ljust(len(raw), b' ')
        rom.setFileByName(f, bytes(d))
    rom.setFileByName(DLG_FONT, font_patch(rom.getFileByName(DLG_FONT)))
    patch_arm9(rom)
    import gfxtl
    n, t = gfxtl.apply_all(rom)
    print('images: %d edited (%d tiles/objs written)' % (n, t))
    if os.environ.get('KR_NO_ARM9'):
        rom.arm9 = load_rom().arm9; print('TEST BUILD: original ARM9 kept')
    out = write_in_place(rom)
    with open(OUT_ROM, 'wb') as f: f.write(out)
    print('wrote', OUT_ROM)


def write_in_place(rom):
    """Write the modified ROM over a copy of the original image, keeping the original layout.

    Header, ARM7, overlays, FNT, icon and every unchanged file stay at their original offsets.
    A changed file is written at its old offset when it fits in its old slot (up to the next item);
    otherwise it goes into the free 0xFF area after the original data. Only FAT entries change."""
    img = bytearray(open(SRC_ROM, 'rb').read())
    orig = load_rom()
    hdr = bytes(img[:0x200])
    fat_off, fat_size = struct.unpack_from('<II', hdr, 0x48)
    arm9_off, arm9_size = struct.unpack_from('<I', hdr, 0x20)[0], struct.unpack_from('<I', hdr, 0x2C)[0]
    used = struct.unpack_from('<I', hdr, 0x80)[0]
    # ARM9: same offset, padded to the original size (decompression uses the module-params end pointer)
    a9 = bytes(rom.arm9)
    if len(a9) > arm9_size: raise SystemExit('ARM9 grew (%d > %d)' % (len(a9), arm9_size))
    img[arm9_off:arm9_off + arm9_size] = a9 + bytes(arm9_size - len(a9))
    # occupied regions, to know how big each file's slot is
    nfiles = fat_size // 8
    fat = [struct.unpack_from('<II', img, fat_off + 8 * i) for i in range(nfiles)]
    starts = sorted({s for s, e in fat if e > s} | {struct.unpack_from('<I', hdr, o)[0] for o in (0x20, 0x30, 0x40, 0x48, 0x50, 0x58, 0x68)} | {used})
    import bisect
    free = (used + 0x1FF) & ~0x1FF
    moved = inplace = 0
    for i, (s, e) in enumerate(fat):
        new = bytes(rom.files[i])
        if i < len(orig.files) and new == bytes(orig.files[i]): continue
        nxt = starts[bisect.bisect_right(starts, s)] if bisect.bisect_right(starts, s) < len(starts) else len(img)
        if e > s and len(new) <= nxt - s:
            img[s:nxt] = new + b'\xff' * (nxt - s - len(new)); inplace += 1
            struct.pack_into('<II', img, fat_off + 8 * i, s, s + len(new))
        else:
            if free + len(new) > len(img): raise SystemExit('no free space left in the ROM image')
            img[free:free + len(new)] = new
            struct.pack_into('<II', img, fat_off + 8 * i, free, free + len(new)); moved += 1
            free = (free + len(new) + 0x1FF) & ~0x1FF
    assert img[:0x4000] == open(SRC_ROM, 'rb').read(0x4000), 'header changed'
    print('in-place write: %d files in their old slot, %d moved to free space (end %d)' % (inplace, moved, free))
    return bytes(img)


def crc16(data):
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8): crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


def keep_original_header(rom):
    """Make the ROM header byte-identical to the original Japanese ROM.

    Flashcart kernels and nds-bootstrap (TWiLight Menu++) pick their anti-piracy fix by game code +
    header CRC16. If the header changes, no AP fix is applied and the game's anti-piracy kicks in.
    Only two header fields would change: the ARM9 size (our recompressed ARM9 is smaller) and the
    used-ROM size. We pad the ARM9 back to its original length (decompression uses the end pointer
    in the module params, not the size field, so trailing zeros are ignored) and pad the file."""
    orig = open(SRC_ROM, 'rb').read(0x4000)
    o_arm9 = struct.unpack_from('<I', orig, 0x2C)[0]
    o_used = struct.unpack_from('<I', orig, 0x80)[0]
    if len(rom.arm9) > o_arm9:
        raise SystemExit('ARM9 grew (%d > %d): header cannot match the original' % (len(rom.arm9), o_arm9))
    rom.arm9 = bytes(rom.arm9) + bytes(o_arm9 - len(rom.arm9))
    d = bytearray(rom.save())
    used = struct.unpack_from('<I', d, 0x80)[0]
    if used > o_used:
        raise SystemExit('ROM data grew past the original used size (%d > %d)' % (used, o_used))
    struct.pack_into('<I', d, 0x80, o_used)
    if len(d) < o_used: d += b'\xff' * (o_used - len(d))
    d[0x160:0x4000] = orig[0x160:0x4000]          # reserved header area (ndspy writes a stray value)
    struct.pack_into('<H', d, 0x15E, crc16(d[:0x15E]))
    if d[:0x4000] != orig:
        diff = [hex(i) for i in range(0x4000) if d[i] != orig[i]]
        print('WARN header still differs at', diff[:10])
    else:
        print('header identical to original (CRC16 %04X)' % struct.unpack_from('<H', d, 0x15E)[0])
    return bytes(d)


def arm9_sites(data, jp_bytes):
    """Null-terminated, 4-aligned occurrences of jp_bytes whose RAM address is referenced by a pointer.
    Returns (offset, capacity) where capacity excludes the terminator."""
    ptrs = set(struct.unpack_from('<%dI' % (len(data) // 4), data, 0))
    sites = []; i = data.find(jp_bytes)
    while i != -1:
        end = i + len(jp_bytes)
        if i % 4 == 0 and end < len(data) and data[end] == 0 and (0x02000000 + i) in ptrs:
            slot_end = (end + 1 + 3) & ~3          # string + terminator, padded to 4 bytes
            if all(b == 0 for b in data[end:slot_end]):
                sites.append((i, slot_end - i - 1))
        i = data.find(jp_bytes, i + 1)
    return sites


def patch_arm9(rom):
    import ndspy.codeCompression, blz
    tbl = jload(os.path.join(TL, 'arm9.json'), [])
    if not any(e.get('en') for e in tbl): return
    # Patch the decompressed image directly and recompress it to the original size, so the module
    # params (compressedStaticEnd) and the header ARM9 size stay byte-identical (see tools/blz.py).
    orig = bytes(rom.arm9)
    data = bytearray(ndspy.codeCompression.decompress(orig))
    for e in tbl:
        if not e.get('en'): continue
        jb = e['jp'].encode(ENC); eb = enc(e['en'])
        sites = arm9_sites(bytes(data), jb)
        if not sites: print('WARN arm9: not found', e['jp'])
        for off, cap in sites:
            if len(eb) > cap: raise SystemExit('arm9: %r too long (%d > %d)' % (e['en'], len(eb), cap))
            data[off:off + cap + 1] = eb + b'\0' * (cap + 1 - len(eb))
    rom.arm9 = blz.compress_exact(bytes(data), len(orig))


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'check'
    {'extract': extract, 'check': check, 'build': build}[cmd]()
