"""对 28 个'典型'覆盖的字做 +1px 膨胀，生成预览图和覆盖。"""
from PIL import Image, ImageDraw
from pathlib import Path
import numpy as np
from scipy.ndimage import binary_dilation

base = Path(r'C:\Users\zzy\Pictures\作业\Seal-Stroke-Split-Visualization-main\public\assets\experiments\v1')
preview = Path(r'C:\Users\zzy\Pictures\作业\Seal-Stroke-Split-Visualization-main\scripts\_preview')

# 28 个'典型'覆盖的字
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


def thicken1px(strokes_png_path):
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
        print(f'[SKIP] {gid}')
        fail += 1
        continue
    try:
        thick = thicken1px(sp)
        if thick is None:
            print(f'[SKIP] {gid} 全白')
            fail += 1
            continue
        thick.save(sp)
        ok += 1
    except Exception as e:
        print(f'[FAIL] {gid}: {e}')
        fail += 1

print(f'\n{ok} 成功 / {fail} 失败 / {len(glyphs)} 总计')

# 做 4 字预览（先、光、净、㕻）
preview_gids = ['07432_先_Z_說文‧先部', '07433_光_Z_說文‧火部', '07552_净_Z_說文‧仌部', '00389_㕻_Z_說文‧丶部']
imgs = []
for gid in preview_gids:
    sp = base / gid / 'strokes.png'
    binp = base / gid / 'binary.png'
    im = Image.open(sp).convert('RGB')
    binim = Image.open(binp).convert('RGB')
    imgs.append((binim, im))

scale = 4
pad = 25
title_h = 30
W_each = max(im[0].width for im in imgs) * scale + pad
H_each = max(im[0].height for im in imgs) * scale + title_h * 2
W = W_each * 2 + pad
H = H_each
canvas = Image.new('RGB', (W, H + title_h), (250, 250, 250))
d = ImageDraw.Draw(canvas)
d.text((10, 5), 'binary（原图）', fill='black')
d.text((W_each + 10, 5), 'strokes +1px（新）', fill='black')

x = pad // 2
y0 = title_h * 2
for binim, stim in imgs:
    binim_s = binim.resize((binim.width * scale, binim.height * scale), Image.NEAREST)
    stim_s = stim.resize((stim.width * scale, stim.height * scale), Image.NEAREST)
    canvas.paste(binim_s, (x, y0))
    x += W_each
    canvas.paste(stim_s, (x, y0))
    x += pad

out_file = preview / 'plus1_dianxing_preview.png'
canvas.save(out_file)
print(f'预览: {out_file}')
