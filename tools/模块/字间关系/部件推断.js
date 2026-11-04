(() => {
  /**
   * 从 glyph 数据中推导 三类部件：
   *   - radical（部首）：从 source.section（如 "說文‧不部" → "不"）
   *   - phonetic（声旁）：从 parts[] 找 part_type 为 "声旁" / "声旁构件" 的字
   *   - semantic（形旁）：从 parts[] 找 part_type 为 "形旁" 的字
   *
   * 如果没有 docx 注入的 parts/part_type，phonetic/semantic 为空数组，
   * 只剩 radical 这一类筛选可用。
   */
  function deriveComponents(glyph) {
    const section = glyph?.source?.section || "";
    let radical = "";
    if (section.startsWith("說文‧")) {
      radical = section.slice(3).replace(/部$/, "");
    } else if (section && section !== "来源待补" && section !== "小篆") {
      radical = section.replace(/部$/, "");
    }

    // 优先 docx 显式标注的 xing_pang / sheng_pang
    let phonetic = [];
    let semantic = [];
    const xp = typeof glyph?.xing_pang === "string" ? glyph.xing_pang.trim() : "";
    const sp = typeof glyph?.sheng_pang === "string" ? glyph.sheng_pang.trim() : "";
    if (xp || sp) {
      if (xp) semantic = xp.split(/[、,\s]+/).filter(Boolean);
      if (sp) phonetic = sp.split(/[、,\s]+/).filter(Boolean);
    } else {
      // 回退到从 parts[] + part_type[] 推导
      const parts = Array.isArray(glyph?.parts) ? glyph.parts : [];
      const types = Array.isArray(glyph?.part_type) ? glyph.part_type : [];
      for (let i = 0; i < parts.length; i += 1) {
        const t = types[i] || "";
        if (t === "声旁" || t === "声旁构件") phonetic.push(parts[i]);
        else if (t === "形旁") semantic.push(parts[i]);
      }
    }
    return { radical, phonetic, semantic };
  }

  function annotate(glyphs) {
    for (const glyph of glyphs) {
      const c = deriveComponents(glyph);
      glyph._radical = c.radical;
      glyph._phonetic = c.phonetic;
      glyph._semantic = c.semantic;
    }
    return glyphs;
  }

  window.ComponentDeriver = { deriveComponents, annotate };
})();
