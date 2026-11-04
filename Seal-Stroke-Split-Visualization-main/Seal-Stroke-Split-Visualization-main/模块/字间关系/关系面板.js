/* 字间联系模块。只负责容器内的展示；切换字形通过 onSelect(id) 通知主页面。 */
(() => {
  function render({container,glyph,glyphs,onSelect}) {
    const relations = window.RelationEngine.relatedGlyphs(glyphs,glyph,6);
    container.replaceChildren();
    const graph = document.createElement('div');
    graph.id = 'relationGraph'; graph.className = 'graph-shell';
    window.GraphRenderer.render(graph,glyph,relations,onSelect);
    container.append(graph);
    if (!relations.length) {
      const empty = document.createElement('p'); empty.className = 'relations-empty';
      empty.textContent = '这个字的联系资料正在补充。'; container.append(empty);
    }
  }
  window.RelationsPanel = {render};
})();
