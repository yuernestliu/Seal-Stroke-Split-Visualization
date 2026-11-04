"""列出 glyphs.js 里 124 个字的 id 和 title。"""
import json, re
from pathlib import Path
ROOT = Path(r'c:\Users\zzy\Pictures\作业\Seal-Stroke-Split-Visualization-main')
text = (ROOT / 'data' / 'glyphs.js').read_text(encoding='utf-8')
m = re.search(r'window\.GLYPH_DATA\s*=\s*', text)
brace = text.index('{', m.end())
depth = 0; end = -1
for i in range(brace, len(text)):
    c = text[i]
    if c == '{': depth += 1
    elif c == '}':
        depth -= 1
        if depth == 0: end = i; break
data = json.loads(text[brace:end+1])
print(f'总字数: {len(data["glyphs"])}')
print()
for i, g in enumerate(data['glyphs'], 1):
    print(f'{i:3d}. id={g["id"]:35s} title={g["title"]}')
