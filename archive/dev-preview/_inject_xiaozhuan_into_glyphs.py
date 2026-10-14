"""把 汉字构形分析-.docx 里的 JSON 数据合并进 glyphs.js。
对每个 char，按 glyph.id 末尾的 title 匹配，注入:
  analysis / parts / part_type / mark_text
"""
import json, re, html, zipfile, shutil
from pathlib import Path

ROOT = Path(r'c:\Users\zzy\Pictures\作业\Seal-Stroke-Split-Visualization-main')
DOCX = Path(r'C:\Users\zzy\Pictures\作业\汉字构形分析-.docx')
GLYPHS_JS = ROOT / 'data' / 'glyphs.js'
GLYPHS_BAK = ROOT / 'data' / 'glyphs.js.bak'

# ---------- 读 docx → JSON ----------
with zipfile.ZipFile(DOCX) as z:
    xml = z.read('word/document.xml').decode('utf-8')
data = json.loads(html.unescape(re.sub(r'<[^>]+>', '', xml)))
print(f'docx 条目: {len(data)}')

# ---------- char → analysis 映射 ----------
by_char = {}
for d in data:
    ch = d['char']
    by_char[ch] = {
        'analysis': d.get('analysis', ''),
        'parts': d.get('parts', []),
        'part_type': d.get('part_type', []),
        'mark_text': d.get('mark_text', ''),
    }

# ---------- 解析 glyphs.js ----------
def parse_js(text):
    m = re.search(r'window\.GLYPH_DATA\s*=\s*', text)
    brace = text.index('{', m.end())
    depth = 0; end = -1
    for i in range(brace, len(text)):
        c = text[i]
        if c == '{': depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0: end = i; break
    return json.loads(text[brace:end+1]), m.start()

text = GLYPHS_JS.read_text(encoding='utf-8')
data_cur, _ = parse_js(text)

# ---------- 注入 ----------
injected = 0
for g in data_cur['glyphs']:
    title = g.get('title', '')
    if title in by_char:
        b = by_char[title]
        g['analysis'] = b['analysis']
        g['parts'] = b['parts']
        g['part_type'] = b['part_type']
        g['mark_text'] = b['mark_text']
        injected += 1

print(f'注入字形数: {injected} / {len(data_cur["glyphs"])}')

# ---------- 写回 (保持外层缩进) ----------
# header 是 window.GLYPH_DATA = 之前的所有内容，suffix 是 ;
prefix_end = text.index('{', text.index('window.GLYPH_DATA'))
m = re.search(r'window\.GLYPH_DATA\s*=\s*', text)
prefix = text[:m.end()]
# 找最后的 ;
suffix_m = re.search(r';\s*$', text)
suffix = suffix_m.group(0) if suffix_m else ';'

new_text = prefix + json.dumps(data_cur, ensure_ascii=False, indent=2) + suffix

# 写之前备份
shutil.copy2(GLYPHS_JS, GLYPHS_BAK.with_name('glyphs.js.bak2'))
GLYPHS_JS.write_text(new_text, encoding='utf-8')
print(f'已写入 {GLYPHS_JS}')
print(f'  大小: {len(new_text)} 字符')
