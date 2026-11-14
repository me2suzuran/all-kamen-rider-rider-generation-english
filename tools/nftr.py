import struct, sys
def parse(path):
    d = bytes(path) if isinstance(path,(bytes,bytearray)) else open(path,'rb').read()
    assert d[:4]==b'RTFN', d[:4]
    hs = struct.unpack_from('<H', d, 0xC)[0]
    off = hs
    info = {}
    cmaps = []; cwdh=None; cglp=None; finf=None
    while off < len(d):
        magic = d[off:off+4]; size = struct.unpack_from('<I', d, off+4)[0]
        if magic==b'FNIF': finf=off
        elif magic==b'PLGC': cglp=off
        elif magic==b'HDWC': cwdh=off
        elif magic==b'PAMC': cmaps.append(off)
        if size==0: break
        off += size
    # FINF
    f = finf+8
    ftype, lineh, alt, = d[f], d[f+1], struct.unpack_from('<H', d, f+2)[0]
    dw = d[f+4:f+7]
    enc = d[f+7]
    pglp, pcwdh, pcmap = struct.unpack_from('<III', d, f+8)
    g = cglp+8
    cw, ch, tsz, bl, mw, bpp, flags = struct.unpack_from('<BBHBBBB', d, g)
    return dict(d=d, lineh=lineh, alt=alt, defwidth=tuple(dw), enc=enc, pglp=pglp, pcwdh=pcwdh, pcmap=pcmap,
                cellw=cw, cellh=ch, tilesize=tsz, baseline=bl, maxw=mw, bpp=bpp, cglp=cglp, cwdh=cwdh, cmaps=cmaps)
def charmap(info):
    d=info['d']; m={}
    for c in info['cmaps']:
        b=c+8
        first,last,typ = struct.unpack_from('<HHH', d, b)
        if typ==0:
            idx = struct.unpack_from("<H", d, b+12)[0]
            for i in range(first,last+1): m[i]=idx+i-first
        elif typ==1:
            for i in range(first,last+1):
                v=struct.unpack_from("<H", d, b+12+2*(i-first))[0]
                if v!=0xFFFF: m[i]=v
        elif typ==2:
            n=struct.unpack_from("<H", d, b+12)[0]
            for k in range(n):
                cc,gi=struct.unpack_from("<HH", d, b+14+4*k); m[cc]=gi
    return m
def widths(info):
    d=info['d']; b=info['cwdh']+8
    fi, li = struct.unpack_from('<HH', d, b)
    w={}
    for i in range(fi, li+1):
        w[i]=tuple(d[b+8+3*(i-fi):b+11+3*(i-fi)])
    return w
if __name__=='__main__':
    for p in sys.argv[1:]:
        i=parse(p); m=charmap(i); w=widths(i)
        print(p.split('/')[-1], {k:v for k,v in i.items() if k not in('d',)} , 'nchars',len(m))
        enc=i['enc']
        asc=[c for c in m if c<0x80]
        print(' ascii mapped:', len(asc), ''.join(chr(c) for c in sorted(asc)))
        for c in [0x41,0x61,0x8260,0x8281,0xFF21,0xFF41,0x3042]:
            if c in m: print('  %04x glyph %d width %s'%(c,m[c],w.get(m[c])))
