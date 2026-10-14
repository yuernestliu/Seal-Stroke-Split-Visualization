"""对 28 个'典型'覆盖的字做 -1px 细化，撤销 thicken_dianxing_28.py 的 +1px。"""
from PIL import Image
from pathlib import Path
import numpy as np
from scipy.ndimage import binary_erosion

base = Path(r'C:\Users\zzy\Pictures\作业\Seal-Stroke-Split-Visualization-main\public\assets\experiments\v1')

glyphs = [
    '00389_㕻_Z_說文‧丶部',
    '07008_侠_Z_說文‧人部',
    '07432_先_Z_說文‧先部',
    '07433_光_Z_說文‧火部',
    '07485_兽_Z_說文‧犬部',
    '07520_冠_Z_說文‧冖部',
    '07547_冻_Z_說文‧仌部',
    '07552_净_Z_說文‧仌部',
    '07564_凌_Z_說文‧仌部',
    '07588_凤_Z_說文‧鳥部',
    '16023_狗_Z_說文‧犬部',
    '16242_玲_Z_說文‧玉部',
    '16374_琶_Z_說文‧琴部',
    '16631_男_Z_說文‧男部',
    '16668_畜_Z_說文‧田部',
    '16766_疾_Z_說文‧疒部',
    '16967_皇_Z_說文‧王部',
    '17383_砧_Z_說文‧石部',
    '17672_祈_Z_說文‧示部',
    '17803_秋_Z_說文‧禾部',
    '17974_究_Z_說文‧穴部',
    '18007_窗_Z_說文‧囪部',
    '18080_章_Z_說文‧音部',
    '18194_筒_Z_說文‧竹部',
    '18527_粟_Z_說文‧𠧪部',
    '24806_锦_Z_說文‧金部',
    '25018_闺_Z_說文‧門部',
    '25070_阮_Z_說文‧阜部',
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
    except Exception as e:
        print(f'[FAIL] {gid}: {e}')
        fail += 1

print(f'{ok} 成功 / {fail} 失败 / {len(glyphs)} 总计')
