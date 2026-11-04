"""对 13 个字做 -1px 细化，撤销之前的 +1px 膨胀。"""
from PIL import Image
from pathlib import Path
import numpy as np
from scipy.ndimage import binary_erosion

base = Path(r'C:\Users\zzy\Pictures\作业\Seal-Stroke-Split-Visualization-main\public\assets\experiments\v1')

# 13 个不在'典型'里的字 = 之前 +1px 覆盖过的
glyphs = [
    '07467_八_Z_說文‧八部',
    '07865_勹_Z_說文‧勹部',
    '08145_向_Z_說文‧宀部',
    '10048_宀_Z_說文‧宀部',
    '11789_才_Z_說文‧才部',
    '16722_疒_Z_說文‧疒部',
    '30490_𠦒_Z_說文‧𠦒部',
    '34644_𡧌_Z_說文‧宀部',
    '34667_𡧣_Z_說文‧宀部',
    '34675_𡧫_Z_說文‧宀部',
    '35039_𡭗_Z_說文‧八部',
    '35068_𡭴_Z_說文‧白部',
    '54914_𦣺_Z_說文‧白部',
]


def minus1px(strokes_png_path):
    img = np.array(Image.open(strokes_png_path).convert('RGB'))
    h, w = img.shape[:2]
    is_colored = ~((img[:, :, 0] == 255) & (img[:, :, 1] == 255) & (img[:, :, 2] == 255))
    if not is_colored.any():
        return None
    struct = np.ones((3, 3), dtype=bool)
    eroded = binary_erosion(is_colored, structure=struct, iterations=1)
    out_img = np.full((h, w, 3), 255, dtype=np.uint8)
    out_img[eroded] = img[eroded]
    return Image.fromarray(out_img)


ok, fail = 0, 0
for gid in glyphs:
    sp = base / gid / 'strokes.png'
    if not sp.exists():
        print(f'[SKIP] {gid}')
        fail += 1
        continue
    try:
        thin = minus1px(sp)
        if thin is None:
            print(f'[SKIP] {gid} 全白')
            fail += 1
            continue
        thin.save(sp)
        ok += 1
        print(f'[OK] {gid}')
    except Exception as e:
        print(f'[FAIL] {gid}: {e}')
        fail += 1

print(f'\n{ok} 成功 / {fail} 失败 / {len(glyphs)} 总计')
