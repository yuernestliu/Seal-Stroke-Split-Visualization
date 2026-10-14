"""检查 13 个被错误覆盖的字当前状态"""
from PIL import Image
from pathlib import Path
import numpy as np

base = Path(r'C:\Users\zzy\Pictures\作业\Seal-Stroke-Split-Visualization-main\public\assets\experiments\v1')

# 这 13 个字被我覆盖了，但 "典型" outputs 里没有
wrong = [
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

for gid in wrong:
    sp = base / gid / 'strokes.png'
    bp = base / gid / 'binary.png'
    if not sp.exists() or not bp.exists():
        print(f'{gid}: MISSING')
        continue
    bin_img = np.array(Image.open(bp).convert('L'))
    fg = bin_img < 128
    if not fg.any():
        print(f'{gid}: binary 全白')
        continue
    bin_pix = fg.sum()

    rgb = np.array(Image.open(sp).convert('RGB'))
    is_white = (rgb[:, :, 0] == 255) & (rgb[:, :, 1] == 255) & (rgb[:, :, 2] == 255)
    stroke_pix = (~is_white).sum()
    ratio = stroke_pix / bin_pix if bin_pix else 0
    print(f'{gid}: binary前景={bin_pix}px  strokes={stroke_pix}px  ratio={ratio:.2f}')
