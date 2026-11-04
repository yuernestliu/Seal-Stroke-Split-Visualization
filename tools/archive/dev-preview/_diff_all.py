import json, re
from pathlib import Path

def load(path):
    text = open(path, encoding="utf-8").read()
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    start = text.index("window.GLYPH_DATA")
    eq = text.index("=", start)
    brace = text.index("{", eq)
    depth = 0
    end = -1
    for i in range(brace, len(text)):
        c = text[i]
        if c == "{": depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
    return json.loads(text[brace:end+1])

def seg_fingerprint(seg):
    """用首尾点 + 总点数 作指纹（不用全部 points 节省时间）"""
    pts = seg["points"]
    return (tuple(pts[0]), tuple(pts[-1]), len(pts))

root = Path(r"c:\Users\zzy\Pictures\作业\Seal-Stroke-Split-Visualization-main")
old = load(root / "data" / "glyphs.js.bak")
new = load(root / "data" / "glyphs.js")

old_by_id = {g["id"]: g for g in old["glyphs"]}
new_by_id = {g["id"]: g for g in new["glyphs"]}

changed = []
unchanged = []
for gid in old_by_id:
    o = old_by_id[gid]["segments"]
    n = new_by_id[gid]["segments"]
    o_fp = [seg_fingerprint(s) for s in o]
    n_fp = [seg_fingerprint(s) for s in n]
    if o_fp == n_fp:
        unchanged.append(gid)
    else:
        changed.append(gid)

print(f"总数: {len(old_by_id)}")
print(f"改变: {len(changed)}")
print(f"不变: {len(unchanged)}")
print()
print("=== 改变的字 ===")
for gid in changed:
    o = old_by_id[gid]["segments"]
    n = new_by_id[gid]["segments"]
    print(f"\n  {gid}  ({len(o)} 笔)")
    print("    旧 id/起/终/点:", [seg_fingerprint(s) for s in o])
    print("    新 id/起/终/点:", [seg_fingerprint(s) for s in n])
