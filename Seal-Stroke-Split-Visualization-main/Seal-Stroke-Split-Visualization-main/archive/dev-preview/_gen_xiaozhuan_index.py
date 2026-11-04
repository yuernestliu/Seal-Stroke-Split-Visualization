"""生成 data/xiaozhuan-index.json: 字名 → 文件名
供 render_xiaozhuan.js 前端查表使用。
"""
import json, re
from pathlib import Path

DST_PNG = Path(r'c:\Users\zzy\Pictures\作业\Seal-Stroke-Split-Visualization-main\public\assets\xiaozhuan')
INDEX_OUT = Path(r'c:\Users\zzy\Pictures\作业\Seal-Stroke-Split-Visualization-main\data\xiaozhuan-index.json')

PAT = re.compile(r'(\d+)_([^_]+)_Z_(?:說文‧[^\.]+|小篆)\.png')

char_to_files = {}
for p in DST_PNG.glob('*.png'):
    m = PAT.match(p.name)
    if m:
        ch = m.group(2)
        char_to_files.setdefault(ch, []).append(p.name)

# 多份: 优先 說文 命名
index = {}
for ch, files in char_to_files.items():
    pri = sorted(files, key=lambda n: (0 if '說文' in n else 1, n))
    index[ch] = pri[0]

INDEX_OUT.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'索引条目: {len(index)} 字')
print(f'已写入: {INDEX_OUT}')
print(f'文件大小: {INDEX_OUT.stat().st_size} 字节')
