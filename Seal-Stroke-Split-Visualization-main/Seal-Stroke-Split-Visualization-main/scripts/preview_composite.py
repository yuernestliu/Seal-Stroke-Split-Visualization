"""生成 3 个示例字的笔画拆解彩图（仅作预览）。"""
import zlib, struct, os

def read_png(path):
    with open(path, 'rb') as f:
        data = f.read()
    pos = 8
    width = height = bit_depth = color_type = None
    idat = b''
    while pos < len(data):
        length = struct.unpack('>I', data[pos:pos+4])[0]
        ctype = data[pos+4:pos+8].decode('ascii', errors='ignore')
        cdata = data[pos+8:pos+8+length]
        if ctype == 'IHDR':
            width = struct.unpack('>I', cdata[0:4])[0]
            height = struct.unpack('>I', cdata[4:8])[0]
            bit_depth = cdata[8]
            color_type = cdata[9]
        elif ctype == 'IDAT':
            idat += cdata
        pos += 8 + length + 4
    raw = zlib.decompress(idat)
    bpp = {0:1,2:3,3:1,4:2,6:4}[color_type]
    row_len = width * bpp + 1
    pixels = []
    prev = bytes(width * bpp)
    for y in range(height):
        row_start = y * row_len
        filt = raw[row_start]
        row = bytearray(raw[row_start+1:row_start+row_len])
        if filt == 0:
            pass
        elif filt == 1:
            for i in range(bpp, len(row)):
                row[i] = (row[i] + row[i-bpp]) & 0xFF
        elif filt == 2:
            for i in range(len(row)):
                row[i] = (row[i] + prev[i]) & 0xFF
        elif filt == 3:
            for i in range(len(row)):
                left = row[i-bpp] if i >= bpp else 0
                row[i] = (row[i] + (left + prev[i]) // 2) & 0xFF
        elif filt == 4:
            for i in range(len(row)):
                a = row[i-bpp] if i >= bpp else 0
                b = prev[i]
                c = prev[i-bpp] if i >= bpp else 0
                p = a + b - c
                pa, pb, pc = abs(p-a), abs(p-b), abs(p-c)
                if pa <= pb and pa <= pc: pred = a
                elif pb <= pc: pred = b
                else: pred = c
                row[i] = (row[i] + pred) & 0xFF
        pixels.append(bytes(row))
        prev = row
    return width, height, bpp, pixels

def write_png_rgba(path, width, height, rgba_rows):
    raw = bytearray()
    for row in rgba_rows:
        raw.append(0)
        raw.extend(row)
    compressed = zlib.compress(bytes(raw), 9)
    def chunk(t, d):
        return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xFFFFFFFF)
    ihdr = struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)
    with open(path, 'wb') as f:
        f.write(b'\x89PNG\r\n\x1a\n')
        f.write(chunk(b'IHDR', ihdr))
        f.write(chunk(b'IDAT', compressed))
        f.write(chunk(b'IEND', b''))

PALETTE = [(217,68,68),(232,158,49),(225,199,56),(78,178,110),(64,165,205),(158,110,200),(214,105,160),(80,190,175)]

ROOT = r'c:\Users\zzy\Pictures\作业\Seal-Stroke-Split-Visualization-main'
OUT = os.path.join(ROOT, 'composite-preview')
os.makedirs(OUT, exist_ok=True)

PREVIEW = [
    ('shang', r'public\assets\sources\v1\八部\10202_尚_Z_說文‧八部.png', r'public\assets\experiments\v1\10202_尚_Z_說文‧八部', 6),
    ('bu',    r'public\assets\sources\v1\不部\06605_不_Z_說文‧不部.png', r'public\assets\experiments\v1\06605_不_Z_說文‧不部', 4),
    ('xian',  r'public\assets\sources\v1\先部\07432_先_Z_說文‧先部.png', r'public\assets\experiments\v1\07432_先_Z_說文‧先部', 5),
]

for tag, orig_p, seg_dir, n in PREVIEW:
    ow, oh, obpp, orows = read_png(os.path.join(ROOT, orig_p))
    segs = []
    for s in range(1, n + 1):
        sw, sh, sbpp, srows = read_png(os.path.join(ROOT, seg_dir, 'strokes_individual', f'stroke_{s:02d}.png'))
        segs.append(srows)
    out_rows = []
    for y in range(oh):
        row = bytearray()
        for x in range(ow):
            oR = orows[y][x * 3]
            if oR >= 160:
                row.extend([0, 0, 0, 0])
                continue
            assigned = False
            for s in range(n):
                if segs[s][y][x] < 160:
                    r, g, b = PALETTE[s]
                    row.extend([r, g, b, 255])
                    assigned = True
                    break
            if not assigned:
                row.extend([oR, orows[y][x * 3 + 1], orows[y][x * 3 + 2], 255])
        out_rows.append(row)
    out_path = os.path.join(OUT, f'{tag}_composite.png')
    write_png_rgba(out_path, ow, oh, out_rows)
    print(f'wrote {out_path} ({ow}x{oh})')
print('done')
