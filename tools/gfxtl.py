"""Image text translation: render game graphics, apply edit specs, re-import into the ROM.

Asset ids:  "Folder/name"      -> background screen  (name.NSCR + name.NCGR + palette)
            "Folder/name#N"    -> sprite cell N      (name.NCER + name.NCGR/NCBR + palette)
Specs live in tl/gfx/*.json as {asset_id: [op, ...]}. Ops (rects are [x0, y0, x1, y1], end exclusive):
  {"op": "fill", "rect": R, "mode": "h"}            each row: interpolate between pixels left/right of R
  {"op": "fill", "rect": R, "mode": "v"}            each column: interpolate between pixels above/below R
  {"op": "fill", "rect": R, "color": [r, g, b]}     flat colour
  {"op": "copy", "src": R, "dst": [x, y]}           copy a block (e.g. clean texture) from the original
  {"op": "text", "text": "A\\nB", "rect": R, "color": C, "outline": C|null, "font": "12"|"10",
   "bold": true, "align": "center"|"left"|"right", "lh": 12, "spacing": 0, "shadow": C|null}
Usage:
  python tools/gfxtl.py preview [filter]   # writes tl/gfx/preview/*.png (original | translated, 2x)
  python tools/gfxtl.py export <asset>     # writes tl/gfx/orig/<asset>.png for measuring
"""
import glob, json, os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from PIL import Image
import numpy as np
from gfx import Chars, Screen, Cells, nclr, render_screen, render_cell, cell_bbox, oam_pixels, write_oam_pixels
from nftr import parse as nftr_parse, charmap as nftr_charmap

ROOT = os.path.dirname(HERE)
GFX = os.path.join(ROOT, 'tl', 'gfx')
D = '_Data/'


# ------------------------------------------------------------------ pack files (CharaSelect)
_PACKS = {}
def pack_members(rom, path):
    """Packs: u32 n, u32 size[n], u32 offset[n], data. Cached per ROM object; edits go to the list."""
    key = (id(rom), path)
    if key not in _PACKS:
        d = rom.getFileByName(path)
        n = struct.unpack_from('<I', d, 0)[0]
        sizes = struct.unpack_from('<%dI' % n, d, 4); offs = struct.unpack_from('<%dI' % n, d, 4 + 4 * n)
        _PACKS[key] = [bytes(d[o:o + s]) for o, s in zip(offs, sizes)]
    return _PACKS[key]


def pack_save(rom, path):
    mem = _PACKS[(id(rom), path)]; n = len(mem)
    p = 4 + 8 * n; offs = []; body = b''
    for m in mem:
        offs.append(p + len(body)); body += m
        body += bytes((-len(body)) % 4)
    rom.setFileByName(path, struct.pack('<I', n) + struct.pack('<%dI' % n, *[len(m) for m in mem])
                      + struct.pack('<%dI' % n, *offs) + body)


# ------------------------------------------------------------------ asset loading
class Asset:
    def __init__(self, rom, aid):
        self.rom, self.aid = rom, aid
        name, _, cell = aid.partition('#')
        self.cell = int(cell) if cell else None
        self.files = rom.filenames
        if name.startswith('pack:'):
            # pack:<path under _Data>:<NCGR idx>:<NCLR idx>:<NSCR or NCER idx>
            _, path, g, p, x = name.split(':')
            self.pack = D + path
            mem = pack_members(rom, self.pack)
            self.charf, palf = int(g), int(p)
            self.chars = Chars(mem[self.charf]); self.pal = nclr(mem[palf])
            if self.cell is None: self.scrf = int(x); self.scr = Screen(mem[self.scrf])
            else:
                self.cellf = int(x); self.cells = Cells(mem[self.cellf]); self.oams = self.cells.cells[self.cell]
            return
        self.pack = None
        self.folder, self.name = name.rsplit('/', 1)
        if self.cell is None:
            self.charf = self._p('.NCGR'); self.scrf = self._p('.NSCR')
            self.chars = Chars(self._get(self.charf)); self.scr = Screen(self._get(self.scrf))
        else:
            self.cellf = self._p('.NCER')
            self.charf = self._p('.NCGR') if self._exists('.NCGR') else self._p('.NCBR')
            self.chars = Chars(self._get(self.charf)); self.cells = Cells(self._get(self.cellf))
            self.oams = self.cells.cells[self.cell]
        self.pal = nclr(self._get(self._palette()))

    def _p(self, ext): return D + self.folder + '/' + self.name + ext
    def _exists(self, ext): return self.files.idOf(self._p(ext)) is not None
    def _get(self, p): return self.rom.getFileByName(p)

    def _put(self, key, data):
        if self.pack:
            pack_members(self.rom, self.pack)[key] = bytes(data); pack_save(self.rom, self.pack)
        else:
            self.rom.setFileByName(key, data)

    def _palette(self):
        if self._exists('.NCLR'): return self._p('.NCLR')
        folder = self.files[D + self.folder] if False else None
        pre = self.name.split('_')[0]
        cands = sorted(n for n in self._listdir() if n.endswith('.NCLR'))
        for c in cands:
            if c.startswith(pre): return D + self.folder + '/' + c
        return D + self.folder + '/' + cands[0]

    def _listdir(self):
        f = self.files
        for part in (D + self.folder).strip('/').split('/'):
            f = dict(f.folders)[part]
        return list(f.files)

    def render(self):
        if self.cell is None: return render_screen(self.chars, self.scr, self.pal)
        return render_cell(self.oams, self.chars, self.pal, self.cells.unit())

    # -------------------------------------------------------------- import
    def nearest(self, rgb, lo, hi):
        best, bi = 1 << 30, lo
        for i in range(lo, min(hi, len(self.pal))):
            p = self.pal[i]; dd = (p[0] - rgb[0]) ** 2 + (p[1] - rgb[1]) ** 2 + (p[2] - rgb[2]) ** 2
            if dd < best: best, bi = dd, i
        return bi

    def store(self, new):
        """Write changed pixels of `new` (RGBA, same size as render()) back into char data."""
        old = np.array(self.render()); new = np.array(new.convert('RGBA'))
        changed = np.any(old != new, axis=2)
        if not changed.any(): return 0
        cache = {}
        def idx(rgba, lo, hi):
            k = (tuple(rgba[:3]), lo, hi)
            if k not in cache: cache[k] = self.nearest(tuple(int(v) for v in rgba[:3]), lo, hi)
            return cache[k]
        n = 0
        if self.cell is None:
            tw = self.scr.wpx // 8; tb = self.chars.tile_bytes()
            refs = {}
            for i, e in enumerate(self.scr.map): refs.setdefault(e & 0x3FF, []).append(i)
            newpx = {}
            for i, e in enumerate(self.scr.map):
                X, Y = (i % tw) * 8, (i // tw) * 8
                if not changed[Y:Y + 8, X:X + 8].any(): continue
                t, hf, vf, p = e & 0x3FF, e & 0x400, e & 0x800, e >> 12
                px = self.chars.tile(t * tb)
                lo, hi = (1, 256) if self.chars.bpp == 8 else (p * 16 + 1, p * 16 + 16)
                for k in range(64):
                    x, y = k % 8, k // 8
                    sx, sy = (7 - x if hf else x), (7 - y if vf else y)
                    if changed[Y + sy, X + sx]:
                        v = idx(new[Y + sy, X + sx], lo, hi)
                        px[k] = v if self.chars.bpp == 8 else v - p * 16
                newpx[i] = px
            appended = 0
            for t in sorted({self.scr.map[i] & 0x3FF for i in newpx}):
                mine = [i for i in refs[t] if i in newpx]
                same = all(newpx[i] == newpx[mine[0]] for i in mine)
                if len(mine) == len(refs[t]) and same:      # tile only used where we edit: overwrite
                    self.chars.set_tile(t * tb, newpx[mine[0]]); n += 1
                    continue
                made = {}
                for i in mine:                              # shared tile: give edited spots their own tile
                    key = bytes(newpx[i])
                    if key not in made:
                        made[key] = self.chars.append_tile(newpx[i]); appended += 1
                    nt = made[key]
                    if nt > 0x3FF: raise SystemExit('%s: out of BG tile indices' % self.aid)
                    self.scr.map[i] = (self.scr.map[i] & ~0x3FF) | nt; n += 1
            if appended:
                print('NOTE %s: %d new tiles appended (shared tiles), now %d' % (self.aid, appended, self.chars.ntiles()))
                self._put(self.scrf, self.scr.save())
            self._put(self.charf, bytes(self.chars.d))
        else:
            x0, y0, _, _ = cell_bbox(self.oams)
            owner = {}
            for oi, o in enumerate(self.oams):          # topmost OAM that covers each pixel
                for yy in range(o['h']):
                    for xx in range(o['w']):
                        owner.setdefault((o['x'] - x0 + xx, o['y'] - y0 + yy), oi)
            unit = self.cells.unit()
            for oi, o in enumerate(self.oams):
                w, h = o['w'], o['h']; px = oam_pixels(o, self.chars, unit); dirty = False
                lo, hi = (1, 256) if o['bpp8'] else (o['pal'] * 16 + 1, o['pal'] * 16 + 16)
                for k in range(w * h):
                    x, y = k % w, k // w
                    dx, dy = (w - 1 - x if o['hf'] else x), (h - 1 - y if o['vf'] else y)
                    X, Y = o['x'] - x0 + dx, o['y'] - y0 + dy
                    if not changed[Y, X] or owner.get((X, Y)) != oi: continue
                    if new[Y, X][3] < 128: v = 0
                    else:
                        v = idx(new[Y, X], lo, hi)
                        if not o['bpp8']: v -= o['pal'] * 16
                    px[k] = v; dirty = True
                if dirty: write_oam_pixels(o, self.chars, unit, px); n += 1
            self._put(self.charf, bytes(self.chars.d))
        return n


# ------------------------------------------------------------------ text rendering
_FONTS = {}
def font(rom, name):
    if name not in _FONTS:
        info = nftr_parse(rom.getFileByName(D + 'font/Font%s.NFTR' % {'12': '1212', '10': '1010'}[name]))
        _FONTS[name] = (info, nftr_charmap(info))
    return _FONTS[name]


def glyph(rom, fname, ch):
    info, cmap = font(rom, fname); d = info['d']
    code = ord(ch) if ord(ch) < 0x80 else int.from_bytes(ch.encode('cp932'), 'big')
    g = cmap[code]
    cw, chh, ts, bpp = info['cellw'], info['cellh'], info['tilesize'], info['bpp']
    off = info['cglp'] + 16 + g * ts
    bits = ''.join(f'{b:08b}' for b in d[off:off + ts])
    wb = info['cwdh'] + 16 + 3 * g
    left, gw, adv = d[wb], d[wb + 1], d[wb + 2]
    rows = [[bits[(y * cw + x) * bpp] == '1' for x in range(cw)] for y in range(chh)]
    # crop to actual ink for proportional layout
    xs = [x for r in rows for x, v in enumerate(r) if v]
    if not xs: return [], 0 if ch != ' ' else (3 if fname == '10' else 4)
    x0, x1 = min(xs), max(xs)
    pts = [(x - x0, y) for y, r in enumerate(rows) for x, v in enumerate(r) if v]
    return pts, x1 - x0 + 1


def layout_line(rom, text, fname, bold, spacing):
    pts = []; x = 0
    for ch in text:
        g, w = glyph(rom, fname, ch)
        gs = set(g)
        for (gx, gy) in g:
            pts.append((x + gx, gy))
            # embolden to the right, but never close a 1px gap (keeps m, w, M readable)
            if bold and (gx + 1, gy) not in gs and (gx + 2, gy) not in gs: pts.append((x + gx + 1, gy))
        x += w + (1 if bold else 0) + 1 + spacing
    return pts, max(0, x - 1 - spacing)


def draw_text(img, rom, op):
    x0, y0, x1, y1 = op['rect']
    fname = op.get('font', '12'); bold = op.get('bold', True)
    lines = op['text'].split('\n')
    lh = op.get('lh', 12 if fname == '12' else 10)
    spacing = op.get('spacing', 0)
    info, _ = font(rom, fname)
    glyph_h = info['cellh']
    laid = [layout_line(rom, t, fname, bold, spacing) for t in lines]
    # squeeze letter spacing if a line is too wide
    warn = []
    for i, t in enumerate(lines):
        sp = spacing
        while laid[i][1] > (x1 - x0 - 2) and sp > -1:
            sp -= 1; laid[i] = layout_line(rom, t, fname, bold, sp)
        if laid[i][1] > (x1 - x0 - 2): warn.append('text too wide: %r (%d > %d)' % (t, laid[i][1], x1 - x0 - 2))
    total_h = lh * (len(lines) - 1) + glyph_h
    ty = y0 + (y1 - y0 - total_h) // 2 + op.get('dy', 0)
    ink = set()
    for i, (pts, w) in enumerate(laid):
        al = op.get('align', 'center')
        tx = x0 + 1 + ((x1 - x0 - 2 - w) // 2 if al == 'center' else (x1 - x0 - 2 - w if al == 'right' else 0)) + op.get('dx', 0)
        for (px, py) in pts: ink.add((tx + px, ty + i * lh + py))
    P = img.load()
    def put(x, y, c):
        if 0 <= x < img.width and 0 <= y < img.height: P[x, y] = tuple(c) + (255,)
    if op.get('shadow'):
        for (x, y) in ink: put(x + 1, y + 1, op['shadow'])
    if op.get('outline'):
        for (x, y) in ink:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if (x + dx, y + dy) not in ink: put(x + dx, y + dy, op['outline'])
    for (x, y) in ink: put(x, y, op['color'])
    return warn


def do_fill(img, orig, op):
    x0, y0, x1, y1 = op['rect']
    a = np.array(img).astype(float); o = np.array(orig).astype(float)
    if op.get('mode') == 'clear':           # make transparent (sprites only)
        a[y0:y1, x0:x1] = 0
    elif 'color' in op:
        a[y0:y1, x0:x1, :3] = op['color']; a[y0:y1, x0:x1, 3] = 255
    elif op.get('mode') == 'tile':       # repeat a clean block: rows from_y.. (period_y), cols from_x.. (period_x)
        fy, py = op.get('from_y'), op.get('period_y', 1)
        fx, px = op.get('from_x'), op.get('period_x', 1)
        for y in range(y0, y1):
            sy = fy + (y - fy) % py if fy is not None else y
            for x in range(x0, x1):
                sx = fx + (x - fx) % px if fx is not None else x
                a[y, x] = o[sy, sx]
    elif op.get('mode') == 'inpaint':
        # mask = text pixels inside rect: luma >= min_luma, or luma <= max_luma, or near one of `colors`
        sub = o[y0:y1, x0:x1, :3]; luma = sub.mean(axis=2)
        mask = np.zeros(luma.shape, bool)
        if 'min_luma' in op: mask |= luma >= op['min_luma']
        if 'max_luma' in op: mask |= luma <= op['max_luma']
        for c in op.get('colors', []):
            mask |= np.abs(sub - np.array(c)).sum(axis=2) <= op.get('tol', 60)
        for _ in range(op.get('grow', 1)):                 # include anti-alias / outline ring
            g = mask.copy(); g[1:] |= mask[:-1]; g[:-1] |= mask[1:]; g[:, 1:] |= mask[:, :-1]; g[:, :-1] |= mask[:, 1:]
            mask = g
        val = a[y0:y1, x0:x1].copy()
        while mask.any():
            acc = np.zeros(val.shape); cnt = np.zeros(mask.shape)
            ok = ~mask
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                sh_ok = np.zeros_like(ok); sh_v = np.zeros_like(val)
                ys = slice(max(dy, 0), mask.shape[0] + min(dy, 0)); yd = slice(max(-dy, 0), mask.shape[0] + min(-dy, 0))
                xs = slice(max(dx, 0), mask.shape[1] + min(dx, 0)); xd = slice(max(-dx, 0), mask.shape[1] + min(-dx, 0))
                sh_ok[yd, xd] = ok[ys, xs]; sh_v[yd, xd] = val[ys, xs]
                acc += sh_v * sh_ok[..., None]; cnt += sh_ok
            fill = mask & (cnt > 0)
            if not fill.any(): break
            val[fill] = acc[fill] / cnt[fill][:, None]
            mask &= ~fill
        a[y0:y1, x0:x1] = val
    elif op.get('mode') == 'row':        # each row -> its most common colour (textured flat boxes)
        for y in range(y0, y1):
            vals, cnt = np.unique(o[y, x0:x1].reshape(-1, 4), axis=0, return_counts=True)
            a[y, x0:x1] = vals[cnt.argmax()]
    elif op.get('mode', 'h') == 'h':
        for y in range(y0, y1):
            L = o[y, max(x0 - 1, 0)]; R = o[y, min(x1, o.shape[1] - 1)]
            for x in range(x0, x1):
                t = (x - x0 + 1) / (x1 - x0 + 1); a[y, x] = L * (1 - t) + R * t
    else:
        for x in range(x0, x1):
            T = o[max(y0 - 1, 0), x]; B = o[min(y1, o.shape[0] - 1), x]
            for y in range(y0, y1):
                t = (y - y0 + 1) / (y1 - y0 + 1); a[y, x] = T * (1 - t) + B * t
    return Image.fromarray(a.round().astype(np.uint8), 'RGBA').copy()


def apply_ops(rom, orig, ops):
    img = orig.copy(); warns = []
    for op in ops:
        k = op['op']
        if k == 'fill': img = do_fill(img, orig, op)
        elif k == 'copy':
            sx0, sy0, sx1, sy1 = op['src']; img.paste(orig.crop((sx0, sy0, sx1, sy1)), tuple(op['dst']))
        elif k == 'text': warns += draw_text(img, rom, op)
        else: raise ValueError(k)
    return img, warns


def load_specs(flt=None):
    specs = {}
    for f in sorted(glob.glob(os.path.join(GFX, '*.json'))):
        for aid, ops in json.load(open(f, encoding='utf-8')).items():
            if aid.startswith('_'): continue
            if flt and flt not in aid: continue
            specs[aid] = ops
    return specs


def apply_all(rom, flt=None, preview=False):
    specs = load_specs(flt); total = 0
    out = os.path.join(GFX, 'preview')
    if preview: os.makedirs(out, exist_ok=True)
    for aid, ops in specs.items():
        a = Asset(rom, aid); orig = a.render()
        new, warns = apply_ops(rom, orig, ops)
        for w in warns: print('WARN', aid, w)
        if preview:
            W, H = orig.size; s = Image.new('RGBA', (W * 2 + 4, H), (255, 0, 255, 255))
            s.paste(orig, (0, 0)); s.paste(new, (W + 4, 0))
            s.resize((s.width * 2, s.height * 2), Image.NEAREST).save(os.path.join(out, aid.replace('/', '__').replace('#', '_').replace(':', '_') + '.png'))
        else:
            total += a.store(new)
    return len(specs), total


if __name__ == '__main__':
    import ndspy.rom
    from krtl import SRC_ROM
    rom = ndspy.rom.NintendoDSRom.fromFile(SRC_ROM)
    cmd = sys.argv[1]
    if cmd == 'preview':
        n, _ = apply_all(rom, sys.argv[2] if len(sys.argv) > 2 else None, preview=True); print('previewed', n)
    elif cmd == 'export':
        a = Asset(rom, sys.argv[2]); os.makedirs(os.path.join(GFX, 'orig'), exist_ok=True)
        p = os.path.join(GFX, 'orig', sys.argv[2].replace('/', '__').replace('#', '_') + '.png')
        a.render().save(p); print(p, a.render().size)
