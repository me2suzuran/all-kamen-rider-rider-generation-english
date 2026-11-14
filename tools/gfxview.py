"""Measuring helpers for image translation.

  python tools/gfxview.py list <Folder>                 # assets in a folder (screens + every sprite cell, with sizes)
  python tools/gfxview.py grid <asset> <out.png> [x0 y0 x1 y1] [scale]   # zoomed render with 8px grid + coords
  python tools/gfxview.py rows <asset> x0 x1 y0 y1      # ASCII map per row: '#' bright, '+' mid, '.' dark
  python tools/gfxview.py colors <asset> x0 y0 x1 y1    # most common colours in a rect
  python tools/gfxview.py sheet <pattern> <out.png>     # side-by-side previews (tl/gfx/preview/*pattern*)
Asset ids: "Folder/name" (NSCR screen) or "Folder/name#N" (sprite cell N). Folder is relative to _Data/.
"""
import glob, os, sys
from collections import Counter
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import ndspy.rom
from PIL import Image, ImageDraw
import gfxtl
from gfx import Cells
from krtl import SRC_ROM

_rom = None
def rom():
    global _rom
    if _rom is None: _rom = ndspy.rom.NintendoDSRom.fromFile(SRC_ROM)
    return _rom


def render(aid):
    return gfxtl.Asset(rom(), aid).render()


def main():
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == 'list':
        f = rom().filenames
        for part in ('_Data/' + args[0]).split('/'): f = dict(f.folders)[part]
        names = sorted(f.files)
        for n in names:
            base, ext = os.path.splitext(n)
            if ext == '.NSCR': print('%s/%s' % (args[0], base), render('%s/%s' % (args[0], base)).size)
            if ext == '.NCER':
                if not any(m in names for m in (base + '.NCGR', base + '.NCBR')): continue
                c = Cells(rom().getFileByName('_Data/%s/%s' % (args[0], n)))
                for i in range(c.n):
                    aid = '%s/%s#%d' % (args[0], base, i)
                    try: print(aid, render(aid).size)
                    except Exception as e: print(aid, 'ERR', e)
    elif cmd == 'grid':
        im = render(args[0]); out = args[1]
        ox = oy = 0
        if len(args) >= 6:
            x0, y0, x1, y1 = map(int, args[2:6]); im = im.crop((x0, y0, x1, y1)); ox, oy = x0, y0
        sc = int(args[6]) if len(args) > 6 else 3
        bg = Image.new('RGBA', im.size, (255, 0, 255, 255)); bg.alpha_composite(im)
        im = bg.resize((bg.width * sc, bg.height * sc), Image.NEAREST); d = ImageDraw.Draw(im)
        for x in range(0, im.width, sc * 8):
            d.line([(x, 0), (x, im.height)], fill=(255, 0, 0, 90)); d.text((x + 1, 0), str(ox + x // sc), fill=(255, 255, 0, 255))
        for y in range(0, im.height, sc * 8):
            d.line([(0, y), (im.width, y)], fill=(255, 0, 0, 90)); d.text((0, y + 1), str(oy + y // sc), fill=(0, 255, 255, 255))
        im.save(out); print(out, im.size)
    elif cmd == 'rows':
        im = render(args[0]).convert('RGBA'); x0, x1, y0, y1 = map(int, args[1:5])
        for y in range(y0, y1):
            row = [im.getpixel((x, y)) for x in range(x0, x1)]
            s = ''.join(' ' if p[3] == 0 else ('#' if sum(p[:3]) > 450 else ('+' if sum(p[:3]) > 250 else '.')) for p in row)
            print('%4d %s' % (y, s))
    elif cmd == 'colors':
        im = render(args[0]).convert('RGBA'); x0, y0, x1, y1 = map(int, args[1:5])
        print(Counter(im.getpixel((x, y)) for x in range(x0, x1) for y in range(y0, y1)).most_common(10))
    elif cmd == 'sheet':
        files = sorted(glob.glob(os.path.join(gfxtl.GFX, 'preview', '*%s*.png' % args[0])))
        ims = [Image.open(f) for f in files]
        W = max(i.width for i in ims); H = sum(i.height + 2 for i in ims)
        s = Image.new('RGBA', (W, H), (40, 40, 40, 255)); y = 0
        for i in ims: s.paste(i, (0, y)); y += i.height + 2
        if s.height > 3000: print('WARNING: sheet is tall (%d px); use a narrower pattern' % s.height)
        s.save(args[1]); print(args[1], s.size, len(ims), 'images')


if __name__ == '__main__':
    main()
