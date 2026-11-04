"""
两阶段 in-place 替换：
1. 从 glyphs.js.bak（合法 JS JSON）读旧数据，调用 stroke_ordering.order_strokes
   跑出每个字的新顺序，保存为紧凑临时 JSON _new_data.json
2. 从临时文件读新数据，从 .bak 读原文本，在原文本上只改 28 个字的 segments + lengths
   写出为 glyphs.js（保持 5 行缩进格式，每个元素独占一行，合法 JSON）
"""
import sys, json, re
from pathlib import Path

ROOT = Path(r"c:\Users\zzy\Pictures\作业\Seal-Stroke-Split-Visualization-main")
BAK = ROOT / "data" / "glyphs.js.bak"
OUT = ROOT / "data" / "glyphs.js"
TMP = ROOT / "scripts" / "_preview" / "_new_data.json"
ORDERING = ROOT / "拆笔画修改" / "拆笔画_修改" / "src" / "seal_stroke_split" / "stroke_ordering.py"

# ---------- 加载 ----------
sys.path.insert(0, str(ORDERING.parent))
# 不让模块顶层执行太多，stroke_ordering.py 顶部应该只 import，不执行
sys.path.insert(0, str(ROOT / "拆笔画修改" / "拆笔画_修改" / "src"))
sys.path.insert(0, str(ROOT / "拆笔画修改" / "拆笔画_修改"))

# 先尝试包导入
try:
    from seal_stroke_split.stroke_ordering import order_strokes
except Exception as e:
    print(f"包导入失败 {e}，尝试 path 导入")
    import importlib.util
    spec = importlib.util.spec_from_file_location("stroke_ordering", ORDERING)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["stroke_ordering"] = mod
    spec.loader.exec_module(mod)
    order_strokes = mod.order_strokes

print(f"stroke_ordering 模块来自: {ORDERING}")

# 解析 .bak（合法 JS）
text_bak = BAK.read_text(encoding="utf-8")
m = re.search(r"window\.GLYPH_DATA\s*=\s*", text_bak)
brace = text_bak.index("{", m.end())
depth = 0; end = -1; in_str = False; esc = False
for i in range(brace, len(text_bak)):
    c = text_bak[i]
    if in_str:
        if esc: esc = False
        elif c == chr(92): esc = True
        elif c == chr(34): in_str = False
    else:
        if c == chr(34): in_str = True
        elif c == "{": depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0: end = i; break
data_old = json.loads(text_bak[brace:end+1])

# ---------- 对每个字跑 order_strokes，存临时文件 ----------
new_glyphs = []
for g in data_old["glyphs"]:
    stroke_masks = []  # stroke_ordering 需要 stroke_masks 但不真正用其值
    segments = [dict(s) for s in g["segments"]]  # 复制
    segments_for_api = []
    for s in segments:
        # StrokeSegment dataclass? 让我们看看类型
        pass
    # 直接调 order_strokes：参数 (stroke_masks, segments)
    # segments 里每个 dict 至少要有 points 字段
    sorted_masks, sorted_segs = order_strokes(stroke_masks=stroke_masks, segments=segments)
    # sorted_segs 是 StrokeSegment 对象列表，但应该有 stroke_id 重打
    # 转回标准 dict
    new_segs = []
    for s in sorted_segs:
        if hasattr(s, '__dict__') or hasattr(s, 'stroke_id'):
            # dataclass 对象
            new_segs.append({
                "id": getattr(s, 'stroke_id', 0),
                "pointCount": len(getattr(s, 'points', [])),
                "pixelCount": 0,  # 不重要，stroke_ordering 不涉及
                "points": list(getattr(s, 'points', [])),
            })
        else:
            new_segs.append(s)
    new_g = dict(g)
    new_g["segments"] = new_segs
    new_glyphs.append(new_g)

# 写出紧凑临时 JSON
out_data = {
    "dataset": data_old["dataset"],
    "glyphs": new_glyphs,
}
TMP.write_text(json.dumps(out_data, ensure_ascii=False), encoding="utf-8")
print(f"新数据已存: {TMP}")

# ---------- 找需要改的字 ----------
def seg_fp(seg):
    pts = seg["points"]
    return (tuple(pts[0]), tuple(pts[-1]), len(pts))
old_by_id = {g["id"]: g for g in data_old["glyphs"]}
new_by_id = {g["id"]: g for g in new_glyphs}
changed_ids = []
for gid in old_by_id:
    o = [seg_fp(s) for s in old_by_id[gid]["segments"]]
    n = [seg_fp(s) for s in new_by_id[gid]["segments"]]
    if o != n:
        changed_ids.append(gid)
print(f"需要 in-place 替换的字数: {len(changed_ids)}")