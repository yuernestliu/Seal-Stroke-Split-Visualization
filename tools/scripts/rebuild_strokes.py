"""为指定字形重新合成 strokes.png：用 binary.png 当底 + strokes_individual mask + 调色板.

对 mask 是裁剪图的情况，用 template matching 在 binary.png 找位置。
"""
from pathlib import Path
from PIL import Image


PALETTE = [
    (217, 68, 68),   # 红
    (49, 134, 232),  # 蓝
    (78, 178, 110),  # 绿
    (232, 158, 49),  # 橙
    (158, 110, 200), # 紫
    (225, 199, 56),  # 黄
    (214, 105, 160), # 粉
    (64, 165, 205),  # 青
    (80, 190, 175),  # 蓝绿
    (200, 80, 140),  # 玫红
    (130, 200, 100), # 黄绿
    (255, 140, 60),  # 橙红
    (90, 90, 200),   # 蓝紫
    (170, 130, 80),  # 棕
]


def binarize_white_is_ink(img: Image.Image) -> Image.Image:
    """返回 mode='L' 二值图：255 = 笔画像素, 0 = 背景."""
    g = img.convert("L")
    return g.point(lambda v: 255 if v > 128 else 0)


def binarize_black_is_ink(img: Image.Image) -> Image.Image:
    """返回 mode='L' 二值图：255 = 笔画像素, 0 = 背景. 用于 binary.png（白底黑字）."""
    g = img.convert("L")
    return g.point(lambda v: 255 if v < 128 else 0)


def match_position(mask: Image.Image, target: Image.Image) -> tuple[int, int]:
    """在 target(全画布) 中找 mask 最佳左上角 (x0, y0).

    mask 与 target 都是 mode='L' 二值图，255=笔画, 0=背景.
    """
    mw, mh = mask.size
    tw, th = target.size
    if mw > tw or mh > th:
        raise ValueError(f"mask {mask.size} 比 target {target.size} 大")
    # 用 mask 与 target 滑窗，按 (mask 与 target) AND 区域求和，取最大
    best = (-1, 0, 0)
    # 把 target 转成 bytes 加速
    tgt_bytes = target.tobytes()
    mask_bytes = mask.tobytes()
    # PIL 的 getpixel 太慢，用 numpy 不可用就手写
    # 简单做：每行扫描
    for y in range(th - mh + 1):
        for x in range(tw - mw + 1):
            s = 0
            for row in range(mh):
                base = ((y + row) * tw + x) * 1
                mbase = row * mw * 1
                for col in range(mw):
                    if mask_bytes[mbase + col] and tgt_bytes[base + col]:
                        s += 1
            if s > best[0]:
                best = (s, x, y)
    if best[0] <= 0:
        return 0, 0
    return best[1], best[2]


def rebuild_one(folder: Path, dry_run: bool = True) -> bool:
    binary_path = folder / "binary.png"
    out_path = folder / "strokes.png"
    if not binary_path.exists():
        return False
    binary = Image.open(binary_path)
    bw, bh = binary.size
    target = binarize_black_is_ink(binary)
    si_dir = folder / "strokes_individual"
    if not si_dir.exists():
        return False
    mask_files = sorted(si_dir.glob("stroke_*.png"))
    if not mask_files:
        return False

    # 对每个 mask 找位置；mask 已经是全画布就跳过
    placements = []
    for mf in mask_files:
        m = Image.open(mf)
        if m.size != (bw, bh):
            mbin = binarize_white_is_ink(m)
            x0, y0 = match_position(mbin, target)
        else:
            x0, y0 = 0, 0
        placements.append((mf, m, x0, y0, m.size))

    # 合成
    out = Image.new("RGB", (bw, bh), "white")
    px = out.load()
    for idx, (mf, m, x0, y0, (mw, mh)) in enumerate(placements):
        mbin = binarize_white_is_ink(m)
        color = PALETTE[idx % len(PALETTE)]
        for row in range(mh):
            for col in range(mw):
                if mbin.getpixel((col, row)):
                    nx, ny = x0 + col, y0 + row
                    if 0 <= nx < bw and 0 <= ny < bh:
                        px[nx, ny] = color

    if dry_run:
        print(f"  [dry-run] would write {out_path}  size={out.size}  strokes={len(placements)}")
        # 临时保存预览
        out.save(folder / "strokes_rebuilt.png")
    else:
        out.save(out_path)
        print(f"  wrote {out_path}")
    return True


if __name__ == "__main__":
    import sys
    base = Path("public/assets/experiments/v1")
    targets = sys.argv[1:] if len(sys.argv) > 1 else ["07432_先_Z_說文‧先部"]
    for name in targets:
        f = base / name
        print(f"=== {name}")
        rebuild_one(f, dry_run=True)
