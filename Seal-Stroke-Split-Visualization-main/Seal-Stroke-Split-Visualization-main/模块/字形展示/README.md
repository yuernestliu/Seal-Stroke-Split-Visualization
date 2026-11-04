# 字形展示

| 文件 | 责任 |
| --- | --- |
| 字形界面.js | 整字、拆笔／拆部件、字库和分页；window.GlyphUI |
| 平滑字形.js | 已核字形唯一SVG渲染器；window.CleanGlyphShapes |
| 小篆标记.js | 正文标记，统一指向字库/原始字形/ |
| 部件简释.js | 部件短释；颜色分区未对齐名称时不擅自套用 |

原图在字库/原始字形/，平滑结果在data/cleaned-glyphs/，轮廓在data/glyph-vectors.js，模板蒙版在public/assets/template-parts/。SVG里嵌PNG不等于平滑矢量。

保留已核平滑几何的优先级；有笔段叫拆笔，只有模板叫拆部件，没有资料就待完成。合字和拆分同源。接口：GlyphUI.renderImage/renderSegments/renderCatalog/vectorMarkup。

下一步先读docs/GLYPH-CLEANUP.md，在500字里认领小批次，分别核对轮廓与笔段。故事和关系由相邻模块负责。
