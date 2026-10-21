(() => {
  function sum(values) {
    return values.reduce((total, value) => total + value, 0);
  }

  // 保留原序列距离计算，作为同分排序的次级参考
  function sequenceDistance(left, right) {
    const leftTotal = sum(left);
    const rightTotal = sum(right);
    const width = Math.max(left.length, right.length);
    let distance = Math.abs(left.length - right.length) * 0.28;
    for (let index = 0; index < width; index += 1) {
      const leftValue = left[index] ? left[index] / leftTotal : 0;
      const rightValue = right[index] ? right[index] / rightTotal : 0;
      distance += Math.abs(leftValue - rightValue);
    }
    return distance;
  }

  // 集合求交集（字符数组，去重）
  function intersect(a, b) {
    if (!a?.length || !b?.length) return [];
    const set = new Set(a);
    return b.filter((x) => set.has(x));
  }

  // 把"标签"用的样板字符截短到 1 个（多字部件也只露代表字）
  function oneOf(arr) {
    return arr && arr.length ? arr[0] : "";
  }

  /**
   * 判定 source 与 candidate 的相似关系
   * 优先级：声旁 > 形旁 > 部首
   * 满足任一类即视为相似；多类同时满足时加少量 bonus
   * 返回 { type, label, score, matches } 或 null（不相似）
   */
  function describeRelation(source, candidate, distance) {
    const srcPh = source._phonetic || [];
    const srcSm = source._semantic || [];
    const srcRd = source._radical || "";
    const cndPh = candidate._phonetic || [];
    const cndSm = candidate._semantic || [];
    const cndRd = candidate._radical || "";

    const phHit = intersect(srcPh, cndPh);
    const smHit = intersect(srcSm, cndSm);
    const rdHit = srcRd && srcRd === cndRd ? [srcRd] : [];

    const hitCount = (phHit.length ? 1 : 0) + (smHit.length ? 1 : 0) + (rdHit.length ? 1 : 0);
    if (hitCount === 0) return null;

    // 优先级高的决定主类型，标签附上具体共用的部件字
    let primary, type, baseScore;
    if (phHit.length) {
      primary = phHit; type = "phonetic"; baseScore = 100;
    } else if (smHit.length) {
      primary = smHit; type = "semantic"; baseScore = 88;
    } else {
      primary = rdHit; type = "radical"; baseScore = 72;
    }

    const partLabel = oneOf(primary);
    const labelMap = { phonetic: "同声旁", semantic: "同形旁", radical: "同部首" };
    const label = partLabel ? `${labelMap[type]}·${partLabel}` : labelMap[type];

    // 多类同时满足：+4 / 类
    const bonus = (hitCount - 1) * 4;

    // 距离作为微调（笔画序列越接近，分数略高）
    const distanceBoost = -distance * 6;

    return {
      type,
      label,
      matches: { phonetic: phHit, semantic: smHit, radical: rdHit },
      score: baseScore + bonus + distanceBoost,
    };
  }

  function relatedGlyphs(glyphs, glyph, limit = 6) {
    const candidates = [];
    for (const candidate of glyphs) {
      if (candidate.id === glyph.id) continue;
      const measurable = glyph.hasStrokeMetrics !== false && candidate.hasStrokeMetrics !== false;
      const distance = measurable ? sequenceDistance(glyph.metrics.lengths, candidate.metrics.lengths) : 0;
      const relation = describeRelation(glyph, candidate, distance);
      if (!relation) continue;
      const segmentGap = measurable ? Math.abs(candidate.metrics.segmentCount - glyph.metrics.segmentCount) : 0;
      const overlapGap = measurable ? Math.abs(candidate.metrics.overlapPixels - glyph.metrics.overlapPixels) / 20 : 0;
      const score = relation.score - segmentGap * 1.5 - overlapGap * 0.4;
      candidates.push({ glyph: candidate, ...relation, distance, score });
    }
    candidates.sort((a, b) => {
      if (b.score !== a.score) return b.score - a.score;
      return a.distance - b.distance;
    });
    return candidates.slice(0, limit);
  }

  function filterRelations(relations, filter) {
    if (!filter || filter === "all") return relations;
    return relations.filter((relation) => relation.type === filter);
  }

  window.RelationEngine = { relatedGlyphs, filterRelations, describeRelation };
})();
