/* One image inventory; prepared records enrich it without replacing raw sources. */
(() => {
  const inventory = window.SEAL_LIBRARY;
  const prepared = new Map(window.GLYPH_DATA.glyphs.map(g => [g.id, {...g}]));
  const templateData = window.TEMPLATE_GLYPH_DATA || {glyphs:[],partsByMark:{}};
  for (const glyph of templateData.glyphs) if (!prepared.has(glyph.id)) prepared.set(glyph.id,{...glyph});
  const aliasMap = new Map();
  for (const [character,id] of Object.entries(inventory.aliases)) {
    if (!aliasMap.has(id)) aliasMap.set(id,[]);
    aliasMap.get(id).push(character);
  }
  const glyphs = inventory.entries.map(([id,mark,section]) => {
    const glyph = prepared.get(id) || {
      id,mark,title:mark,sourceId:id.split('_')[0],
      source:{collection:'说文解字',section,experiment:'raw'},
      assets:{original:inventory.imageBase+id+'.png'},
      segments:[],parts:[],components:[],original_meaning:'',meaning_extend:'',structure_desc:'',
      reviewStatus:'原图已收录；平滑、拆分与释读待完成'
    };
    const template = templateData.partsByMark[mark];
    if (template) {
      glyph.templateParts = template.parts;
      glyph.templateWidth = template.width;
      glyph.templateHeight = template.height;
    }
    glyph.aliases = aliasMap.get(id) || [];
    glyph.hasStrokeMetrics = Boolean(glyph.metrics?.lengths?.length);
    glyph.metrics ||= {lengths:[],segmentCount:0,overlapPixels:0};
    const prior = window.COMPONENT_PRIORS?.[id];
    if (prior) {
      glyph.componentPrior = prior;
      if (!glyph.components?.length && !glyph.parts?.length) glyph.components = prior.parts.map(name => ({name,kind:'IDS先验',status:'候选部件，待校核'}));
    }
    return glyph;
  });
  const byId = new Map(glyphs.map(g => [g.id,g]));
  function forScope(scope='500') {
    return scope === 'all' ? glyphs : (inventory.sets[scope] || []).map(id => byId.get(id)).filter(Boolean);
  }
  function splitKind(glyph) {
    if (window.CLEANED_GLYPHS?.[glyph.id] || glyph.segments?.length) return 'strokes';
    return glyph.templateParts?.length > 1 ? 'parts' : null;
  }
  window.GlyphLibrary = {glyphs,byId,forScope,splitKind,stats:inventory.stats};
})();
