"""Trial component identification by matching independent radical/component glyphs."""
from __future__ import annotations

import csv
import argparse
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from scipy.ndimage import label, distance_transform_edt

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from build_component_csvs import get_filename_parts, load_ids, choose_alternative  # noqa: E402
from identify_radical_images import IDC, contains_target, locate_target, parse_tree  # noqa: E402

COLORS = [(220, 45, 45), (45, 90, 220), (35, 160, 70), (210, 130, 25), (150, 55, 180),
          (30, 140, 160), (140, 90, 40), (200, 80, 140), (120, 140, 30), (90, 110, 150)]
ALIASES = {"刀": {"刀", "刂"}, "心": {"心", "忄", "⺗"}}


def load_rows(root: Path, radical: str):
    rows = {}
    with (root / "部件组成" / f"{radical}.csv").open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            rows[row["文件名"]] = row
    return rows


def find_template(root: Path, component: str):
    aliases = ALIASES.get(component, {component})
    candidates = []
    # A written variant such as 刂 uses the canonical 刀 radical folder.
    # Otherwise the lookup misses the template and falls back to the whole
    # IDS region, making the connected-domain count constraint ineffective.
    folder_name = next(
        (canonical for canonical, names in ALIASES.items() if component in names),
        component,
    )
    folder = root / "按部首分类" / folder_name
    if folder.exists():
        for p in folder.rglob("*.png"):
            char, _ = get_filename_parts(p)
            if char in aliases:
                candidates.append((0 if "独体" in p.parts else 1, p))
    if not candidates:
        return None, 0
    candidates.sort(key=lambda x: (x[0], str(x[1])))
    gray = np.asarray(Image.open(candidates[0][1]).convert("L"))
    mask = gray == 0
    ys, xs = np.where(mask)
    cropped = mask[ys.min():ys.max()+1, xs.min():xs.max()+1] if len(xs) else None
    if cropped is None:
        return None, 0
    _, count = label(cropped, structure=np.ones((3, 3), dtype=np.uint8))
    return cropped, int(count)


def child_box_for_component(sequence: str | None, component: str):
    if not sequence or sequence[0] not in IDC:
        return None
    try:
        tree, consumed = parse_tree(sequence)
    except (IndexError, ValueError):
        return None
    if consumed != len(sequence):
        return None
    aliases = ALIASES.get(component, {component})
    box, _ = locate_target(tree, aliases)
    return box


def box_mask(shape, box):
    h, w = shape
    if box is None:
        return np.ones(shape, dtype=bool)
    x0, y0, x1, y1 = box
    yy, xx = np.mgrid[0:h, 0:w]
    nx = xx / max(1, w - 1)
    ny = yy / max(1, h - 1)
    return (nx >= x0) & (nx <= x1) & (ny >= y0) & (ny <= y1)


def fit_template(glyph: np.ndarray, template: np.ndarray, region: np.ndarray):
    ys, xs = np.where(region)
    if not len(xs):
        return np.zeros_like(glyph), -1.0
    x0, x1, y0, y1 = xs.min(), xs.max()+1, ys.min(), ys.max()+1
    target = (glyph[y0:y1, x0:x1].astype(np.uint8) * 255)
    th, tw = template.shape
    best = None
    for sx in np.linspace(0.45, 1.25, 12):
        for sy in np.linspace(0.45, 1.25, 12):
            w, h = max(3, round(tw*sx)), max(3, round(th*sy))
            if w > target.shape[1] or h > target.shape[0]:
                continue
            temp = cv2.resize((template.astype(np.uint8)*255), (w, h), interpolation=cv2.INTER_NEAREST)
            result = cv2.matchTemplate(target, temp, cv2.TM_CCOEFF_NORMED)
            _, corr, _, loc = cv2.minMaxLoc(result)
            tx, ty = loc
            tblack = temp == 255
            gblack = target[ty:ty+h, tx:tx+w] == 255
            overlap = int((tblack & gblack).sum())
            precision = overlap / max(1, int(gblack.sum()))
            recall = overlap / max(1, int(tblack.sum()))
            score = float(corr)*0.25 + precision*0.25 + recall*0.50
            if best is None or score > best[0]:
                best = (score, tx, ty, w, h, tblack)
    if best is None:
        return np.zeros_like(glyph), -1.0
    score, tx, ty, w, h, tblack = best
    out = np.zeros_like(glyph)
    out[y0+ty:y0+ty+h, x0+tx:x0+tx+w] = tblack
    return out & glyph, score


def save_colored(gray, masks, expected_counts, path):
    # Assign each original black 8-connected component to exactly one
    # component mask.  This prevents one connected glyph domain from being
    # split across two template colors.
    black = gray == 0
    labels, count = label(black, structure=np.ones((3, 3), dtype=np.uint8))
    owners = np.full(count + 1, -1, dtype=np.int32)
    candidates = []
    for index, mask in enumerate(masks):
        overlaps = []
        for component_index in range(1, count + 1):
            amount = int(((labels == component_index) & mask).sum())
            if amount > 0:
                overlaps.append((amount, component_index))
        overlaps.sort(reverse=True)
        expected = expected_counts[index]
        # A component template with N black domains may claim at most N target
        # black domains.  Extra touching domains are rejected as a bad match.
        if expected > 0:
            if len(overlaps) != expected:
                # Domain-count mismatch means this template placement is not
                # trustworthy; do not assign any of its candidate domains.
                overlaps = []
            else:
                overlaps = overlaps[:expected]
        candidates.append(overlaps)
    for index, overlaps in enumerate(candidates):
        for amount, component_index in overlaps:
            if owners[component_index] < 0:
                owners[component_index] = index
            else:
                old = owners[component_index]
                old_amount = next((a for a, c in candidates[old] if c == component_index), -1)
                if amount > old_amount:
                    owners[component_index] = index

    rgb = np.repeat(gray[:, :, None], 3, axis=2).astype(np.uint8)
    # Every selected black pixel receives its component color.
    for index, color in enumerate(COLORS):
        rgb[(owners[labels] == index) & black] = color

    # For non-white pixels removed by binarization, inherit the color of the
    # nearest black connected domain instead of reverting to black/grayscale.
    _, nearest = distance_transform_edt(~black, return_indices=True)
    nearest_owner = owners[labels[tuple(nearest)]]
    gray_foreground = (gray > 0) & (gray < 255) & (nearest_owner >= 0)
    for index, color in enumerate(COLORS):
        rgb[gray_foreground & (nearest_owner == index)] = color
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        Image.fromarray(rgb, mode="RGB").save(f, format="PNG")
    # Per-component number of original black domains it ended up owning;
    # 0 means the domain-count constraint rejected the placement (or the
    # fallback mask touched nothing usable).  Used for the run log.
    assigned = [0] * len(masks)
    for component_index in range(1, count + 1):
        owner = owners[component_index]
        if owner >= 0:
            assigned[owner] += 1
    return assigned


def main():
    # Windows consoles may default to GBK and fail on uncommon radical
    # characters when reporting progress.  Keep output UTF-8 so a long run
    # cannot stop after an otherwise successful folder.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--only", nargs="*", default=None,
                        help="只处理这些部首；缺省时处理 按部首分类 下除 --skip 外全部")
    parser.add_argument("--skip", nargs="*", default=("刀", "心"),
                        help="已完成的部首，缺省跳过")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    ids = load_ids(root / "data" / "ids.txt")
    output_root = args.output or (root / "按模板识别")
    log_rows = []
    folders = sorted(p.name for p in (root / "按部首分类").iterdir() if p.is_dir())
    for radical in folders:
        if args.only and radical not in args.only:
            continue
        if not args.only and radical in args.skip:
            continue
        if not (root / "部件组成" / f"{radical}.csv").exists():
            print(f"警告: {radical} 缺少 部件组成/{radical}.csv，跳过")
            continue
        rows = load_rows(root, radical)
        source = root / "按部首分类" / radical
        output = output_root / radical
        for path in sorted(source.rglob("*.png")):
            row = rows.get(path.name)
            if not row:
                continue
            # Template lookup and component matching use normalized component
            # names, so variants such as 刂 are handled as 刀 directly.
            components = [x for x in row["归一部件"].split("；") if x]
            gray = np.asarray(Image.open(path).convert("L"))
            glyph = gray == 0
            sequence = choose_alternative(ids.get(row["字"], []))[0] if ids.get(row["字"]) else None
            masks = []
            expected_counts = []
            per_image_meta = []
            for component in components:
                template, template_count = find_template(root, component)
                region = box_mask(glyph.shape, None)
                if sequence:
                    region = box_mask(glyph.shape, child_box_for_component(sequence, component))
                if template is not None:
                    mask, score = fit_template(glyph, template, region)
                else:
                    mask, score = np.zeros_like(glyph), -1.0
                if not mask.any():
                    mask = glyph & region
                masks.append(mask)
                expected_counts.append(template_count)
                per_image_meta.append((component, template is not None, template_count))
            # Evaluate every template against the same original glyph mask.
            # Do not subtract earlier masks here: doing so can hide a second
            # touched connected domain and make a domain-count mismatch appear
            # valid merely because another component was processed first.
            assigned = save_colored(gray, masks, expected_counts,
                                    output / path.relative_to(source))
            for (component, found, template_count), got in zip(per_image_meta, assigned):
                log_rows.append([radical, path.name, row["字"], component,
                                 "是" if found else "否", template_count, got,
                                 row["归一部件"]])
        print(f"radical={radical} output={output}")
    log_path = output_root / "_运行日志.csv"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["部首", "文件名", "字", "部件", "模板找到",
                         "模板连通域数", "实际分配连通域数", "归一部件"])
        writer.writerows(log_rows)
    print(f"日志: {log_path}（{len(log_rows)} 行）")


if __name__ == "__main__":
    main()
