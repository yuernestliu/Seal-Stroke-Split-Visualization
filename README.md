# 小篆实验网页

三个内容区域：字形、字源故事、字间联系。默认以“安”起始。默认界面只保留左侧“字库”“偶遇”和字形下方“拆笔”。

直接打开 `index.html`，或运行 `npm run dev` 后访问 <http://127.0.0.1:4186>。GitHub Pages 可从仓库根目录发布，无需构建。

## 当前功能

- 安、宇、包、光已使用原包笔段清理后的 SVG，合字与拆笔完全同形。其他字仍使用现有字体/轮廓回退。
- 点击“拆笔”显示彩色拆分字形与独立笔段；点击“合字”恢复。没有播放、速度、描写、猜字或独立笔画选择。
- 展示已有本义、引申义、构形说明和古今字形对照；资料来源按需查看。
- 字库搜索与随机遇见有故事的字。
- 关系图固定展示，点击关系节点可切换字形。没有筛选或展开/收起选择。
- 页面底部只显示“授权说明”，完整署名、版权和许可在 `license.html` 与 `assets/fonts/LICENSE.md` 中。

当前数据是 124 个样本，61 个有本义、引申义和构形说明。没有补造完整历史演变链。

## 目录入口

| 位置 | 用途 |
| --- | --- |
| `index.html`、`styles.css` | 页面结构和整体样式 |
| `license.html` | 可从页面访问的授权说明 |
| `src/app.js`、`src/ui.js` | 当前选择、拆笔、字库与故事展示 |
| `src/relations-panel.js`、`src/relations-panel.css` | 独立的字间联系模块 |
| `src/relation-engine.js`、`src/graph-renderer.js` | 关系规则与图形绘制 |
| `data/glyphs.js` | 原有字形、笔段、图像路径和释读资料，本次未修改 |
| `data/stories.js` | 故事标题、出处和有材料支持的历史字形路径 |
| `data/cleaned-glyphs/`、`data/cleaned-glyphs.js` | 逐字清理结果与生成的发布文件 |
| `src/clean-glyph-shapes.js` | 清理字形唯一渲染器 |
| `data/glyph-vectors.js` | 从原样本提取的 SVG 轮廓与独立笔段 |
| `assets/fonts/`、`data/seal-font.js` | 未修改的官方字体、授权和覆盖表 |
| `assets/xiaozhuan/`、`public/assets/` | 部件字图、原图与实验发布资产 |
| `research/` | 原始算法工程与趣味字素材 |
| `archive/` | 旧站、临时预览、备份；上一版完整交互在 `interface-with-controls/` |
| `docs/`、`tests/` | 协作说明和验证 |

后续 agent 的清理入口：[字形清理 Notes](docs/GLYPH-CLEANUP.md)。

独立开发关系区域见 [关系模块说明](docs/RELATIONS-MODULE.md)。资料录入见 [CONTRIBUTING](docs/CONTRIBUTING.md)。

## 字体与拆分数据

四个清理字优先显示，不会被崇羲字体加载覆盖。后续字按 Notes 逐字生成、检查、发布。

官方崇羲篆體 OTF 保持原始字节，不裁剪、转换或修改。样本 SVG 来自项目图像，与官方字体分开。拆笔时使用样本坐标与轮廓，避免把不同笔形混在一起。

导入新实验后可执行 `python3 scripts/build_glyph_vectors.py` 更新轮廓，需要 Pillow、NumPy、SciPy、scikit-image；不会修改原图或笔顺数据。

`npm run check` 检查脚本语法，`npm test` 检查拆笔、字库、固定关系图、字形覆盖与发布资源。
