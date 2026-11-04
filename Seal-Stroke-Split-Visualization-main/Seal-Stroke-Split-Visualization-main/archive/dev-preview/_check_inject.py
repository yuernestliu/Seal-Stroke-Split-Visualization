"""检查 docx 与 glyphs.js title 的匹配情况。"""
import json, re, html, zipfile
from pathlib import Path

ROOT = Path(r'c:\Users\zzy\Pictures\作业\Seal-Stroke-Split-Visualization-main')
DOCX = Path(r'C:\Users\zzy\Pictures\作业\汉字构形分析-.docx')

with zipfile.ZipFile(DOCX) as z:
    xml = z.read('word/document.xml').decode('utf-8')
docx_data = json.loads(html.unescape(re.sub(r'<[^>]+>', '', xml)))

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
glyph_titles = set(g['title'] for g in data['glyphs'])

miss = [d for d in docx_data if d['char'] not in glyph_titles]
print(f'docx 里没匹配的字 ({len(miss)}):')
for d in miss:
    parts = d.get('parts', [])
    print(f"  char='{d['char']}' parts={parts}")
