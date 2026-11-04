"""Create structure-separated knife-radical previews using modern IDS layout."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import binary_dilation
from scipy.ndimage import label

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from identify_radical_images import (  # noqa: E402
    IDC,
    TARGETS,
    box_mask,
    choose_alternative,
    get_filename_parts,
    locate_target,
    normalize_glyph,
    parse_tree,
    load_ids,
    find_reference,
    fit_reference_template,
)


STRUCTURES = {"左右结构", "上下结构", "左中右结构"}
NEIGHBORHOOD = np.ones((3, 3), dtype=np.uint8)


def export(gray: np.ndarray, mask: np.ndarray, output: Path) -> None:
    edge = binary_dilation(mask, structure=NEIGHBORHOOD) & (gray > 0) & (gray < 255)
    red = mask | edge
    rgb = np.repeat(gray[:, :, None], 3, axis=2).astype(np.uint8)
    strength = np.clip((255.0 - gray) / 255.0, 0.0, 1.0)
    color = np.stack(
        [255.0 - 35.0 * strength, 255.0 - 215.0 * strength, 255.0 - 215.0 * strength],
        axis=2,
    ).astype(np.uint8)
    rgb[red] = color[red]
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("wb") as handle:
        Image.fromarray(rgb, mode="RGB").save(handle, format="PNG")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rightmost-two", action="store_true")
    parser.add_argument("--rightmost-component", action="store_true")
    parser.add_argument("--whole-glyph-rightmost", action="store_true")
    parser.add_argument("--whole-glyph-positioned", action="store_true")
    parser.add_argument("--centroid-positioned", action="store_true")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    source = root / "按部首分类" / "刀"
    output = args.output or root / "部首识别_刀_连通约束"
    ids = load_ids(root / "data" / "ids.txt")
    reference = find_reference(root, "刀")
    total = 0
    for structure in STRUCTURES:
        source_dir = source / structure
        for path in sorted(source_dir.glob("*.png")):
            char, _ = get_filename_parts(path)
            gray = np.asarray(Image.open(path).convert("L"))
            black = gray == 0
            if char in TARGETS["刀"]:
                mask = black
            elif (args.whole_glyph_rightmost or args.whole_glyph_positioned or args.centroid_positioned) and structure in STRUCTURES:
                labels, count = label(black, structure=NEIGHBORHOOD)
                components = []
                for index in range(1, count + 1):
                    component = labels == index
                    ys, xs = np.where(component)
                    if len(xs):
                        components.append((int(xs.max()), int(ys.max()), int(xs.min()), int(ys.min()), float(xs.mean()), float(ys.mean()), int(component.sum()), index))
                mask = np.zeros_like(black)
                if components:
                    if args.centroid_positioned and structure == "左右结构":
                        chosen = max(components, key=lambda item: (item[4], item[6]))
                    elif args.centroid_positioned and structure == "上下结构":
                        chosen = max(components, key=lambda item: (item[5], item[6]))
                    elif structure == "左右结构":
                        chosen = max(components, key=lambda item: (item[0], item[6]))
                    elif structure == "上下结构":
                        chosen = max(components, key=lambda item: (item[1], item[6]))
                    else:
                        height, width = black.shape
                        chosen = min(
                            components,
                            key=lambda item: (abs((item[4] if args.centroid_positioned else ((item[0] + item[2]) / 2)) - (width - 1) / 2), -item[6]),
                        )
                    mask = labels == chosen[7]
            else:
                alternatives = ids.get(char, [])
                sequence = choose_alternative(alternatives)[0] if alternatives else None
                box = None
                outer = False
                if sequence and sequence[0] in IDC:
                    try:
                        tree, consumed = parse_tree(sequence)
                        if consumed == len(sequence):
                            box, outer = locate_target(tree, TARGETS["刀"])
                    except (IndexError, ValueError):
                        pass
                # The modern-font structural position is the primary rule.
                # These are layout cells, not a loose template match.
                if structure == "左右结构":
                    box, outer = (0.5, 0.0, 1.0, 1.0), False
                elif structure == "上下结构":
                    box, outer = (0.0, 0.5, 1.0, 1.0), False
                elif structure == "左中右结构":
                    box, outer = (1 / 3, 0.0, 2 / 3, 1.0), False
                normalized, crop_box = normalize_glyph(gray)
                region = box_mask(normalized.shape, box, outer)
                left, top, right, bottom = crop_box
                mapped = np.asarray(
                    Image.fromarray((region.astype(np.uint8) * 255), mode="L").resize(
                        (right - left, bottom - top), Image.Resampling.NEAREST
                    )
                ) > 0
                mask = np.zeros_like(black)
                mask[top:bottom, left:right] = mapped
                mask &= black
                if (args.rightmost_two or args.rightmost_component) and structure == "左右结构":
                    labels, count = label(mask, structure=NEIGHBORHOOD)
                    components = []
                    for index in range(1, count + 1):
                        component = labels == index
                        ys, xs = np.where(component)
                        if len(xs):
                            components.append((int(xs.max()), int(xs.min()), int(component.sum()), index))
                    components.sort(reverse=True)
                    keep = np.zeros_like(mask)
                    limit = 1 if args.rightmost_component else 2
                    for _, _, _, index in components[:limit]:
                        keep |= labels == index
                    if keep.any():
                        mask = keep
                # Keep only black connected components touched by a fitted
                # knife seed.  Pixels merely lying in the modern-font cell,
                # but disconnected from the knife strokes, are excluded.
                fitted, _ = fit_reference_template(normalized, region, reference, 1)
                seed_norm = fitted & normalized & region
                seed_original = np.zeros_like(black)
                seed_mapped = np.asarray(
                    Image.fromarray((seed_norm.astype(np.uint8) * 255), mode="L").resize(
                        (right - left, bottom - top), Image.Resampling.NEAREST
                    )
                ) > 0
                seed_original[top:bottom, left:right] = seed_mapped
                labels, count = label(mask, structure=NEIGHBORHOOD)
                if count and seed_original.any() and not (args.rightmost_two or args.rightmost_component):
                    keep = np.zeros_like(mask)
                    for index in range(1, count + 1):
                        component = labels == index
                        if (component & seed_original).any():
                            keep |= component
                    if keep.any():
                        mask = keep
            export(gray, mask, output / structure / path.name)
            total += 1
    print(f"total={total} output={output}")


if __name__ == "__main__":
    main()
