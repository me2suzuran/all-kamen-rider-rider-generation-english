"""Nitro graphics (NCLR / NCGR / NCBR / NSCR / NCER) decode + encode helpers."""
import struct
from PIL import Image

SIZES = {0: [(8, 8), (16, 16), (32, 32), (64, 64)],
         1: [(16, 8), (32, 8), (32, 16), (64, 32)],
         2: [(8, 16), (8, 32), (16, 32), (32, 64)]}


def section(d, magic):
    off = struct.unpack_from('<H', d, 0xC)[0]
    while off < len(d):
        m, size = d[off:off + 4], struct.unpack_from('<I', d, off + 4)[0]
        if m == magic: return off
        if size == 0: break
        off += size
    raise KeyError(magic)


# ------------------------------------------------------------------ palette
def nclr(d):
    s = section(d, b'TTLP')
    bpp, _, size, off = struct.unpack_from('<IIII', d, s + 8)
    raw = d[s + 8 + off: s + 8 + off + size]
    cols = []
    for i in range(0, len(raw) - 1, 2):
        v = struct.unpack_from('<H', raw, i)[0]
        cols.append(((v & 31) * 255 // 31, ((v >> 5) & 31) * 255 // 31, ((v >> 10) & 31) * 255 // 31))
    return cols


# ------------------------------------------------------------------ characters
class Chars:
    def __init__(self, d):
        self.d = bytearray(d)
        s = self.s = section(d, b'RAHC')
        self.h, self.w, bpp, self.mapping, self.tiled, self.size, self.off = struct.unpack_from('<HHIIIII', d, s + 8)
        self.bpp = 4 if bpp == 3 else 8
        self.base = s + 8 + self.off
        # tiled == 0: data is 8x8 tiles; tiled == 1: linear bitmap (we only meet 1D OBJ data here)

    def tile_bytes(self): return 8 * self.bpp

    def ntiles(self): return self.size // self.tile_bytes()

    def tile(self, byte_off):
        """64 palette indices of the 8x8 tile starting at byte offset into char data."""
        b = self.d[self.base + byte_off: self.base + byte_off + self.tile_bytes()]
        if len(b) < self.tile_bytes(): b = bytes(b) + bytes(self.tile_bytes() - len(b))
        if self.bpp == 8: return list(b)
        out = []
        for x in b: out += [x & 15, x >> 4]
        return out

    def set_tile(self, byte_off, px):
        if self.bpp == 8: b = bytes(px)
        else: b = bytes(px[i] | (px[i + 1] << 4) for i in range(0, 64, 2))
        self.d[self.base + byte_off: self.base + byte_off + len(b)] = b

    def append_tile(self, px):
        """Append one 8x8 tile at the end of the char data, return its index."""
        tb = self.tile_bytes(); idx = self.size // tb
        if self.bpp == 8: b = bytes(px)
        else: b = bytes(px[i] | (px[i + 1] << 4) for i in range(0, 64, 2))
        end = self.base + self.size
        self.d[end:end] = b
        self.size += tb
        struct.pack_into('<I', self.d, self.s + 8 + 16, self.size)
        struct.pack_into('<I', self.d, self.s + 4, struct.unpack_from('<I', self.d, self.s + 4)[0] + tb)
        struct.pack_into('<I', self.d, 8, struct.unpack_from('<I', self.d, 8)[0] + tb)
        return idx

    def resize(self, ntiles):
        """Grow/shrink char data to ntiles (for re-tiled backgrounds)."""
        new = ntiles * self.tile_bytes(); old = self.size
        if new == old: return
        d = self.d
        d[self.base + old:self.base + old] = bytes(max(0, new - old)) if new > old else b''
        if new < old: del d[self.base + new:self.base + old]
        delta = new - old
        self.size = new
        struct.pack_into('<I', d, self.s + 8 + 16, new)            # data size
        struct.pack_into('<I', d, self.s + 4, struct.unpack_from('<I', d, self.s + 4)[0] + delta)
        struct.pack_into('<I', d, 8, struct.unpack_from('<I', d, 8)[0] + delta)
        if self.h != 0xFFFF:
            self.h = ntiles // max(1, self.w)
            struct.pack_into('<H', d, self.s + 8, self.h)


def put_tile(img, x0, y0, px, pal, palbase, hflip=False, vflip=False, transparent=True):
    for i, v in enumerate(px):
        if v == 0 and transparent: continue
        x, y = i % 8, i // 8
        if hflip: x = 7 - x
        if vflip: y = 7 - y
        X, Y = x0 + x, y0 + y
        if 0 <= X < img.width and 0 <= Y < img.height:
            c = pal[palbase + v] if palbase + v < len(pal) else (255, 0, 255)
            img.putpixel((X, Y), c + (255,))


# ------------------------------------------------------------------ screens
class Screen:
    def __init__(self, d):
        self.d = bytearray(d)
        s = self.s = section(d, b'NRCS')
        self.wpx, self.hpx, self.fmt, self.size = struct.unpack_from('<HHII', d, s + 8)
        self.base = s + 8 + 12
        self.map = list(struct.unpack_from('<%dH' % (self.size // 2), d, self.base))

    def save(self):
        struct.pack_into('<%dH' % len(self.map), self.d, self.base, *self.map)
        return bytes(self.d)


def render_screen(chars, scr, pal):
    tw = scr.wpx // 8
    img = Image.new('RGBA', (scr.wpx, scr.hpx), (0, 0, 0, 255))
    for i, e in enumerate(scr.map):
        t, hf, vf, p = e & 0x3FF, bool(e & 0x400), bool(e & 0x800), e >> 12
        palbase = 0 if chars.bpp == 8 else p * 16
        put_tile(img, (i % tw) * 8, (i // tw) * 8, chars.tile(t * chars.tile_bytes()), pal, palbase, hf, vf, transparent=False)
    return img


# ------------------------------------------------------------------ cells (sprites)
class Cells:
    def __init__(self, d):
        self.d = d
        s = section(d, b'KBEC')
        self.n, self.battr, coff, self.mode = struct.unpack_from('<HHII', d, s + 8)
        cbase = s + 8 + coff
        esz = 16 if self.battr == 1 else 8
        obase = cbase + esz * self.n
        self.cells = []
        for c in range(self.n):
            noam, attr, ooff = struct.unpack_from('<HHI', d, cbase + esz * c)
            oams = []
            for k in range(noam):
                a0, a1, a2 = struct.unpack_from('<HHH', d, obase + ooff + 6 * k)
                y = a0 & 0xFF; y = y - 256 if y >= 128 else y
                x = a1 & 0x1FF; x = x - 512 if x >= 256 else x
                shape, size = a0 >> 14, a1 >> 14
                w, h = SIZES.get(shape, SIZES[0])[size]
                rs = bool(a0 & 0x100)
                oams.append(dict(x=x, y=y, w=w, h=h, bpp8=bool(a0 & 0x2000), tile=a2 & 0x3FF, pal=a2 >> 12,
                                 hf=bool(a1 & 0x1000) and not rs, vf=bool(a1 & 0x2000) and not rs))
            self.cells.append(oams)

    def unit(self):
        return 32 << self.mode if self.mode < 4 else 32


def cell_bbox(oams):
    if not oams: return (0, 0, 1, 1)
    return (min(o['x'] for o in oams), min(o['y'] for o in oams),
            max(o['x'] + o['w'] for o in oams), max(o['y'] + o['h'] for o in oams))


def oam_tiles(o, chars, unit):
    """Yield (tile_x, tile_y, byte_offset) for each 8x8 tile of an OAM entry (1D mapping)."""
    tb = 64 if o['bpp8'] else 32
    start = o['tile'] * unit
    tw, th = o['w'] // 8, o['h'] // 8
    for ty in range(th):
        for tx in range(tw):
            yield tx, ty, start + (ty * tw + tx) * tb


def oam_pixels(o, chars, unit):
    """Return w*h palette indices of an OAM entry (handles tiled NCGR and linear NCBR data)."""
    w, h = o['w'], o['h']; start = o['tile'] * unit
    px = [0] * (w * h)
    if chars.tiled == 1:                          # NCBR: whole OBJ stored as a linear bitmap
        n = w * h
        if o['bpp8']:
            b = chars.d[chars.base + start: chars.base + start + n]
            for i, v in enumerate(b): px[i] = v
        else:
            b = chars.d[chars.base + start: chars.base + start + n // 2]
            for i, v in enumerate(b): px[2 * i] = v & 15; px[2 * i + 1] = v >> 4
    else:
        for tx, ty, off in oam_tiles(o, chars, unit):
            t = tile_at(chars, off, o['bpp8'])
            for i, v in enumerate(t): px[(ty * 8 + i // 8) * w + tx * 8 + i % 8] = v
    return px


def write_oam_pixels(o, chars, unit, px):
    w, h = o['w'], o['h']; start = o['tile'] * unit
    if chars.tiled == 1:
        b = bytes(px) if o['bpp8'] else bytes(px[i] | (px[i + 1] << 4) for i in range(0, w * h, 2))
        chars.d[chars.base + start: chars.base + start + len(b)] = b
    else:
        for tx, ty, off in oam_tiles(o, chars, unit):
            t = [px[(ty * 8 + i // 8) * w + tx * 8 + i % 8] for i in range(64)]
            set_tile_at(chars, off, o['bpp8'], t)


def render_cell(oams, chars, pal, unit, opaque=False):
    x0, y0, x1, y1 = cell_bbox(oams)
    img = Image.new('RGBA', (x1 - x0, y1 - y0), (0, 0, 0, 0))
    for o in reversed(oams):          # first OAM is on top
        w, h = o['w'], o['h']
        px = oam_pixels(o, chars, unit)
        palbase = 0 if o['bpp8'] else o['pal'] * 16
        for i, v in enumerate(px):
            if v == 0 and not opaque: continue
            x, y = i % w, i // w
            if o['hf']: x = w - 1 - x
            if o['vf']: y = h - 1 - y
            c = pal[palbase + v] if palbase + v < len(pal) else (255, 0, 255)
            img.putpixel((o['x'] - x0 + x, o['y'] - y0 + y), c + (255,))
    return img


def tile_at(chars, off, bpp8):
    b = chars.d[chars.base + off: chars.base + off + (64 if bpp8 else 32)]
    if bpp8: return list(b) + [0] * (64 - len(b))
    out = []
    for x in b: out += [x & 15, x >> 4]
    return out + [0] * (64 - len(out))


def set_tile_at(chars, off, bpp8, px):
    b = bytes(px) if bpp8 else bytes(px[i] | (px[i + 1] << 4) for i in range(0, 64, 2))
    chars.d[chars.base + off: chars.base + off + len(b)] = b
