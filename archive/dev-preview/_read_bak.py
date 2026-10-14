"""看 .bak 里 07432_先 的 image 格式"""
import re
from pathlib import Path

bak = Path(r'data\glyphs.js.bak').read_text(encoding='utf-8')

# 找 07432_先 那段
target = '07432_先'
i = bak.find(f'"id": "{target}_Z_說文')
if i < 0:
    i = bak.find(target)
print(f"found at {i}")
if i > 0:
    # 截 2000 字符
    print(bak[i:i+1500])