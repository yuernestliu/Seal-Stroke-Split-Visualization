"""Identify connected radical pixels for the three trial radical folders.

Recognition is performed on exact-black binary masks only.  The independent
radical reference is also binarized first.  Structure/IDS information limits
the search area, then one connected target component is selected by comparing
its normalized binary shape with the normalized binary reference.  Disjoint
target regions are never combined into one radical mask.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import cv2
from PIL import Image
from scipy.ndimage import binary_dilation, label
from collections import deque

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from build_component_csvs import IDC, choose_alternative, get_filename_parts, load_ids  # noqa: E402


TARGETS = {
    "刀": {"刀", "刂"},
    "心": {"心", "忄", "⺗"},
    "勹": {"勹"},
}
REFERENCE_FILES = {
    "刀": "07616_刀_Z_說文‧刀部.png",
    "心": "11139_心_Z_說文‧心部.png",
    "勹": "07865_勹_Z_說文‧勹部.png",
}
ENCLOSING = {"⿴", "⿵", "⿶", "⿷", "⿸", "⿹", "⿺"}
NEIGHBORHOOD = np.ones((3, 3), dtype=np.uint8)
CANVAS = 128
PATCH_SIZE = 64


def parse_tree(sequence: str, index: int = 0):
    token = sequence[index]
    if token not in IDC:
        return {"token": token, "children": []}, index + 1
    children = []
    for _ in range(3 if token in {"⿲", "⿳"} else 2):
        child, index = parse_tree(sequence, index + 1 if not children else index)
        children.append(child)
    return {"token": token, "children": children}, index


def contains_target(node: dict, aliases: set[str]) -> bool:
    return node["token"] in aliases or any(contains_target(child, aliases) for child in node["children"])


def child_boxes(token: str, count: int, box: tuple[float, float, float, float]):
    x0, y0, x1, y1 = box
    if token in {"⿰", "⿲"}:
        return [(x0 + (x1 - x0) * i / count, y0, x0 + (x1 - x0) * (i + 1) / count, y1) for i in range(count)]
    if token in {"⿱", "⿳"}:
        return [(x0, y0 + (y1 - y0) * i / count, x1, y0 + (y1 - y0) * (i + 1) / count) for i in range(count)]
    if token in ENCLOSING and count == 2:
        inset = 0.22
        return [box, (x0 + inset * (x1 - x0), y0 + inset * (y1 - y0), x1 - inset * (x1 - x0), y1 - inset * (y1 - y0))]
    return [box for _ in range(count)]


def locate_target(node: dict, aliases: set[str], box=(0.0, 0.0, 1.0, 1.0)):
    if not node["children"]:
        return (box, False) if node["token"] in aliases else (None, False)
    boxes = child_boxes(node["token"], len(node["children"]), box)
    hits = []
    outer = False
    for index, child in enumerate(node["children"]):
        if contains_target(child, aliases):
            hit, _ = locate_target(child, aliases, boxes[index])
            if hit is not None:
                hits.append(hit)
            outer = outer or (node["token"] in ENCLOSING and index == 0)
    if not hits:
        return None, False
    return (
        min(box[0] for box in hits),
        min(box[1] for box in hits),
        max(box[2] for box in hits),
        max(box[3] for box in hits),
    ), outer


def fallback_box(sequence: str | None, radical: str):
    if not sequence or sequence[0] not in IDC:
        return (0.0, 0.0, 1.0, 1.0), radical == "勹"
    op = sequence[0]
    if radical == "勹":
        if op in ENCLOSING:
            return (0.0, 0.0, 1.0, 1.0), True
        if op == "⿱":
            return (0.0, 0.0, 1.0, 0.52), False
    if radical == "刀":
        if op == "⿰":
            return (0.5, 0.0, 1.0, 1.0), False
        if op == "⿲":
            return (1 / 3, 0.0, 2 / 3, 1.0), False
        if op in {"⿱", "⿳"}:
            return (0.0, 0.55, 1.0, 1.0), False
    if radical == "心":
        if op == "⿰":
            return (0.0, 0.0, 0.5, 1.0), False
        if op in {"⿱", "⿳"}:
            return (0.0, 0.55, 1.0, 1.0), False
    return (0.0, 0.0, 1.0, 1.0), False


def box_mask(shape: tuple[int, int], box, outer: bool) -> np.ndarray:
    height, width = shape
    yy, xx = np.mgrid[0:height, 0:width]
    nx = xx / max(1, width - 1)
    ny = yy / max(1, height - 1)
    x0, y0, x1, y1 = box
    if outer:
        distance = np.minimum.reduce([nx - x0, x1 - nx, ny - y0, y1 - ny])
        return distance <= 0.25
    return (nx >= x0 - 0.015) & (nx <= x1 + 0.015) & (ny >= y0 - 0.015) & (ny <= y1 + 0.015)


def crop_mask(mask: np.ndarray) -> np.ndarray:
    ys, xs = np.where(mask)
    if len(xs) == 0:
        return mask
    return mask[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def normalize_shape(mask: np.ndarray, size: int = 64) -> np.ndarray:
    mask = crop_mask(mask)
    if not mask.any():
        return np.zeros((size, size), dtype=bool)
    image = Image.fromarray((mask.astype(np.uint8) * 255), mode="L")
    scale = min((size - 4) / mask.shape[1], (size - 4) / mask.shape[0])
    width = max(1, round(mask.shape[1] * scale))
    height = max(1, round(mask.shape[0] * scale))
    resized = np.asarray(image.resize((width, height), Image.Resampling.NEAREST)) > 0
    canvas = np.zeros((size, size), dtype=bool)
    x = (size - width) // 2
    y = (size - height) // 2
    canvas[y:y + height, x:x + width] = resized
    return canvas


def normalize_glyph(gray: np.ndarray):
    black = gray == 0
    ys, xs = np.where(black)
    if len(xs) == 0:
        return np.zeros((CANVAS, CANVAS), dtype=bool), (0, 0, gray.shape[1], gray.shape[0])
    left, top, right, bottom = int(xs.min()), int(ys.min()), int(xs.max() + 1), int(ys.max() + 1)
    crop = black[top:bottom, left:right]
    scale = min(112 / crop.shape[1], 112 / crop.shape[0])
    width, height = max(1, round(crop.shape[1] * scale)), max(1, round(crop.shape[0] * scale))
    resized = np.asarray(Image.fromarray((crop.astype(np.uint8) * 255), mode="L").resize((width, height), Image.Resampling.NEAREST)) > 0
    canvas = np.zeros((CANVAS, CANVAS), dtype=bool)
    x, y = (CANVAS - width) // 2, (CANVAS - height) // 2
    canvas[y:y + height, x:x + width] = resized
    return canvas, (left, top, right, bottom)


def mask_bounds(mask: np.ndarray):
    ys, xs = np.where(mask)
    if len(xs) == 0:
        return 0, 0, mask.shape[1], mask.shape[0]
    return int(xs.min()), int(ys.min()), int(xs.max() + 1), int(ys.max() + 1)


def patch_from_region(normalized: np.ndarray, region: np.ndarray):
    box = mask_bounds(region)
    x0, y0, x1, y1 = box
    patch = np.asarray(Image.fromarray(((normalized[y0:y1, x0:x1] & region[y0:y1, x0:x1]).astype(np.uint8) * 255), mode="L").resize((PATCH_SIZE, PATCH_SIZE), Image.Resampling.NEAREST)) > 0
    return patch, box


def patch_to_canvas(patch: np.ndarray, box):
    x0, y0, x1, y1 = box
    canvas = np.zeros((CANVAS, CANVAS), dtype=bool)
    resized = np.asarray(Image.fromarray((patch.astype(np.uint8) * 255), mode="L").resize((x1 - x0, y1 - y0), Image.Resampling.NEAREST)) > 0
    canvas[y0:y1, x0:x1] = resized
    return canvas


def normalized_to_original(mask: np.ndarray, crop_box, shape: tuple[int, int]) -> np.ndarray:
    left, top, right, bottom = crop_box
    resized = np.asarray(Image.fromarray((mask.astype(np.uint8) * 255), mode="L").resize((right - left, bottom - top), Image.Resampling.NEAREST)) > 0
    result = np.zeros(shape, dtype=bool)
    result[top:bottom, left:right] = resized
    return result


def component_score(component: np.ndarray, reference: np.ndarray, region: np.ndarray) -> float:
    candidate = normalize_shape(component)
    ref = normalize_shape(reference)
    intersection = float(np.logical_and(candidate, ref).sum())
    union = float(np.logical_or(candidate, ref).sum())
    iou = intersection / union if union else 0.0
    area_ratio = min(component.sum(), reference.sum()) / max(component.sum(), reference.sum())
    ys, xs = np.where(component)
    ry, rx = np.where(reference)
    component_aspect = (xs.max() - xs.min() + 1) / max(1, ys.max() - ys.min() + 1)
    ref_aspect = (rx.max() - rx.min() + 1) / max(1, ry.max() - ry.min() + 1)
    aspect_score = min(component_aspect, ref_aspect) / max(component_aspect, ref_aspect)
    return iou * 0.60 + area_ratio * 0.20 + aspect_score * 0.20


def fit_reference_template(normalized: np.ndarray, region: np.ndarray, reference: np.ndarray, dilate_iterations: int = 2):
    """Fit one binary reference silhouette inside a structure candidate box."""
    x0, y0, x1, y1 = mask_bounds(region)
    target = (normalized[y0:y1, x0:x1].astype(np.uint8) * 255)
    ref_crop = crop_mask(reference)
    if target.size == 0 or ref_crop.size == 0:
        return np.zeros_like(normalized), 0.0
    ref_h, ref_w = ref_crop.shape
    best = None
    # Independent x/y scaling is intentional: the same radical is often
    # squeezed or stretched when it is used as a component.
    for sx in np.linspace(0.40, 1.30, 13):
        for sy in np.linspace(0.45, 1.30, 13):
            width = max(3, round(ref_w * sx))
            height = max(3, round(ref_h * sy))
            if width > target.shape[1] or height > target.shape[0]:
                continue
            template = cv2.resize((ref_crop.astype(np.uint8) * 255), (width, height), interpolation=cv2.INTER_NEAREST)
            result = cv2.matchTemplate(target, template, cv2.TM_CCOEFF_NORMED)
            _, correlation, _, location = cv2.minMaxLoc(result)
            tx, ty = location
            target_window = target[ty:ty + height, tx:tx + width] == 255
            template_black = template == 255
            # Recall alone would accept a tiny fragment.  Penalize target
            # black pixels inside the fitted box that the reference cannot
            # explain; this is what rejects the attached 册 stroke in 删.
            target_area = int(target_window.sum())
            template_area = int(template_black.sum())
            overlap = int((target_window & template_black).sum())
            precision = overlap / max(1, target_area)
            recall = overlap / max(1, template_area)
            # Recall is weighted highest so the fitted result cannot collapse
            # to one convenient stroke of a multi-stroke radical.  Precision
            # still rejects neighboring strokes in the same connected blob.
            score = float(correlation) * 0.20 + precision * 0.30 + recall * 0.50
            if recall >= 0.42 and (best is None or score > best[0]):
                best = (score, tx, ty, width, height, template_black)
    # A historical seal glyph can differ substantially from the independent
    # reference.  Keep the acceptance gate conservative but not so high that
    # a legitimate stretched/squeezed variant becomes entirely unmarked.
    if best is None or best[0] < 0.25:
        return np.zeros_like(normalized), 0.0
    score, tx, ty, width, height, template_black = best
    fitted = np.zeros_like(normalized)
    fitted[y0 + ty:y0 + ty + height, x0 + tx:x0 + tx + width] = template_black
    # Resize/interpolation can leave a reference stroke one normalized pixel
    # away from the target stroke.  A small dilation restores that stroke,
    # while the final intersection with exact-black source pixels prevents
    # white or unrelated anti-alias pixels from being selected.
    if dilate_iterations > 0:
        fitted = binary_dilation(fitted, structure=NEIGHBORHOOD, iterations=dilate_iterations)
    return fitted, score


def geodesic_seed_partition(black: np.ndarray, region: np.ndarray, radical_seed: np.ndarray, side: str) -> np.ndarray:
    """Assign each black pixel to the radical or the neighboring component.

    A connected blob may contain both parts.  Multi-source BFS on the black
    pixel graph keeps strokes continuous while placing the cut at the shortest
    path between the radical seed and the opposite structural boundary.
    """
    candidate = black & region
    radical_seed = radical_seed & candidate
    if not radical_seed.any():
        return np.zeros_like(black)
    ys, xs = np.where(region)
    x0, x1 = int(xs.min()), int(xs.max())
    y0, y1 = int(ys.min()), int(ys.max())
    other = np.zeros_like(black)
    thickness = 3
    if side == "right":
        other[:, max(x0, x0 + thickness):] = False
        other[:, :min(candidate.shape[1], x0 + thickness)] = candidate[:, :min(candidate.shape[1], x0 + thickness)]
    elif side == "left":
        other[:, max(0, x1 - thickness):] = candidate[:, max(0, x1 - thickness):]
    elif side == "bottom":
        other[max(0, y0):min(candidate.shape[0], y0 + thickness), :] = candidate[max(0, y0):min(candidate.shape[0], y0 + thickness), :]
    elif side == "top":
        other[max(0, y1 - thickness):, :] = candidate[max(0, y1 - thickness):, :]
    other &= ~radical_seed
    if not other.any():
        # A standalone radical or an enclosing radical has no opposite seed.
        return candidate if radical_seed.sum() >= 3 else np.zeros_like(black)

    distances = np.full(candidate.shape, -1, dtype=np.int32)
    owners = np.zeros(candidate.shape, dtype=np.uint8)
    queue = deque()
    for y, x in zip(*np.where(radical_seed)):
        distances[y, x] = 0
        owners[y, x] = 1
        queue.append((y, x, 1))
    for y, x in zip(*np.where(other)):
        if distances[y, x] < 0:
            distances[y, x] = 0
            owners[y, x] = 2
            queue.append((y, x, 2))
    for_yx = ((-1, 0), (1, 0), (0, -1), (0, 1))
    while queue:
        y, x, owner = queue.popleft()
        nd = distances[y, x] + 1
        for dy, dx in for_yx:
            ny, nx = y + dy, x + dx
            if 0 <= ny < candidate.shape[0] and 0 <= nx < candidate.shape[1] and candidate[ny, nx]:
                if distances[ny, nx] < 0:
                    distances[ny, nx] = nd
                    owners[ny, nx] = owner
                    queue.append((ny, nx, owner))
    return (owners == 1) & candidate


def choose_connected_component(black: np.ndarray, region: np.ndarray, reference: np.ndarray):
    candidate = black & region
    labels, count = label(candidate, structure=NEIGHBORHOOD)
    options = []
    for index in range(1, count + 1):
        component = labels == index
        if component.sum() < 3:
            continue
        options.append((component_score(component, reference, region), component))
    if options:
        options.sort(key=lambda item: item[0], reverse=True)
        return options[0][1], False, options[0][0]

    # The region can miss a connected radical when IDS and the historical
    # folder disagree.  Still select exactly one connected target component,
    # never a union of disconnected pixels.
    labels, count = label(black, structure=NEIGHBORHOOD)
    options = []
    for index in range(1, count + 1):
        component = labels == index
        overlap = (component & region).sum()
        if overlap == 0:
            continue
        options.append((component_score(component, reference, region) + overlap / max(1, component.sum()) * 0.10, component))
    if options:
        options.sort(key=lambda item: item[0], reverse=True)
        return options[0][1], True, options[0][0]
    return np.zeros_like(black), True, 0.0


def export_image(gray: np.ndarray, red_black: np.ndarray, output: Path) -> int:
    # Keep all original grayscale values.  Only non-black anti-alias pixels
    # adjacent to a selected black component are recolored red.
    red_edge = binary_dilation(red_black, structure=NEIGHBORHOOD, iterations=1) & (gray > 0) & (gray < 255)
    red_candidate = red_black | red_edge
    strength = np.clip((255.0 - gray) / 255.0, 0.0, 1.0)
    rgb = np.repeat(gray[:, :, None], 3, axis=2).astype(np.uint8)
    red = np.stack([255.0 - 35.0 * strength, 255.0 - 215.0 * strength, 255.0 - 215.0 * strength], axis=2).astype(np.uint8)
    rgb[red_candidate] = red[red_candidate]
    output.parent.mkdir(parents=True, exist_ok=True)
    # Open the final path explicitly so Windows handles the Unicode filename
    # without routing it through a shell/code-page conversion.
    if output.exists():
        output.unlink()
    with output.open("wb") as handle:
        Image.fromarray(rgb, mode="RGB").save(handle, format="PNG")
    return int(red_candidate.sum())


def find_reference(root: Path, radical: str) -> np.ndarray:
    path = root / "按部首分类" / radical / "独体" / REFERENCE_FILES[radical]
    if not path.exists():
        path = next((root / "按部首分类" / radical).rglob(REFERENCE_FILES[radical]))
    gray = np.asarray(Image.open(path).convert("L"))
    return gray == 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--input", type=Path, default=None)
    parser.add_argument("--ids", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--dilate", type=int, default=2)
    parser.add_argument("--legacy-consensus", action="store_true")
    parser.add_argument("--consensus-left-right-only", action="store_true")
    args = parser.parse_args()

    root = args.root.resolve()
    input_dir = (args.input or root / "按部首分类").resolve()
    ids_path = (args.ids or root / "data" / "ids.txt").resolve()
    output_dir = (args.output or root / "部首识别").resolve()
    ids = load_ids(ids_path)
    references = {radical: find_reference(root, radical) for radical in TARGETS}
    samples = []
    groups = {}
    fallback_count = 0
    for radical, aliases in TARGETS.items():
        for path in sorted((input_dir / radical).rglob("*.png")):
            char, _ = get_filename_parts(path)
            gray = np.asarray(Image.open(path).convert("L"))
            black = gray == 0
            alternatives = ids.get(char, [])
            sequence = choose_alternative(alternatives)[0] if alternatives else None
            if char in aliases:
                normalized, crop_box = normalize_glyph(gray)
                region = np.ones((CANVAS, CANVAS), dtype=bool)
                outer = False
                used_fallback = False
            else:
                try:
                    tree, consumed = parse_tree(sequence) if sequence else (None, 0)
                    box, outer = locate_target(tree, aliases) if tree is not None and consumed == len(sequence) else (None, False)
                except (IndexError, ValueError):
                    box, outer = None, False
                used_fallback = box is None
                if box is None:
                    box, outer = fallback_box(sequence, radical)
                normalized, crop_box = normalize_glyph(gray)
                region = box_mask((CANVAS, CANVAS), box, outer)
            if outer:
                prototype_input = normalized & region
                patch_box = None
            else:
                prototype_input, patch_box = patch_from_region(normalized, region)
            structure_key = sequence[0] if sequence and sequence[0] in IDC else "独体"
            sample = {
                "radical": radical,
                "aliases": aliases,
                "path": path,
                "gray": gray,
                "black": black,
                "normalized": normalized,
                "crop_box": crop_box,
                "region": region,
                "prototype_input": prototype_input,
                "patch_box": patch_box,
                "outer": outer,
                "sequence": sequence,
                "fallback": used_fallback,
                "structure": structure_key,
            }
            samples.append(sample)
            groups.setdefault((radical, structure_key, outer), []).append(sample)
            fallback_count += int(used_fallback)

    if args.legacy_consensus:
        prototypes = {}
        for key, members in groups.items():
            stack = np.stack([member["prototype_input"] for member in members]).astype(np.float32)
            occupancy = stack.mean(axis=0)
            threshold = 0.52 if len(members) >= 12 else 0.40
            prototype = occupancy >= threshold
            if not prototype.any():
                prototype = members[0]["prototype_input"]
            prototypes[key] = prototype
        total = no_match = red_pixels = 0
        for sample in samples:
            direct_cell = False
            use_consensus = not args.consensus_left_right_only or sample["structure"] in {"⿰", "⿲"}
            if use_consensus:
                prototype = prototypes[(sample["radical"], sample["structure"], sample["outer"])]
                if sample["outer"]:
                    support = prototype & sample["region"]
                else:
                    support = patch_to_canvas(prototype, sample["patch_box"]) & sample["region"]
                support_original = normalized_to_original(support, sample["crop_box"], sample["gray"].shape)
                red_black = sample["black"] & support_original
            else:
                if not sample["outer"] and sample["structure"] != "⿰":
                    direct_cell = True
                    # In vertical structures the IDS leaf box is already the
                    # complete radical cell; consensus/template matching
                    # tends to reduce its multi-stroke shape to fragments.
                    support_original = normalized_to_original(sample["region"], sample["crop_box"], sample["gray"].shape)
                else:
                    fitted, _ = fit_reference_template(sample["normalized"], sample["region"], references[sample["radical"]], args.dilate)
                    support_original = normalized_to_original(fitted, sample["crop_box"], sample["gray"].shape)
                red_black = sample["black"] & support_original
            if not red_black.any() and sample["black"].any():
                region_original = normalized_to_original(sample["region"], sample["crop_box"], sample["gray"].shape)
                red_black, _, _ = choose_connected_component(sample["black"], region_original, references[sample["radical"]])
            if not red_black.any():
                no_match += 1
            # The historical version retained the largest connected colored
            # component after adding anti-aliased edge pixels.
            legacy_candidate = red_black | (binary_dilation(red_black, structure=NEIGHBORHOOD) & (sample["gray"] > 0) & (sample["gray"] < 255))
            labels, count = label(legacy_candidate, structure=NEIGHBORHOOD)
            if count and not direct_cell:
                ranked = sorted(
                    ((int(((labels == i) & red_black).sum()), int((labels == i).sum()), i) for i in range(1, count + 1)),
                    reverse=True,
                )
                red_black = labels == ranked[0][2]
            red_pixels += export_image(sample["gray"], red_black, output_dir / sample["radical"] / sample["path"].name)
            total += 1
        print(f"total={total} groups={len(groups)} prototypes={len(prototypes)} fallback_structure={fallback_count} no_match={no_match} red_pixels={red_pixels}")
        return

    total = no_match = red_pixels = 0
    for sample in samples:
        if sample["radical"] in TARGETS and get_filename_parts(sample["path"])[0] in TARGETS[sample["radical"]]:
            red_black = sample["black"]
            fit_score = 1.0
        else:
            fitted, fit_score = fit_reference_template(
                sample["normalized"], sample["region"], references[sample["radical"]], args.dilate
            )
            # This is the earlier version requested by the user: fit the
            # transformed binary reference, slightly close its strokes, and
            # intersect only with exact-black pixels from the source glyph.
            support_original = normalized_to_original(fitted, sample["crop_box"], sample["gray"].shape)
            red_black = sample["black"] & support_original
        if not red_black.any():
            no_match += 1
        red_pixels += export_image(sample["gray"], red_black, output_dir / sample["radical"] / sample["path"].name)
        total += 1

    print(
        f"total={total} groups={len(groups)} "
        f"fallback_structure={fallback_count} no_match={no_match} red_pixels={red_pixels}"
    )


if __name__ == "__main__":
    main()
