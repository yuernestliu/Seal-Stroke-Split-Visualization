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

# 检查 pixelCount
zero_pc_glyphs = []
for g in data['glyphs']:
    for s in g.get('segments', []):
        if s.get('pixelCount', -1) == 0:
            zero_pc_glyphs.append(g['id'])
            break

print(f"pixelCount=0 的字（segment 里全部为 0）: {len(zero_pc_glyphs)}")
for x in zero_pc_glyphs[:30]:
    print(f"  - {x}")

# 抽样看：07432_先（被改的）vs 06605_不（没被改的）
print()
print("=== 抽样 ===")
for g in data['glyphs']:
    if g['id'].startswith('07432_先'):
        print(f"\n  {g['id']}（改了）:")
        for s in g['segments']:
            print(f"    id={s['id']}: pointCount={s['pointCount']}, pixelCount={s['pixelCount']}")
    elif g['id'].startswith('06605_不'):
        print(f"\n  {g['id']}（没改）:")
        for s in g['segments']:
            print(f"    id={s['id']}: pointCount={s['pointCount']}, pixelCount={s['pixelCount']}")