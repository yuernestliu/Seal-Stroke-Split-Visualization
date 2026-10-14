"""检查 segments 里 image 字段缺失情况"""
import json, re
from pathlib import Path

text = Path(r'data\glyphs.js').read_text(encoding='utf-8')
m = re.search(r'window\.GLYPH_DATA\s*=\s*', text)
brace = text.index('{', m.end())
depth = 0; end = -1; in_str = False; esc = False
for i in range(brace, len(text)):
    c = text[i]
    if in_str:
        if esc: esc = False
        elif c == chr(92): esc = True
        elif c == chr(34): in_str = False
    else:
        if c == chr(34): in_str = True
        elif c == '{': depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0: end = i; break
data = json.loads(text[brace:end+1])

# 看 segment 字段都有啥
print("=== 第一个字的所有 segment 字段 ===")
g0 = data['glyphs'][0]
print(f"字: {g0['id']}")
for k in g0:
    print(f"  {k}: {type(g0[k]).__name__}")
print()
if g0.get('segments'):
    print(f"  segment 字段:")
    for k in g0['segments'][0]:
        print(f"    {k}: {type(g0['segments'][0][k]).__name__}")
print()

# 统计哪些字 segment 缺 image
missing = []
present = 0
for g in data['glyphs']:
    for s in g.get('segments', []):
        if 'image' not in s or not s.get('image'):
            missing.append((g['id'], s.get('id', '?')))
        else:
            present += 1

print(f"有 image 字段的 segment 数: {present}")
print(f"缺 image 字段的 segment 数: {len(missing)}")
print()
if missing:
    print("缺 image 的字（前 30）:")
    seen = set()
    for gid, sid in missing[:60]:
        if gid not in seen:
            print(f"  {gid}: 缺 id={sid}")
            seen.add(gid)
        if len(seen) >= 30: break