# 字间关系

部件推断.js提取显式部首／形旁／声旁；关系规则.js提供纯计算RelationEngine.relatedGlyphs；关系绘图.js绘图；关系面板.js/.css提供固定面板RelationsPanel.render({container,glyph,glyphs,onSelect})。

当前是先验关系，还没有梯径小篆分类。没有测量的字不能当作零笔画参与距离；现代IDS也不能直接升级为已确认形旁或声旁。新关系需提供理由、来源和状态。

梯径参考在资料/部件与笔画/梯径参考/，属于现代字笔画编码，不能直接对应小篆像素或路径。下一步独立做小篆输入适配与人工样本评估。接口细节见docs/RELATIONS-MODULE.md；本组不需要改字形或故事代码。
