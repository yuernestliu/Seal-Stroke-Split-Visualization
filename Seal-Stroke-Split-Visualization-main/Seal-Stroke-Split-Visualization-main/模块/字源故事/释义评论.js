/* 释义评论：本义 / 引申 / 构形 三块右上角的小角标，点开留言板，数据存 localStorage。
   监听释义块自身的 DOM 变化：内容被重写后角标自动补回，不依赖渲染方显式调用。 */
(() => {
  const STORE_KEY = 'seal-comment-notes';
  const FIELDS = [
    { key: 'meaning', host: '#glyphOriginalMeaning', label: '本义' },
    { key: 'extend', host: '#glyphMeaningExtendBlock', label: '引申义' },
    { key: 'structure', host: '#structureDesc', label: '构形' },
  ];
  const escapeHtml = v => String(v ?? '').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#039;');
  const COMMENT_ICON = '<svg viewBox="0 0 16 16" width="11" height="11" aria-hidden="true" focusable="false"><path d="M2 2.8h12v8H6.2L3 13.4c-.35.3-.9.08-.9-.35V2.8z" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/></svg>';
  const load = () => { try { return JSON.parse(localStorage.getItem(STORE_KEY)) || {}; } catch { return {}; } };
  const save = data => localStorage.setItem(STORE_KEY, JSON.stringify(data));
  const notesOf = (data, gid, key) => data[gid]?.[key] || [];

  let glyphId = '';
  let lastId = '';
  let openField = null;

  function renderList(field, drawer, data) {
    const notes = notesOf(data, glyphId, field.key);
    const box = drawer.querySelector('.comment-list');
    box.replaceChildren();
    if (!notes.length) {
      const empty = document.createElement('p');
      empty.className = 'comment-empty';
      empty.textContent = '还没有批注。';
      box.append(empty);
      return;
    }
    for (const [i, note] of notes.entries()) {
      const row = document.createElement('div');
      row.className = 'comment-item';
      row.innerHTML = `<p class="comment-text">${escapeHtml(note.text)}</p><span class="comment-time">${escapeHtml(note.time)}</span>`;
      const del = document.createElement('button');
      del.type = 'button';
      del.className = 'comment-delete';
      del.setAttribute('aria-label', '删除这条批注');
      del.textContent = '×';
      del.addEventListener('click', () => {
        const latest = load();
        const list = latest[glyphId]?.[field.key] || [];
        list.splice(i, 1);
        if (!list.length) delete latest[glyphId][field.key];
        if (latest[glyphId] && !Object.keys(latest[glyphId]).length) delete latest[glyphId];
        save(latest);
        openField = field;
        refresh(glyphId, field.key);
      });
      row.append(del);
      box.append(row);
    }
  }

  function buildDrawer(field) {
    const drawer = document.createElement('div');
    drawer.className = 'comment-drawer';
    drawer.innerHTML = `<div class="comment-list"></div>
      <div class="comment-compose"><textarea rows="2" placeholder="对「${field.label}」补充你的批注…" aria-label="批注内容"></textarea>
      <button type="button" class="comment-submit">发表</button></div>`;
    const submit = () => {
      const input = drawer.querySelector('textarea');
      const text = input.value.trim();
      if (!text) return;
      const data = load();
      const notes = notesOf(data, glyphId, field.key);
      notes.push({ text, time: new Date().toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) });
      data[glyphId] = data[glyphId] || {};
      data[glyphId][field.key] = notes;
      save(data);
      refresh(glyphId, field.key);
    };
    drawer.querySelector('.comment-submit').addEventListener('click', submit);
    drawer.querySelector('textarea').addEventListener('keydown', e => {
      if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) submit();
    });
    return drawer;
  }

  function toggle(field) {
    if (openField === field) { openField = null; refresh(glyphId); return; }
    openField = field;
    refresh(glyphId, field.key);
    field.drawer?.querySelector('textarea')?.focus();
  }

  function refresh(id, focusKey) {
    glyphId = id || '';
    if (glyphId !== lastId) { openField = null; lastId = glyphId; }   // 换字后收起抽屉
    const data = load();
    for (const field of FIELDS) {
      field.hostEl = document.querySelector(field.host);
      field.drawer?.remove();
      field.drawer = null;
      field.badge?.remove();
      field.badge = null;
      if (!field.hostEl || !glyphId) continue;
      const notes = notesOf(data, glyphId, field.key);
      const badge = document.createElement('button');
      badge.type = 'button';
      badge.className = `comment-badge${notes.length ? ' has-notes' : ''}`;
      badge.innerHTML = notes.length ? escapeHtml(String(notes.length)) : COMMENT_ICON;
      badge.title = `批注：${field.label}`;
      badge.setAttribute('aria-label', `${field.label}的批注，${notes.length} 条`);
      badge.setAttribute('aria-expanded', String(openField === field));
      badge.addEventListener('click', () => toggle(field));
      field.hostEl.append(badge);
      field.badge = badge;
      if (openField === field) {
        const drawer = buildDrawer(field);
        field.hostEl.after(drawer);
        field.drawer = drawer;
        renderList(field, drawer, data);
        if (focusKey === field.key) drawer.querySelector('textarea')?.focus();
      }
    }
  }

  /* 从地址栏 hash / 资料来源编号里反推当前字 id，作为渲染方未调用时的兜底。 */
  function resolveId() {
    if (lastId) return lastId;
    const hash = new URLSearchParams(location.hash.slice(1)).get('glyph');
    if (hash) return hash;
    return document.querySelectorAll('#sourceDetails dd')[2]?.textContent.trim() || '';
  }

  /* 释义块内容被重写（渲染/换字）后，角标会被清掉；观察到缺失就补回。 */
  let scheduled = false;
  function schedule() {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(() => {
      scheduled = false;
      const hosts = FIELDS.map(f => document.querySelector(f.host)).filter(Boolean);
      if (!hosts.length || hosts.every(h => h.querySelector(':scope > .comment-badge'))) return;
      const id = resolveId();
      if (id) refresh(id);
    });
  }
  const mo = new MutationObserver(schedule);
  for (const field of FIELDS) {
    const el = document.querySelector(field.host);
    if (el) mo.observe(el, { childList: true });
  }
  schedule();

  window.CommentNotes = { refresh };
})();
