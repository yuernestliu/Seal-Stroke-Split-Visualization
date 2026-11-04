"""看 .bak 里第一个 segment 的完整内容（包含 image）"""
import re
from pathlib import Path

bak = Path(r'data\glyphs.js.bak').read_text(encoding='utf-8')

# 找第一个带 "image" 的 segment
i = bak.find('"image":')
if i < 0:
    print("bak 里也没 image 字段!")
else:
    # 往前找一个 segment 开始
    j = bak.rfind('"id":', 0, i)
    print(bak[j:j+800])