import struct, sys, glob, os
def parse(d):
    cnt = struct.unpack_from('<I', d, 0)[0]
    p = 4; chunks=[]
    for c in range(cnt):
        size = struct.unpack_from('<I', d, p)[0]
        end = p+size
        csize = struct.unpack_from('<I', d, p+4)[0]
        code = d[p+4:p+4+csize]
        t = p+4+csize
        tsize, n = struct.unpack_from('<IH', d, t)
        assert t+tsize == end, (c, t, tsize, end)
        q = t+6; strs=[]
        for k in range(n):
            L = d[q]; strs.append(d[q+1:q+1+L]); q += 1+L
        assert q == end
        chunks.append((code, strs)); p = end
    assert p == len(d), (p, len(d))
    return chunks
def build(chunks):
    out = struct.pack('<I', len(chunks))
    for code, strs in chunks:
        body = b''.join(bytes([len(s)])+s for s in strs)
        tb = struct.pack('<IH', 6+len(body), len(strs)) + body
        out += struct.pack("<I", 4+len(code)+len(tb)) + code + tb
    return out
if __name__=='__main__':
    tot=0; chars=0
    for f in sorted(glob.glob(sys.argv[1]+'/*.dat')):
        d=open(f,'rb').read()
        ch=parse(d)
        assert build(ch)==d
        n=sum(len(s) for c,s in ch); tot+=n
        chars+=sum(len(x.decode('cp932')) for c,s in ch for x in s)
        print('==',os.path.basename(f), len(ch), n)
        for ci,(c,s) in enumerate(ch[:int(sys.argv[2])]):
            for k,x in enumerate(s): print(ci,k, x.decode('cp932'))
    print('total',tot,'chars',chars)
