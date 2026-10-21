"""Generate one UTF-8-BOM/CRLF component CSV per top-level radical folder.

The decomposition source is cjkvi-ids' ids.txt.  For each character, the
first [G]-labelled IDS alternative is preferred (otherwise the first
alternative is selected) and recursively flattened to its leaf components in
writing order.  This is a modern glyph decomposition, not an etymological
analysis and not an image-region segmentation.
"""

from __future__ import annotations

import argparse
import csv
import re
from collections import Counter
from pathlib import Path


IDC = set("⿰⿱⿲⿳⿴⿵⿶⿷⿸⿹⿺⿻")
IDC_NAME = {
    "⿰": "左右",
    "⿱": "上下",
    "⿲": "左中右",
    "⿳": "上中下",
    "⿴": "包围",
    "⿵": "包围",
    "⿶": "包围",
    "⿷": "包围",
    "⿸": "包围",
    "⿹": "包围",
    "⿺": "包围",
    "⿻": "重叠",
}
ARITY = {op: 3 if op in {"⿲", "⿳"} else 2 for op in IDC}

VARIANT_MAP = {
    "刂": "刀",
    "亻": "人",
    "氵": "水",
    "灬": "火",
    "忄": "心",
    "扌": "手",
    "牜": "牛",
    "饣": "食",
}

NAME_RE = re.compile(r"^(?P<id>\d+)_(?P<char>.+?)_Z_(?P<source>.+)\.png$")
ANNOTATION_RE = re.compile(r"\[[^\]]*\]")
STROKE_LEVEL_PARTS = set("一丨丿丶乀亅乚乛乙㇀㇁㇂フ𠃌𠃍𠃎𠃊") | {"丷", "二"}
CIRCLED_DIGITS = {chr(codepoint) for codepoint in range(0x2460, 0x2474)}
STROKE_LEVEL_PARTS |= CIRCLED_DIGITS


def load_ids(path: Path) -> dict[str, list[tuple[str, bool]]]:
    result: dict[str, list[tuple[str, bool]]] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw or raw.startswith("#"):
            continue
        fields = raw.split("\t")
        if len(fields) < 2:
            continue
        char = fields[1]
        if not char:
            continue
        candidates: list[tuple[str, bool]] = []
        for field in fields[2:]:
            has_g_label = "[G]" in field
            field = ANNOTATION_RE.sub("", field).strip()
            if field and any(op in field for op in IDC):
                candidates.append((field, has_g_label))
        result[char] = candidates
    return result


def choose_alternative(alternatives: list[tuple[str, bool]]) -> tuple[str, int]:
    """Return the preferred IDS and its original candidate index."""
    for index, (sequence, has_g_label) in enumerate(alternatives):
        if has_g_label:
            return sequence, index
    return alternatives[0][0], 0


def parse_ids(sequence: str, index: int = 0, position: str | None = None) -> tuple[list[tuple[str, str | None]], int]:
    if index >= len(sequence):
        return [], index
    token = sequence[index]
    if token not in IDC:
        return [(token, position)], index + 1
    leaves: list[tuple[str, str | None]] = []
    child_count = ARITY[token]
    for child_index in range(child_count):
        child_position = position
        if token == "⿰":
            child_position = "left" if child_index == 0 else "right"
        child, index = parse_ids(sequence, index + 1 if child_index == 0 else index, child_position)
        leaves.extend(child)
    return leaves, index


def flatten(sequence: str) -> tuple[list[tuple[str, str | None]], str]:
    root = sequence[0]
    leaves, consumed = parse_ids(sequence)
    if consumed != len(sequence):
        # Keep the result useful while flagging malformed/non-standard IDS.
        return leaves, "含未编码部件"
    return leaves, ""


def normalize(component: str, position: str | None) -> str:
    if component in {"阝", "⻖"}:
        if position == "left":
            return "阜"
        if position == "right":
            return "邑"
    return VARIANT_MAP.get(component, component)


def structure(sequence: str | None) -> str:
    if not sequence or sequence[0] not in IDC:
        return "独体"
    return IDC_NAME.get(sequence[0], "复合")


def get_filename_parts(path: Path) -> tuple[str, str]:
    match = NAME_RE.match(path.name)
    if not match:
        return "", ""
    return match.group("char"), match.group("source")


def make_row(
    path: Path,
    input_dir: Path,
    ids: dict[str, list[tuple[str, bool]]],
) -> tuple[list[str], bool, bool, bool, int]:
    char, _ = get_filename_parts(path)
    note = ""
    alternatives = ids.get(char)
    g_changed = 0
    if alternatives:
        chosen, chosen_index = choose_alternative(alternatives)
        g_changed = int(chosen_index > 0)
        leaves, flatten_note = flatten(chosen)
        parts = [component for component, _ in leaves]
        normalized = [normalize(component, position) for component, position in leaves]
        note = flatten_note
        if not parts:
            parts = [char]
            normalized = [char]
            note = "含未编码部件"
        is_compound = True
    else:
        # An IDS entry may exist as an atomic character but is intentionally
        # not retained by load_ids.  It is still a valid independent glyph.
        known = char in ids
        parts = [char]
        normalized = [char]
        note = "" if known else "IDS缺失"
        is_compound = False

    if len(parts) > 1 and all(part in STROKE_LEVEL_PARTS for part in parts):
        structure_name = "独体"
        parts = [char]
        normalized = [char]
        note = "IDS仅笔画级拆解，按独体处理"
        stroke_only_override = True
    else:
        structure_name = structure(chosen) if alternatives else "独体"
        stroke_only_override = False
        if any(part in CIRCLED_DIGITS for part in parts) and note != "IDS仅笔画级拆解，按独体处理":
            note = "含未编码部件"

    # The first-level operator is the modern glyph structure.  For atomic or
    # unavailable data, 独体 is the honest fallback.
    row = [
        path.name,
        char,
        structure_name,
        "；".join(parts),
        "；".join(normalized),
        note,
    ]
    mixed_circled = int(any(part in CIRCLED_DIGITS for part in parts) and not stroke_only_override)
    return row, is_compound, stroke_only_override, bool(mixed_circled), g_changed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--input", type=Path, default=None)
    parser.add_argument("--ids", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    root = args.root.resolve()
    input_dir = (args.input or root / "按部首分类").resolve()
    ids_path = (args.ids or root / "data" / "ids.txt").resolve()
    output_dir = (args.output or root / "部件组成").resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    ids = load_ids(ids_path)
    groups: dict[str, list[Path]] = {}
    for path in sorted(input_dir.rglob("*.png")):
        relative = path.relative_to(input_dir)
        if not relative.parts:
            continue
        groups.setdefault(relative.parts[0], []).append(path)

    header = ["文件名", "字", "结构", "部件组成", "归一部件", "备注"]
    total = 0
    missing = 0
    independent = 0
    stroke_only_hits = 0
    mixed_circled_rows = 0
    g_changed_chars = 0
    group_counts: Counter[str] = Counter()
    for group, paths in sorted(groups.items()):
        out_path = output_dir / f"{group}.csv"
        with out_path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle, lineterminator="\r\n")
            writer.writerow(header)
            for path in paths:
                row, compound, stroke_only_override, mixed_circled, g_changed = make_row(path, input_dir, ids)
                writer.writerow(row)
                total += 1
                group_counts[group] += 1
                if row[-1] == "IDS缺失":
                    missing += 1
                if row[2] == "独体":
                    independent += 1
                stroke_only_hits += int(stroke_only_override)
                mixed_circled_rows += int(mixed_circled)
                g_changed_chars += g_changed

    summary = output_dir / "_汇总.txt"
    summary.write_text(
        "\n".join([
            f"部首 CSV 数量：{len(groups)}",
            f"字图记录数量：{total}",
            f"IDS 缺失数量：{missing}",
            f"独体字数量：{independent}",
            f"IDS 仅笔画级拆解改判独体数量：{stroke_only_hits}",
            f"含圈数字的混合行数量：{mixed_circled_rows}",
            f"[G] 优先改动字数：{g_changed_chars}",
            f"IDS 来源：{ids_path.as_posix()}",
        ]) + "\n",
        encoding="utf-8",
    )
    print(
        f"groups={len(groups)} records={total} missing={missing} "
        f"independent={independent} stroke_only={stroke_only_hits} "
        f"mixed_circled={mixed_circled_rows} g_changed={g_changed_chars}"
    )


if __name__ == "__main__":
    main()
