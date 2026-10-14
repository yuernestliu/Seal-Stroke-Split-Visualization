"""列出缺 image 的字 + 缺哪几笔"""
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

print("=== 缺 image 的字 + 缺哪几笔 + 现有 image 路径 ===")
for g in data['glyphs']:
    bad = []
    for s in g.get('segments', []):
        if not s.get('image'):
            bad.append(s.get('id'))
    if bad:
        # 看其它有的 segment 的 image 字段格式
        sample_img = next((s['image'] for s in g.get('segments', []) if s.get('image')), None)
        print(f"  {g['id']}: 缺 id={bad}, 完整数={len(g['segments'])}")
        if sample_img:
            print(f"      示例 image: {sample_img}")
        else:
            print(f"      全缺! assets={g.get('assets', {})}")