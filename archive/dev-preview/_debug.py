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

from seal_stroke_split.stroke_ordering import order_strokes
from seal_stroke_split.types import StrokeSegment

print("原 segments 顺序:")
for s in g["segments"]:
    pts = s["points"]
    print("  id={} ymin={} xmin={} pc={}".format(
        s["id"], min(p[0] for p in pts), min(p[1] for p in pts), s["pointCount"]))

seg_objs = [
    StrokeSegment(stroke_id=s["id"], points=[tuple(p) for p in s["points"]])
    for s in g["segments"]
]
print("\nseg_objs 数:", len(seg_objs))
for s in seg_objs:
    print("  stroke_id={} points 类型={} 前 3 点={}".format(
        s.stroke_id, type(s.points[0]), s.points[:3]))

# 调用 order_strokes
print("\n调用 order_strokes ...")
try:
    fake_masks = [None] * len(seg_objs)
    sorted_masks, sorted_segs = order_strokes(fake_masks, seg_objs)
    print("返回类型:", type(sorted_masks), type(sorted_segs))
    print("返回长度:", len(sorted_masks), len(sorted_segs))
    print("\n排序后顺序:")
    for seg in sorted_segs:
        print("  stroke_id={} ymin={} xmin={}".format(
            seg.stroke_id, min(p[0] for p in seg.points), min(p[1] for p in seg.points)))
except Exception as e:
    print("异常:", type(e).__name__, e)
    import traceback
    traceback.print_exc()
