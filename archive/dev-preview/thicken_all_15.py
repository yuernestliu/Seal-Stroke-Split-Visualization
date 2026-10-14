"""对 15 个骨架字的 strokes.png 做 +1px 膨胀，覆盖原文件。"""
from PIL import Image
from pathlib import Path
import numpy as np
from scipy.ndimage import binary_dilation

base = Path(r'C:\Users\zzy\Pictures\作业\Seal-Stroke-Split-Visualization-main\public\assets\experiments\v1')

glyphs = [
    '07432_先_Z_說文‧先部',
    '07552_净_Z_說文‧仌部',
    '07467_八_Z_說文‧八部',
    '07865_勹_Z_說文‧勹部',
    '08145_向_Z_說文‧宀部',
    '10048_宀_Z_說文‧宀部',
    '11789_才_Z_說文‧才部',
    '16722_疒_Z_說文‧疒部',
    '30490_\U00020992_Z_說文‧\U00020992部',
    '34644_\U000219CC_Z_說文‧宀部',
    '34667_\U000219E3_Z_說文‧宀部',
    '34675_\U000219EB_Z_說文‧宀部',
    '35039_\U00021B57_Z_說文‧八部',
    '35068_\U00021B74_Z_說文‧白部',
    '54914_\U000268FA_Z_說文‧白部',
]


def thicken1px(strokes_png_path: Path) -> Image.Image | None:
    img = np.array(Image.open(strokes_png_path).convert('RGB'))
    h, w = img.shape[:2]
    is_colored = ~((img[:, :, 0] == 255) & (img[:, :, 1] == 255) & (img[:, :, 2] == 255))
    if not is_colored.any():
        return None
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
    return Image.fromarray(out_img)


ok, fail = 0, 0
for gid in glyphs:
    sp = base / gid / 'strokes.png'
    if not sp.exists():
        print(f'[SKIP] {gid} - 找不到 strokes.png')
        fail += 1
        continue
    try:
        thick = thicken1px(sp)
        if thick is None:
            print(f'[SKIP] {gid} - strokes.png 全白')
            fail += 1
            continue
        thick.save(sp)
        print(f'[OK]   {gid}')
        ok += 1
    except Exception as e:
        print(f'[FAIL] {gid} - {e}')
        fail += 1

print(f'\n汇总: {ok} 成功 / {fail} 失败 / {len(glyphs)} 总计')
