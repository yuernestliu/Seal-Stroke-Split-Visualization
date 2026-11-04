"""Scan every glyph's strokes.png and classify as 粗笔画彩图 vs 细骨架 vs 缺图."""
import struct, zlib
from pathlib import Path
from collections import Counter


def read_png_dims(path):
    data = path.read_bytes()
    pos = 8
    while pos < len(data):
        length = struct.unpack(">I", data[pos:pos+4])[0]
        ctype = data[pos+4:pos+8]
        chunk = data[pos+8:pos+8+length]
        if ctype == b"IHDR":
            return struct.unpack(">II", chunk[:8])
        pos += 8 + length + 4
    return 0, 0


def read_png_full(path):
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
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


def classify(path):
    """Return (size, colored_pixels, total_pixels, ratio, label)."""
    if not path.exists():
        return 0, 0, 0, 0.0, "MISSING"
    info = read_png_full(path)
    if info is None:
        return path.stat().st_size, 0, 0, 0.0, "NOT_PNG"
    w, h, bd, ct, raw = info
    if ct != 2:
        return path.stat().st_size, 0, w * h, 0.0, f"NOT_RGB(ct={ct})"
    bpp = 3
    px = unfilter(raw, w, h, bpp)
    total = w * h
    colored = 0
    for i in range(total):
        r, g, b = px[i * 3], px[i * 3 + 1], px[i * 3 + 2]
        # 非黑色像素
        if r > 30 or g > 30 or b > 30:
            colored += 1
    ratio = colored / total if total else 0
    # binary.png 的笔画像素大约占 5%~15%，strokes.png 彩色像素应该接近
    if ratio < 0.02:
        label = "骨架"
    elif ratio < 0.05:
        label = "细"
    elif ratio < 0.12:
        label = "粗"
    else:
        label = "很粗"
    return path.stat().st_size, colored, total, ratio, label


def main():
    base = Path("public/assets/experiments/v1")
    rows = []
    for f in sorted(base.iterdir()):
        if not f.is_dir():
            continue
        strokes = f / "strokes.png"
        size, colored, total, ratio, label = classify(strokes)
        rows.append((f.name, size, colored, total, ratio, label))
    print(f"{'字形':40s} {'字节':>6s} {'彩像素':>7s} {'/':1s} {'':<5s} {'占比':>6s}  类别")
    print("-" * 80)
    buckets = Counter(r[5] for r in rows)
    for name, size, colored, total, ratio, label in rows:
        marker = "  <-- 骨架" if label in ("骨架", "细", "MISSING") else ""
        print(f"{name:40s} {size:>6d} {colored:>7d}/{total:<5d} {ratio:>5.1%}  {label}{marker}")
    print()
    print("分类统计:", dict(buckets))


if __name__ == "__main__":
    main()
