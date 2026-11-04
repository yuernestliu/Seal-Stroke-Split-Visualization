"""Trial outputs for non-knife radicals using whole-glyph 8-connected domains."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import label, distance_transform_edt

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from identify_radical_images import (  # noqa: E402
    IDC, TARGETS, box_mask, choose_alternative, find_reference,
    get_filename_parts, locate_target, load_ids, parse_tree,
    normalize_glyph, box_mask,
)

NEIGHBORHOOD = np.ones((3, 3), dtype=np.uint8)


def save(gray, mask, path):
    rgb = np.repeat(gray[:, :, None], 3, axis=2).astype(np.uint8)
    # Assign every gray anti-aliased pixel to the nearest original black
    # connected domain.  Gray pixels near the selected radical become red;
    # gray pixels near other components retain their original gray value.
    black = gray == 0
    black_labels, _ = label(black, structure=NEIGHBORHOOD)
    selected_labels = set(np.unique(black_labels[mask])) - {0}
    _, nearest = distance_transform_edt(~black, return_indices=True)
    nearest_labels = black_labels[tuple(nearest)]
    red_gray = (gray != 0) & (gray < 255) & np.isin(nearest_labels, list(selected_labels))
    red_mask = mask | red_gray
    strength = np.clip((255.0 - gray) / 255.0, 0.0, 1.0)
    red = np.stack([255.0 - 35.0 * strength, 255.0 - 215.0 * strength, 255.0 - 215.0 * strength], axis=2).astype(np.uint8)
    rgb[red_mask] = red[red_mask]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        Image.fromarray(rgb, mode="RGB").save(f, format="PNG")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--radical", required=True, choices=["心", "勹"])
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--complete-radical", action="store_true")
    ap.add_argument("--whole-positioned", action="store_true")
    args = ap.parse_args()
    root = Path(__file__).resolve().parents[1]
    source = root / "按部首分类" / args.radical
    ids = load_ids(root / "data" / "ids.txt")
    total = 0
    paths = sorted(source.glob("*.png"))
    for path in paths:
            gray = np.asarray(Image.open(path).convert("L"))
            black = gray == 0
            char, _ = get_filename_parts(path)
            sequence = choose_alternative(ids.get(char, []))[0] if ids.get(char) else None
            if sequence and sequence.startswith("⿰"):
                structure_name = "左右结构"
            elif sequence and sequence.startswith("⿲"):
                structure_name = "左中右结构"
            elif sequence and sequence.startswith("⿱"):
                structure_name = "上下结构"
            elif sequence and sequence.startswith("⿳"):
                structure_name = "上中下结构"
            else:
                structure_name = "其他结构"
            if char in TARGETS[args.radical]:
                mask = black
            else:
                target_box = None
                target_outer = False
                if sequence and sequence[0] in IDC:
                    try:
                        tree, consumed = parse_tree(sequence)
                        if consumed == len(sequence):
                            target_box, target_outer = locate_target(tree, TARGETS[args.radical])
                    except (IndexError, ValueError):
                        pass
                if args.whole_positioned and target_box is not None:
                    labels, count = label(black, structure=NEIGHBORHOOD)
                    components = []
                    tx0, ty0, tx1, ty1 = target_box
                    tx = (tx0 + tx1) / 2
                    ty = (ty0 + ty1) / 2
                    for index in range(1, count + 1):
                        component = labels == index
                        ys, xs = np.where(component)
                        if len(xs):
                            cx = float(xs.mean() / max(1, black.shape[1] - 1))
                            cy = float(ys.mean() / max(1, black.shape[0] - 1))
                            components.append((cx, cy, len(xs), index))
                    if components:
                        if tx < 0.4:
                            chosen = min(components, key=lambda v: (v[0], -v[2]))
                        elif tx > 0.6:
                            chosen = max(components, key=lambda v: (v[0], v[2]))
                        elif ty < 0.4:
                            chosen = min(components, key=lambda v: (v[1], -v[2]))
                        elif ty > 0.6:
                            chosen = max(components, key=lambda v: (v[1], v[2]))
                        else:
                            chosen = min(components, key=lambda v: ((v[0]-tx)**2 + (v[1]-ty)**2, -v[2]))
                        mask = labels == chosen[3]
                    else:
                        mask = np.zeros_like(black)
                    save(gray, mask, args.output / structure_name / path.name)
                    total += 1
                    continue
                if args.complete_radical and target_box is not None:
                    normalized, crop_box = normalize_glyph(gray)
                    region = box_mask(normalized.shape, target_box, target_outer)
                    left, top, right, bottom = crop_box
                    cell = np.asarray(Image.fromarray((region.astype(np.uint8) * 255), mode="L").resize((right-left, bottom-top), Image.Resampling.NEAREST)) > 0
                    cell_original = np.zeros_like(black)
                    cell_original[top:bottom, left:right] = cell
                    labels, count = label(black & cell_original, structure=NEIGHBORHOOD)
                    if args.radical == "心":
                        mask = black & cell_original
                    else:
                        # 勹 is an enclosing component: retain all domains
                        # touching the outer boundary of its target cell.
                        ys, xs = np.where(cell_original)
                        keep = np.zeros_like(black)
                        if len(xs):
                            x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
                            for index in range(1, count + 1):
                                component = labels == index
                                cy, cx = np.where(component)
                                if len(cx) and (cx.min() <= x0 + 2 or cx.max() >= x1 - 2 or cy.min() <= y0 + 2 or cy.max() >= y1 - 2):
                                    keep |= component
                        mask = keep
                    save(gray, mask, args.output / structure_name / path.name)
                    total += 1
                    continue
                labels, count = label(black, structure=NEIGHBORHOOD)
                candidates = []
                for index in range(1, count + 1):
                    component = labels == index
                    ys, xs = np.where(component)
                    if not len(xs):
                        continue
                    if target_box:
                        x0, y0, x1, y1 = target_box
                        cx = ((xs.mean() / max(1, black.shape[1] - 1)) - (x0 + x1) / 2) ** 2
                        cy = ((ys.mean() / max(1, black.shape[0] - 1)) - (y0 + y1) / 2) ** 2
                        score = cx + cy
                    else:
                        score = 0.0
                    candidates.append((score, -len(xs), index))
                mask = labels == min(candidates)[2] if candidates else np.zeros_like(black)
            save(gray, mask, args.output / structure_name / path.name)
            total += 1
    print(f"radical={args.radical} total={total} output={args.output}")


if __name__ == "__main__":
    main()
