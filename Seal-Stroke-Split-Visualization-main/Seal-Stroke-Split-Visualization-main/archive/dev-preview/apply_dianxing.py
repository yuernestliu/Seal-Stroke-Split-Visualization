"""把'典型' outputs 里 14 个字的 strokes.png 覆盖到 public 对应目录。"""
import shutil
from pathlib import Path
from PIL import Image

base = Path(r'C:\Users\zzy\Pictures\作业\Seal-Stroke-Split-Visualization-main\public\assets\experiments\v1')
dianxing = Path(r'C:\Users\zzy\Pictures\作业\拆笔画_clean\outputs\典型')

# '典型' 14 个目录
dianxing_dirs = [d for d in dianxing.iterdir() if d.is_dir()]


def extract_id(name: str) -> str:
    """从 '07432_先_Z_說文‧先部' 提取字 ID '07432_先'"""
    parts = name.split('_')
    return '_'.join(parts[:2])


# 列出典型所有字 ID
print('=== 典型 outputs 14 个字 ===')
for d in dianxing_dirs:
    sid = extract_id(d.name)
    sp = d / 'strokes.png'
    bp = d / 'binary.png'
    if not sp.exists() or not bp.exists():
        print(f'[?] {d.name}: 缺 strokes.png 或 binary.png')
        continue
    s_size = Image.open(sp).size
    b_size = Image.open(bp).size
    same = '✓' if s_size == b_size else '✗'
    print(f'  {sid:15} strokes={s_size} binary={b_size} 尺寸{same}')


print()
print('=== 找 public 对应目录 ===')
public_dirs = [d for d in base.iterdir() if d.is_dir()]
public_by_id = {extract_id(d.name): d for d in public_dirs}


matched = []
unmatched = []
for d in dianxing_dirs:
    sid = extract_id(d.name)
    if sid in public_by_id:
        matched.append((d, public_by_id[sid]))
    else:
        unmatched.append((d, sid))

for d, sid in unmatched:
    print(f'  [NO] {sid} (典型={d.name})')

print()
print(f'匹配: {len(matched)} / 不匹配: {len(unmatched)}')

# 对每个匹配项：覆盖 strokes.png
ok, fail = 0, 0
print()
print('=== 覆盖 strokes.png ===')
for src_dir, dst_dir in matched:
    sid = extract_id(src_dir.name)
    src = src_dir / 'strokes.png'
    dst = dst_dir / 'strokes.png'
    s_size = Image.open(src).size
    b_dst = Image.open(dst_dir / 'binary.png').size
    try:
        shutil.copy2(src, dst)
        print(f'  [OK]   {sid}: 典型 {src_dir.name}/strokes.png -> public {dst_dir.name}/strokes.png  (尺寸 {s_size}, public binary {b_dst})')
        ok += 1
    except Exception as e:
        print(f'  [FAIL] {sid}: {e}')
        fail += 1

print()
print(f'覆盖: {ok} 成功 / {fail} 失败')
