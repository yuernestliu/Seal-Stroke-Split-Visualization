"""
从 glyphs.js.bak 出发，把 28 个字的 segments + lengths 按 glyphs.js 里的新顺序
in-place 替换，写到 glyphs.js。每个数组元素独占一行（仿 .bak 原格式）。
"""
import json, re
from pathlib import Path

ROOT = Path(r"c:\Users\zzy\Pictures\作业\Seal-Stroke-Split-Visualization-main")
BAK = ROOT / "data" / "glyphs.js.bak"
NEW = ROOT / "data" / "glyphs.js"

# ---------- 加载 ----------
def parse_js(text):
    m = re.search(r"window\.GLYPH_DATA\s*=\s*", text)
    brace = text.index("{", m.end())
    depth = 0; end = -1
    for i in range(brace, len(text)):
        c = text[i]
        if c == "{": depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0: end = i; break
    return json.loads(text[brace:end+1])

data_new = parse_js(NEW.read_text(encoding="utf-8"))
new_by_id = {g["id"]: g for g in data_new["glyphs"]}
old_text = BAK.read_text(encoding="utf-8")
data_old = parse_js(old_text)
old_by_id = {g["id"]: g for g in data_old["glyphs"]}

# ---------- 找需要改的字 ----------
def seg_fp(seg):
    pts = seg["points"]
    return (tuple(pts[0]), tuple(pts[-1]), len(pts))
changed_ids = []
for gid in old_by_id:
    o = [seg_fp(s) for s in old_by_id[gid]["segments"]]
    n = [seg_fp(s) for s in new_by_id[gid]["segments"]]
    if o != n:
        changed_ids.append(gid)
print(f"需要 in-place 替换的字数: {len(changed_ids)}")

# ---------- 格式工具：每元素独占一行 ----------
def find_bracket_block(text, start):
    assert text[start] == "["
    i = start + 1; depth = 1; in_str = False; esc = False
    while i < len(text):
        c = text[i]
        if in_str:
            if esc: esc = False
            elif c == "\\": esc = True
            elif c == '"': in_str = False
        else:
            if c == '"': in_str = True
            elif c == "[": depth += 1
            elif c == "]":
                depth -= 1
                if depth == 0: return start, i
        i += 1
    raise ValueError("bracket not closed")

def reformat_pure_array(compact_json, indent_spaces):
    """纯数字/字符串数组 → 每元素一行"""
    arr = json.loads(compact_json)
    pad = " " * indent_spaces
    elem_pad = " " * (indent_spaces + 2)  # .bak 里是 2 个空格缩进
    lines = [f"["]
    for i, x in enumerate(arr):
        line = f"{elem_pad}{json.dumps(x, ensure_ascii=False)}"
        if i < len(arr) - 1:
            line += ","
        lines.append(line)
    lines.append(f"{pad}]")
    return "\n".join(lines)

def reformat_points_array(compact_json, indent_spaces):
    """[[y,x], ...] → 每个 [y,x] 占 4 行（仿 .bak）"""
    arr = json.loads(compact_json)
    pad = " " * indent_spaces        # ']' 所在缩进
    open_pad = " " * (indent_spaces) # '[' 所在缩进
    elem_pad = " " * (indent_spaces + 2)  # 每个 [y,x] 开始缩进
    lines = [f"{open_pad}["]
    for i, p in enumerate(arr):
        lines.append(f"{elem_pad}[")
        lines.append(f"{elem_pad}  {p[0]},")
        lines.append(f"{elem_pad}  {p[1]}")
        lines.append(f"{elem_pad}]" + ("" if i == len(arr) - 1 else ","))
    lines.append(f"{pad}]")
    return "\n".join(lines)

def reformat_segment_object(seg, indent_spaces):
    """单个 segment 对象 → 5 行格式"""
    pad = " " * indent_spaces  # '{' 所在缩进
    field_pad = " " * (indent_spaces + 2)  # 字段缩进
    pts_pad = indent_spaces + 4  # "points": 所在缩进
    pts_compact = "[" + ",".join(f"[{p[0]},{p[1]}]" for p in seg["points"]) + "]"
    pts_5 = reformat_points_array(pts_compact, pts_pad)
    lines = [
        f"{pad}{{",
        f"{field_pad}\"id\": {seg['id']},",
        f"{field_pad}\"pointCount\": {seg['pointCount']},",
        f"{field_pad}\"pixelCount\": {seg['pixelCount']},",
        f"{field_pad}\"points\": {pts_5}",
        f"{pad}}}",
    ]
    return "\n".join(lines)

def reformat_segments_array(compact_json, indent_spaces):
    """segments 数组 → 每个对象 6 行（含 [{] 6 行 ..]）"""
    arr = json.loads(compact_json)
    pad = " " * indent_spaces  # '[' ']' 缩进
    obj_pad = indent_spaces + 2  # 每个 '{' '{' 缩进
    lines = [f"{pad}["]
    for i, s in enumerate(arr):
        obj_block = reformat_segment_object(s, obj_pad)
        if i < len(arr) - 1:
            obj_block = obj_block[:-1] + "},"  # 最后一行 } 改成 },
        lines.append(obj_block)
    lines.append(f"{pad}]")
    return "\n".join(lines)

# ---------- in-place 替换 ----------
out = old_text
for gid in changed_ids:
    pat = re.compile(r'"id"\s*:\s*"' + re.escape(gid) + r'"')
    m_id = pat.search(out)
    if not m_id: print(f"  !! 找不到 {gid}"); continue
    # lengths
    m_len = re.search(r'"lengths"\s*:\s*\[', out[m_id.end():])
    if not m_len: print(f"  !! {gid} 找不到 lengths"); continue
    len_brace = m_id.end() + m_len.end() - 1
    len_s, len_e = find_bracket_block(out, len_brace)
    new_len_compact = "[" + ",".join(str(x) for x in new_by_id[gid]["metrics"]["lengths"]) + "]"
    new_len_5 = reformat_pure_array(new_len_compact, 8)
    # segments
    m_seg = re.search(r'"segments"\s*:\s*\[', out[m_id.end():])
    if not m_seg: print(f"  !! {gid} 找不到 segments"); continue
    seg_brace = m_id.end() + m_seg.end() - 1
    seg_s, seg_e = find_bracket_block(out, seg_brace)
    new_seg_compact = "[" + ",".join(json.dumps(s, ensure_ascii=False) for s in new_by_id[gid]["segments"]) + "]"
    new_seg_5 = reformat_segments_array(new_seg_compact, 8)
    # 从后往前替换
    out = out[:seg_s] + new_seg_5 + out[seg_e+1:]
    out = out[:len_s] + new_len_5 + out[len_e+1:]

# ---------- 写回 ----------
out_path = ROOT / "data" / "glyphs.js"
out_path.write_text(out, encoding="utf-8")
print(f"\n已写回: {out_path}")
print(f"  js  大小: {out_path.stat().st_size} 字节")
print(f"  bak 大小: {BAK.stat().st_size} 字节")