(() => {
  const NS = "http://www.w3.org/2000/svg";

  function svgNode(name, attributes = {}) {
    const node = document.createElementNS(NS, name);
    Object.entries(attributes).forEach(([key, value]) => node.setAttribute(key, value));
    return node;
  }

  function addText(parent, text, x, y, className) {
    const label = svgNode("text", { x, y, class: className, "text-anchor": "middle" });
    label.textContent = text;
    parent.append(label);
  }

  /**
   * 在 SVG 节点里绘制一个字符的小篆图（找不到时回退为 text）。
   * @param {SVGGElement} parent
   * @param {string} ch
   * @param {number} cx 中心 x
   * @param {number} cy 中心 y
   * @param {number} size 边长（px）
   * @param {string} [textClassName] 回退文字的 class
   */
  function addXiaozhuanMark(parent, ch, cx, cy, size, textClassName) {
    const src = window.xiaozhuanSrc ? window.xiaozhuanSrc(ch) : null;
    if (src) {
      const img = svgNode("image", {
        href: src,
        x: cx - size / 2,
        y: cy - size / 2,
        width: size,
        height: size,
        preserveAspectRatio: "xMidYMid meet",
        class: "graph-mark-img",
      });
      parent.append(img);
    } else {
      addText(parent, String(ch), cx, cy + 8, textClassName || "graph-mark");
    }
  }

  function relationPosition(index, total) {
    const radiusX = total > 4 ? 278 : 244;
    const radiusY = total > 4 ? 138 : 118;
    const angle = -Math.PI / 2 + (Math.PI * 2 * index) / Math.max(total, 1);
    return { x: 430 + Math.cos(angle) * radiusX, y: 205 + Math.sin(angle) * radiusY };
  }

  function render(container, glyph, relations, onSelect) {
    container.replaceChildren();
    const svg = svgNode("svg", { viewBox: "0 0 860 420", role: "img", "aria-label": `${glyph.title} 的字形关系` });
    const center = { x: 430, y: 205 };
    const nodes = relations.map((relation, index) => ({ ...relation, position: relationPosition(index, relations.length) }));

    nodes.forEach((relation) => {
      const position = relation.position;
      const edge = svgNode("line", { x1: center.x, y1: center.y, x2: position.x, y2: position.y, class: "graph-edge" });
      svg.append(edge);
      const labelX = center.x + (position.x - center.x) * 0.53;
      const labelY = center.y + (position.y - center.y) * 0.53 - 7;
      addText(svg, relation.label, labelX, labelY, "graph-edge-label");
    });

    nodes.forEach(({ glyph: related, position }) => {
      const group = svgNode("g", { class: "graph-node graph-node-related", tabindex: "0", role: "button", "aria-label": `查看 ${related.title}` });
      group.append(svgNode("circle", { cx: position.x, cy: position.y, r: 48 }));
      addXiaozhuanMark(group, related.mark, position.x, position.y, 60, "graph-mark");
      addText(group, `${related.metrics.segmentCount} 笔`, position.x, position.y + 73, "graph-count");
      const activate = () => onSelect(related.id);
      group.addEventListener("click", activate);
      group.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          activate();
        }
      });
      svg.append(group);
    });

    const centerGroup = svgNode("g", { class: "graph-node graph-node-center" });
    centerGroup.append(svgNode("circle", { cx: center.x, cy: center.y, r: 63 }));
    addXiaozhuanMark(centerGroup, glyph.mark, center.x, center.y, 78, "graph-mark-center");
    addText(centerGroup, `${glyph.metrics.segmentCount} 笔`, center.x, center.y + 91, "graph-count");
    svg.append(centerGroup);
    container.append(svg);
  }

  window.GraphRenderer = { render };
})();
