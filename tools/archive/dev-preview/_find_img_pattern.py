"""看当前 js 里第一个有 image 的 segment 的完整字段"""
import re
from pathlib import Path

js = Path(r'data\glyphs.js').read_text(encoding='utf-8')

# 找第一个 "image"
i = js.find('"image":')
j = js.rfind('"id":', 0, i)
print("=== 第一个有 image 的 segment ===")
print(js[j:j+400])
print()

# 找 image 路径的模式
paths = re.findall(r'"image":\s*"([^"]+)"', js)
print(f"image 路径数: {len(paths)}")
print(f"前 5 个: {paths[:5]}")
print(f"路径模式: {paths[0] if paths else 'N/A'}")