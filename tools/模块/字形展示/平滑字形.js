/* One geometry source for cleaned glyphs. Only color or viewport may vary. */
(() => {
  const NS='http://www.w3.org/2000/svg';
  const palette=['#eeb377','#a5c4b1','#d89181','#bfafd0','#e6d38a','#8eb8c4'];
  function get(glyph) {
    const record=window.CLEANED_GLYPHS?.[glyph.id];
    return record?.status==='display_checked' ? record : null;
  }
  function svg(glyph,{colored=false,strokeIndex=null,label=`${glyph.mark} 的清理字形`}={}) {
    const record=get(glyph);if(!record)return null;
    const root=document.createElementNS(NS,'svg');
    root.setAttribute('viewBox',`-3 -3 ${record.width+6} ${record.height+6}`);
    root.setAttribute('role','img');root.setAttribute('aria-label',label);root.setAttribute('class','glyph-vector cleaned-glyph');
    record.strokes.forEach((stroke,i) => {
      if(strokeIndex!==null && i!==strokeIndex)return;
      const path=document.createElementNS(NS,'path');
      const attributes={d:stroke.path,fill:'none',stroke:colored ? palette[i%palette.length] : 'currentColor','stroke-width':stroke.width,'stroke-linecap':'round','stroke-linejoin':'round','data-stroke-id':stroke.id};
      Object.entries(attributes).forEach(([key,value])=>path.setAttribute(key,value));root.append(path);
    });
    return root;
  }
  window.CleanGlyphShapes={get,svg};
})();
