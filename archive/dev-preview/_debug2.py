import sys
from pathlib import Path
ROOT = Path(r"c:\Users\zzy\Pictures\作业\Seal-Stroke-Split-Visualization-main")
sys.path.insert(0, str(ROOT / "拆笔画修改" / "拆笔画_修改" / "src"))

import json, re
text = open(ROOT / "data" / "glyphs.js.bak", encoding="utf-8").read()
text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
start = text.index("window.GLYPH_DATA")
eq = text.index("=", start)
brace = text.index("{", eq)
depth = 0
end = -1
for i in range(brace, len(text)):
    c = text[i]
    if c == "{":
        depth += 1
    elif c == "}":
        depth -= 1
        if depth == 0:
            end = i
            break
body = text[brace:end+1]
d = json.loads(body)
g = next(x for x in d["glyphs"] if x["id"] == "08166_否_Z_說文‧不部")

from seal_stroke_split.stroke_ordering import (
    order_strokes, cluster_components, sort_components,
    sort_strokes_within_component, _intersection_count, _y_range,
    segment_center, _compare_strokes
)
from seal_stroke_split.types import StrokeSegment

seg_objs = [
    StrokeSegment(stroke_id=s["id"], points=[tuple(p) for p in s["points"]])
    for s in g["segments"]
]
point_sets = [set(seg.points) for seg in seg_objs]

# 1. 部件聚类
print("=== 部件聚类 ===")
comps = cluster_components(seg_objs)
for i, c in enumerate(comps):
    print("  部件", i, ": 笔画 idx =", c, "  对应 stroke_id =", [seg_objs[j].stroke_id for j in c])

# 2. 部件排序
print("\n=== 部件排序（按重心）===")
sorted_comps = sort_components(comps, seg_objs)
for c in sorted_comps:
    sids = [seg_objs[j].stroke_id for j in c]
    all_ys = [p[0] for j in c for p in seg_objs[j].points]
    all_xs = [p[1] for j in c for p in seg_objs[j].points]
    print("  部件 stroke_id={}  cy={:.1f}  cx={:.1f}  yrange=({},{})  xrange=({},{})".format(
        sids, sum(all_ys)/len(all_ys), sum(all_xs)/len(all_xs),
        min(all_ys), max(all_ys), min(all_xs), max(all_xs)))

# 3. 部件内排序
print("\n=== 部件内排序 ===")
final_indices = []
for c in sorted_comps:
    inner = sort_strokes_within_component(c, seg_objs, point_sets)
    print("  部件 stroke_id={} -> 内部排序后 idx={}  对应 stroke_id={}".format(
        [seg_objs[j].stroke_id for j in c], inner, [seg_objs[j].stroke_id for j in inner]))
    final_indices.extend(inner)

print("\n=== 最终顺序 ===")
print("  笔画 idx 顺序:", final_indices)
print("  对应 stroke_id 顺序:", [seg_objs[i].stroke_id for i in final_indices])
