import re
with open('data/glyphs.js','r',encoding='utf-8') as f:
    src = f.read()
# 找一个完整 glyph 块
i = src.find('"id": "06605_不')
if i > 0:
    # 向前回溯到 { 起点
    start = src.rfind('{', 0, i)
    # 计数
    depth = 0; j = start
    while j < len(src):
        c = src[j]
        if c == '{': depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                end = j+1
                break
        j += 1
    print('--- first glyph ---')
    print(src[start:end])
print()
# 列所有 source.section 不同值 + 统计 docx 注入情况
sections = re.findall(r'"section":\s*"([^"]+)"', src)
print('unique sections:', len(set(sections)), '/', len(sections))
print('sample sections:', sorted(set(sections))[:10])
# 查 part_type 统计
ptypes = re.findall(r'"part_type":\s*\[([^\]]*)\]', src)
print('chars with part_type:', len(ptypes))
if ptypes:
    flat = []
    for p in ptypes:
        for v in re.findall(r'"([^"]+)"', p):
            flat.append(v)
    from collections import Counter
    print('part_type counts:', Counter(flat).most_common())
