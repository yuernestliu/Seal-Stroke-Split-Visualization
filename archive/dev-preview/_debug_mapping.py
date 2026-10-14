"""精确对比 .bak 里 07432_先 的 segments 起点 + 当前 js 里的 segments 起点
+ 看 disk 上 stroke_NN.png 的具体内容（用像素 bbox 推断哪一笔）"""
import json, re, hashlib
from pathlib import Path
from PIL import Image

ROOT = Path(r'c:\Users\zzy\Pictures\作业\Seal-Stroke-Split-Visualization-main')
bak = (ROOT / 'data' / 'glyphs.js.bak').read_text(encoding='utf-8')
cur = (ROOT / 'data' / 'glyphs.js').read_text(encoding='utf-8')

def extract(text, marker):
    m = re.search(r'window\.GLYPH_DATA\s*=\s*', text)
    brace = text.index('{', m.end())
    depth = 0; end = -1; in_str = False; esc = False
    for i in range(brace, len(text)):
        c = text[i]
        if in_str:
            if esc: esc = False
            elif c == chr(92): esc = True
            elif c == chr(34): in_str = False
        else:
            if c == chr(34): in_str = True
            elif c == '{': depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0: end = i; break
    return json.loads(text[brace:end+1])

data_bak = extract(bak, 1)
data_cur = extract(cur, 1)

# 找 07432_先
def find_g(data, gid):
    for g in data['glyphs']:
        if g['id'].startswith(gid + '_'):
            return g
    return None

g_bak = find_g(data_bak, '07432_先')
g_cur = find_g(data_cur, '07432_先')

print(f"=== 07432_先: .bak segments ===")
for i, s in enumerate(g_bak['segments']):
    pts = s['points']
    has_img = bool(s.get('image'))
    print(f"  pos={i} id={s['id']} 起={pts[0]} 末={pts[-1]} npts={len(pts)} image={'有' if has_img else '无'}")

print(f"\n=== 07432_先: 当前 js segments（新顺序）===")
for i, s in enumerate(g_cur['segments']):
    pts = s['points']
    has_img = bool(s.get('image'))
    print(f"  pos={i} id={s['id']} 起={pts[0]} 末={pts[-1]} npts={len(pts)} image={'有' if has_img else '无'}")

# 看 disk 上的 stroke_NN.png
print(f"\n=== disk 上 strokes_individual ===")
sid = ROOT / 'public' / 'assets' / 'experiments' / 'v1' / '07432_先_Z_說文‧先部' / 'strokes_individual'
for f in sorted(sid.glob('*.png')):
    img = Image.open(f).convert('L')
    w, h = img.size
    px = img.load()
    # 找 bbox
    min_x, min_y, max_x, max_y = w, h, 0, 0
    cnt = 0
    for y in range(h):
        for x in range(w):
            if px[x, y] > 128:
                cnt += 1
                min_x = min(min_x, x); min_y = min(min_y, y)
                max_x = max(max_x, x); max_y = max(max_y, y)
    print(f"  {f.name}: 大小={img.size} bbox=({min_x},{min_y})-({max_x},{max_y}) 像素={cnt}")