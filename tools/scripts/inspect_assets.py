"""Quick PNG inspection: dump dimensions, color count, top colors for each asset."""
import struct, zlib
from pathlib import Path
from collections import Counter


def read_png(path):
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", f"not png: {path}"
    pos = 8
    width = height = 0
    bit_depth = color_type = 0
    idat = b""
    while pos < len(data):
        length = struct.unpack(">I", data[pos:pos+4])[0]
        ctype = data[pos+4:pos+8]
        chunk = data[pos+8:pos+8+length]
        if ctype == b"IHDR":
            width, height, bit_depth, color_type = struct.unpack(">IIBB", chunk[:10])
        elif ctype == b"IDAT":
            idat += chunk
        pos += 8 + length + 4
    return width, height, bit_depth, color_type, zlib.decompress(idat)


def unfilter(raw, width, height, bpp):
    bpr = width * bpp
    out = bytearray()
    prev = bytearray(bpr)
    for r in range(height):
        ftype = raw[r * bpr]
        line = bytearray(raw[r * bpr + 1: (r + 1) * bpr + 1])
        if ftype == 0:
            pass
        elif ftype == 1:
            for i in range(bpp, bpr):
                line[i] = (line[i] + line[i - bpp]) & 0xff
        elif ftype == 2:
            for i in range(bpr):
                line[i] = (line[i] + prev[i]) & 0xff
        elif ftype == 3:
            for i in range(bpr):
                a = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + (a + prev[i]) // 2) & 0xff
        elif ftype == 4:
            for i in range(bpr):
                a = line[i - bpp] if i >= bpp else 0
                b = prev[i]
                c = prev[i - bpp] if i >= bpp else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                if pa <= pb and pa <= pc:
                    pr = a
                elif pb <= pc:
                    pr = b
                else:
                    pr = c
                line[i] = (line[i] + pr) & 0xff
        out += line
        prev = line
    return out


def summarize(path):
    w, h, bd, ct, raw = read_png(path)
    bpp = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ct]
    px = unfilter(raw, w, h, bpp)
    total = w * h
    if ct == 2:
        colors = Counter()
        for i in range(total):
            r, g, b = px[i * 3], px[i * 3 + 1], px[i * 3 + 2]
            colors[(r, g, b)] += 1
    elif ct == 0:
        colors = Counter(px)
    elif ct == 6:
        colors = Counter()
        for i in range(total):
            colors[(px[i * 4], px[i * 4 + 1], px[i * 4 + 2])] += 1
    else:
        colors = Counter(px)
    print(f"{path.name:35s} {w}x{h} bit={bd} color={ct} unique={len(colors):4d}")
    for c, n in colors.most_common(8):
        print(f"    {c}: {n}")


if __name__ == "__main__":
    base = Path("public/assets/experiments/v1/10202_尚_Z_說文‧八部")
    for name in ["original.png", "binary.png", "skeleton.png", "overlay.png",
                 "overlap.png", "strokes.png", "strokes_gallery.png"]:
        p = base / name
        if p.exists():
            summarize(p)
    print()
    print("--- stroke_01..06.png ---")
    for p in sorted((base / "strokes_individual").glob("*.png")):
        summarize(p)
