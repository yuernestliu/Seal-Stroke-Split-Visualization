import colorsys
import random
from pathlib import Path
from typing import List, Tuple

import numpy as np
from PIL import Image, ImageDraw

from .types import SplitResult


def _palette(num: int) -> list[tuple[int, int, int]]:
    rng = random.Random(7)
    colors = [(0, 0, 0)]
    for _ in range(num):
        colors.append(
            (
                rng.randint(60, 240),
                rng.randint(60, 240),
                rng.randint(60, 240),
            )
        )
    return colors


def render_stroke_map(stroke_map: np.ndarray) -> Image.Image:
    max_id = int(stroke_map.max())
    colors = _palette(max_id)
    canvas = np.full((*stroke_map.shape, 3), 255, dtype=np.uint8)
    for stroke_id in range(1, max_id + 1):
        canvas[stroke_map == stroke_id] = colors[stroke_id]
    return Image.fromarray(canvas, mode="RGB")


def render_binary(mask: np.ndarray) -> Image.Image:
    return Image.fromarray((~mask * 255).astype(np.uint8), mode="L")


def render_single_stroke(mask: np.ndarray, padding: int = 3) -> Image.Image:
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return Image.new("L", (8, 8), 255)
    y0 = max(int(ys.min()) - padding, 0)
    y1 = min(int(ys.max()) + padding + 1, mask.shape[0])
    x0 = max(int(xs.min()) - padding, 0)
    x1 = min(int(xs.max()) + padding + 1, mask.shape[1])
    cropped = mask[y0:y1, x0:x1]
    return render_binary(cropped)


def render_stroke_gallery(result: SplitResult, columns: int = 4, tile_padding: int = 8) -> Image.Image:
    stroke_images = [render_single_stroke(mask) for mask in result.stroke_masks]
    if not stroke_images:
        return Image.new("RGB", (32, 32), (255, 255, 255))

    cell_w = max(img.width for img in stroke_images) + tile_padding * 2
    cell_h = max(img.height for img in stroke_images) + tile_padding * 2 + 14
    cols = max(1, columns)
    rows = (len(stroke_images) + cols - 1) // cols
    canvas = Image.new("RGB", (cell_w * cols, cell_h * rows), (255, 255, 255))

    for idx, img in enumerate(stroke_images):
        row = idx // cols
        col = idx % cols
        x0 = col * cell_w
        y0 = row * cell_h
        rgb = Image.merge("RGB", (img, img, img))
        px = x0 + (cell_w - img.width) // 2
        py = y0 + tile_padding + 14
        canvas.paste(rgb, (px, py))
        draw = ImageDraw.Draw(canvas)
        draw.text((x0 + 6, y0 + 1), f"{idx + 1}", fill=(0, 0, 0))

    return canvas


def render_overlay(result: SplitResult) -> Image.Image:
    base = np.stack([(~result.cropped_binary * 255).astype(np.uint8)] * 3, axis=-1)
    color = np.array(render_stroke_map(result.stroke_map), dtype=np.uint8)
    overlay = base.copy()
    mask = result.stroke_map > 0
    overlay[mask] = (0.35 * base[mask] + 0.65 * color[mask]).astype(np.uint8)
    skeleton_y, skeleton_x = np.nonzero(result.skeleton)
    overlay[skeleton_y, skeleton_x] = np.array([255, 0, 0], dtype=np.uint8)
    return Image.fromarray(overlay, mode="RGB")


def render_overlap_map(result: SplitResult) -> Image.Image:
    counts = np.zeros(result.cropped_binary.shape, dtype=np.uint8)
    for stroke_mask in result.stroke_masks:
        counts += stroke_mask.astype(np.uint8)
    canvas = np.full((*result.cropped_binary.shape, 3), 255, dtype=np.uint8)
    canvas[result.cropped_binary] = np.array([220, 220, 220], dtype=np.uint8)
    canvas[counts >= 2] = np.array([30, 30, 30], dtype=np.uint8)
    return Image.fromarray(canvas, mode="RGB")


# ============================================================
# 笔顺动画：按步绘制
# ============================================================

def render_handwriting_step(
    stroke_masks: List[np.ndarray],
    step: int,
    canvas_size: Tuple[int, int] | None = None,
    background_color: Tuple[int, int, int] = (255, 255, 255),
    stroke_color_palette: List[Tuple[int, int, int]] | None = None,
    ghost_color: Tuple[int, int, int] = (220, 220, 220),
) -> Image.Image:
    """绘制笔顺第 step 步的状态图。

    stroke_masks 应为已按笔顺排序的掩码列表；step 为 1-based，显示第 1~step 笔。
    """
    if not stroke_masks:
        return Image.new("RGB", (64, 64), background_color)

    if canvas_size is None:
        h, w = stroke_masks[0].shape
        canvas_size = (w, h)

    canvas = np.full((canvas_size[1], canvas_size[0], 3), background_color, dtype=np.uint8)

    if stroke_color_palette is None:
        stroke_color_palette = []
        n = len(stroke_masks)
        for i in range(n):
            hue = (i * 0.618033988749895) % 1.0
            rgb = colorsys.hls_to_rgb(hue, 0.6, 0.8)
            stroke_color_palette.append(
                (int(rgb[0] * 255), int(rgb[1] * 255), int(rgb[2] * 255))
            )

    for idx, mask in enumerate(stroke_masks):
        color = stroke_color_palette[idx % len(stroke_color_palette)] if idx < step else ghost_color
        canvas[mask] = color

    return Image.fromarray(canvas, mode="RGB")


def render_handwriting_animation(
    stroke_masks: List[np.ndarray],
    out_dir: Path,
    prefix: str = "第",
    suffix: str = "步",
    canvas_size: Tuple[int, int] | None = None,
) -> None:
    """生成笔顺动画的所有帧图，逐帧递增显示笔画。"""
    out_dir.mkdir(parents=True, exist_ok=True)

    n = len(stroke_masks)
    if n == 0:
        return

    if canvas_size is None:
        h, w = stroke_masks[0].shape
        canvas_size = (w, h)

    for step in range(1, n + 1):
        img = render_handwriting_step(stroke_masks, step, canvas_size=canvas_size)
        img.save(out_dir / f"{prefix}{step}{suffix}.png")