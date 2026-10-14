"""对 28 个（顺序被改的）字的 strokes_individual/*.png 做 +1px 膨胀，覆盖原文件。"""
import json, re
from pathlib import Path
from PIL import Image
import numpy as np
from scipy.ndimage import binary_dilation

ROOT = Path(r'c:\Users\zzy\Pictures\作业\Seal-Stroke-Split-Visualization-main')
BASE = ROOT / 'public' / 'assets' / 'experiments' / 'v1'

# ---------- 找出 28 个字（segments 顺序与 .bak 不同的字） ----------
def parse_js(text):
    m = re.search(r'window\.GLYPH_DATA\s*=\s*', text)
    brace = text.index('{', m.end())
    depth = 0; end = -1
    for i in range(brace, len(text)):
        c = text[i]
        if c == '{': depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0: end = i; break
    return json.loads(text[brace:end+1])

bak = parse_js((ROOT / 'data' / 'glyphs.js.bak').read_text(encoding='utf-8'))
cur = parse_js((ROOT / 'data' / 'glyphs.js').read_text(encoding='utf-8'))

old_by_id = {g['id']: g for g in bak['glyphs']}
new_by_id = {g['id']: g for g in cur['glyphs']}

def seg_fp(seg):
    pts = seg['points']
    return (tuple(pts[0]), tuple(pts[-1]), len(pts))

changed_ids = []
for gid in old_by_id:
    o = [seg_fp(s) for s in old_by_id[gid]['segments']]
    n = [seg_fp(s) for s in new_by_id[gid]['segments']]
    if o != n:
        changed_ids.append(gid)

print(f'需要处理的字（顺序改变）: {len(changed_ids)}')

# ---------- +1px 膨胀函数 ----------
def thicken1px(png_path: Path) -> bool:
    img = np.array(Image.open(png_path).convert('RGB'))
    h, w = img.shape[:2]
    is_colored = ~((img[:, :, 0] == 255) & (img[:, :, 1] == 255) & (img[:, :, 2] == 255))
    if not is_colored.any():
        return False
    struct = np.ones((3, 3), dtype=bool)
    thickened = binary_dilation(is_colored, structure=struct, iterations=1)
    out_img = np.full((h, w, 3), 255, dtype=np.uint8)
    out_img[is_colored] = img[is_colored]
    new_mask = thickened & ~is_colored
    if new_mask.any():
        ys, xs = np.nonzero(is_colored)
        colors = img[ys, xs]
        ys_new, xs_new = np.nonzero(new_mask)
        for y, x in zip(ys_new, xs_new):
            d = (ys - y) ** 2 + (xs - x) ** 2
            out_img[y, x] = colors[d.argmin()]
    Image.fromarray(out_img).save(png_path)
    return True

# ---------- 遍历 ----------
ok, fail, skip = 0, 0, 0
for gid in changed_ids:
    ind_dir = BASE / gid / 'strokes_individual'
    if not ind_dir.exists():
        print(f'[SKIP] {gid} - 无 strokes_individual 目录')
        skip += 1
        continue
    pngs = sorted(ind_dir.glob('stroke_*.png'))
    if not pngs:
        print(f'[SKIP] {gid} - 目录为空')
        skip += 1
        continue
    for p in pngs:
        try:
            if thicken1px(p):
                ok += 1
            else:
                print(f'[SKIP] {gid} {p.name} - 全白')
                skip += 1
        except Exception as e:
            print(f'[FAIL] {gid} {p.name} - {e}')
            fail += 1
    print(f'[OK]   {gid} - {len(pngs)} 张图')

print(f'\n汇总: {ok} 张成功 / {fail} 张失败 / {skip} 张跳过')
