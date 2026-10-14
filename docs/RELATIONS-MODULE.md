# 字间联系模块

页面的第三块是独立模块，默认固定展示，没有筛选或展开状态。当前规则与旧版保持一致。

入口是 `src/relations-panel.js`，样式是 `src/relations-panel.css`。主页面只提供数据、容器和选择回调：

```js
window.RelationsPanel.render({
  container, // 已挂载的模块容器
  glyph,     // 当前字形
  glyphs,    // 已导入的全部字形
  onSelect,  // onSelect(glyphId)，由主页面完成切换
});
```

模块内部通过 `RelationEngine.relatedGlyphs` 获得候选关系，通过 `GraphRenderer.render` 绘制。它不读取主页面选择状态，不修改字源故事，也不持有字库弹窗。

后续成员可以独立修改关系的表达、布局或规则。展示层优先改 `relations-panel.js/.css` 和 `graph-renderer.js`；关系规则改 `relation-engine.js`。保留上述接口即可与主页面协作。

检查：`npm run check`、`npm test`，再在浏览器检查节点点击与无关系样本。
