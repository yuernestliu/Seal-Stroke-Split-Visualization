"""扫描 C:\\Users\\zzy\\Pictures\\作业\\拆笔画_clean\\按部首分类\\ 全部 PNG
按字名建索引，把 PNG 拍平复制到 public/assets/xiaozhuan/。
优先选择 說文‧部首 命名版本，其次小篆命名版本。
"""
import re, shutil
from pathlib import Path

BASE = Path(r'C:\Users\zzy\Pictures\作业\拆笔画_clean\按部首分类')
DST = Path(r'c:\Users\zzy\Pictures\作业\Seal-Stroke-Split-Visualization-main\public\assets\xiaozhuan')

# 兼容两种命名: {unicode}_{字}_Z_說文‧X.png 或 {unicode}_{字}_Z_小篆.png
PAT = re.compile(r'(\d+)_([^_]+)_Z_(?:說文‧[^\.]+|小篆)\.png')

pngs = list(BASE.rglob('*.png'))
char_to_files = {}
for p in pngs:
    m = PAT.match(p.name)
    if m:
        ch = m.group(2)
        char_to_files.setdefault(ch, []).append((p, p.name))

print(f'按部首分类总 PNG: {len(pngs)}')
print(f'按字名去重: {len(char_to_files)}')

DST.mkdir(parents=True, exist_ok=True)
copied, skipped = 0, 0
for ch, items in char_to_files.items():
    # 优先 說文‧部首 命名
    pri = sorted(items, key=lambda x: (0 if '說文' in x[1] else 1, x[1]))
    chosen_name = pri[0][1]
    src_path = pri[0][0]
    tgt_path = DST / chosen_name
    if tgt_path.exists():
        skipped += 1
        continue
    shutil.copy2(src_path, tgt_path)
    copied += 1

print(f'复制完成: {copied} 张新, {skipped} 张已存在')
print(f'目标目录: {DST}')
print(f'目标文件数: {len(list(DST.glob("*.png")))}')
