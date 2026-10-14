"""把 汉字构形分析-.docx 里的 JSON 数据合并进 glyphs.js。

对每个 char，按 glyph.title 匹配，注入 9 个字段：
  1. mark_text          释义来源模块标题行（支持 {{xiaozhuan:字}} 标记）
  2. original_meaning   【本义】内容，渲染在【释义与来源】模块
  3. meaning_extend     【字义拓展】内容；空字符串时整个区块隐藏
  4. structure_desc     【部件与构形】模块的构形解析总起（支持 xiaozhuan 标记）
  5. parts[]            构件名称数组
  6. part_type[]        构件类型数组（形旁/声旁/会意构件/独体字/独体部首）
  7. part_comment[]     构件在本字中的局部说明
  8. xing_pang          形声字的形旁；非形声字为空字符串（用于同形旁筛选）
  9. sheng_pang         形声字的声旁；非形声字为空字符串（用于同声旁筛选）
"""
import json, re, html, zipfile, shutil
from pathlib import Path

ROOT = Path(r'c:\Users\zzy\Pictures\作业\Seal-Stroke-Split-Visualization-main')
DOCX = Path(r'C:\Users\zzy\Pictures\作业\汉字构形分析-.docx')
GLYPHS_JS = ROOT / 'data' / 'glyphs.js'

# ---------- 读 docx → JSON ----------
with zipfile.ZipFile(DOCX) as z:
    xml = z.read('word/document.xml').decode('utf-8')
data = json.loads(html.unescape(re.sub(r'<[^>]+>', '', xml)))
print(f'docx 条目: {len(data)}')

# ---------- char → 9 字段映射 ----------
INJECT_KEYS = [
    'mark_text', 'original_meaning', 'meaning_extend', 'structure_desc',
    'parts', 'part_type', 'part_comment', 'xing_pang', 'sheng_pang',
]
by_char = {}
for d in data:
    ch = d['char']
    by_char[ch] = {k: d.get(k, '' if k not in ('parts', 'part_type', 'part_comment') else [])
                   for k in INJECT_KEYS}

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
        for k in INJECT_KEYS:
            g[k] = b[k]
        injected += 1

print(f'注入字形数: {injected} / {len(data_cur["glyphs"])}')

# ---------- 写回 (保持外层缩进) ----------
m = re.search(r'window\.GLYPH_DATA\s*=\s*', text)
prefix = text[:m.end()]
suffix_m = re.search(r';\s*$', text)
suffix = suffix_m.group(0) if suffix_m else ';'

new_text = prefix + json.dumps(data_cur, ensure_ascii=False, indent=2) + suffix

# 备份
shutil.copy2(GLYPHS_JS, ROOT / 'data' / 'glyphs.js.bak2')
GLYPHS_JS.write_text(new_text, encoding='utf-8')
print(f'已写入 {GLYPHS_JS}')
print(f'  大小: {len(new_text)} 字符')
