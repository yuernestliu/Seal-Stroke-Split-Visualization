# 当前 167 字处理结果包

本目录保存当前人工拆笔结果及其可复核的几何记录。每个完整字形 ID 目录均对应一个字，并保留原图来源、清理掩膜、真实矢量轮廓、骨架拓扑和复核状态。

## 单字目录文件

- `source.json`：原始 PNG、人工标签图的路径与 SHA-256、画布尺寸及坐标系。
- `mask.png`：清理后的字形掩膜；原始图不在此处覆盖。
- `outline.svg`：未拆分的真实矢量轮廓。
- `outline-split.svg`：按当前人工标签拆分的矢量轮廓。
- `skeleton.json`：节点、边、采样点、交点／闭环和宽度记录，可按原图像素坐标复用。
- `skeleton.svg` / `skeleton-split.svg`：骨架可视化。
- `overlay.svg`：用于把轮廓和骨架叠回坐标画布复核的叠加图。
- `review.json`：轮廓、骨架、拆笔状态，负责人／复核人、问题和修订历史；未人工确认的内容明确标为待复核。
- `parameters.json`：清理、融合、连接和矢量平滑所用参数。
- `display-split.svg`、`strokes-separated.svg`、`site-*.svg`：网页展示派生图，不替代上述规范记录。

## 当前展示版记录

`site-*.svg` 是后来生成的平滑中心线展示版，和上面的 `manual-v2` 填充轮廓／骨架不是同一版几何。因此本目录另外生成了 `current-source.json`、`current-skeleton.json`、`current-skeleton.svg`、`current-parameters.json`、`current-review.json` 以及根目录 `current-display-summary.json`。这些文件严格记录当前展示 SVG 的路径、节点、参数和复核状态；旧的六类文件保留为历史版本，不能与当前展示版混用。

## 坐标与状态

统一坐标原点在原图左上角，`x` 向右、`y` 向下，单位为原始 PNG 像素；归一化坐标必须可逆。人工标签决定当前现代笔画的拆分归属，骨架本身不自动推断笔顺或古文字构形。`review.json` 中若为 `candidate-needs-manual-review`，表示几何已生成但仍需人工复核，不能视为最终确认。

根目录 `summary.json` 汇总 167 个字的数量、笔画连续性、空白保留和修补记录。
