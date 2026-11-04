/**
 * 把文本中的 {{xiaozhuan:字名}} 标记替换为行内小篆图。
 * 找不到的字名保留原文字（不抛错）。
 *
 * 用法（在 index.html 中先于 ui.js 加载）：
 *   <script src="./模块/字形展示/小篆标记.js"></script>
 *   await window.loadXiaozhuanIndex();
 *   const html = window.renderXiaozhuan(text);
 *
 * img 行内样式严格按需求：height:1.2em; vertical-align:middle; margin:0 2px;
 */

const MARK_RE = /\{\{xiaozhuan:([^}]+)\}\}/g;
const IMG_STYLE = 'height:1.2em; vertical-align:middle; margin:0 2px;';
const ESCAPE_RE = /[&<>"']/g;
const ESCAPE_MAP = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
function escapeHtml(s) {
  return String(s).replace(ESCAPE_RE, (c) => ESCAPE_MAP[c]);
}

let _indexCache = window.__xiaozhuanData || null;
let _pendingReady = []; // 等待 'xiaozhuan-index-ready' 事件的回调

/** 同步判断：缓存是否就绪 */
window.isXiaozhuanReady = function () { return _indexCache !== null; };

/** 等待索引就绪后执行回调（已就绪则立刻执行） */
window.whenXiaozhuanReady = function (cb) {
  if (_indexCache) { try { cb(); } catch (e) { console.error(e); } return; }
  _pendingReady.push(cb);
};

/** 加载字名 → 文件名 索引。默认从 ./data/xiaozhuan-index.json 读取。 */
window.loadXiaozhuanIndex = function (url = './data/xiaozhuan-index.json') {
  if (_indexCache) return Promise.resolve(_indexCache);
  return fetch(url).then((r) => {
    if (!r.ok) throw new Error(`无法加载 xiaozhuan 索引: ${r.status}`);
    return r.json();
  }).then((idx) => {
    _indexCache = idx;
    flushPendingReady();
    return idx;
  });
};

/** 手工注入索引（避免 fetch） */
window.setXiaozhuanIndex = function (idx) {
  _indexCache = idx;
  flushPendingReady();
};

function flushPendingReady() {
  const pending = _pendingReady.splice(0);
  pending.forEach((cb) => {
    try { cb(); } catch (e) { console.error(e); }
  });
}

// 监听 index.html 的异步回退事件
window.addEventListener('xiaozhuan-index-ready', () => {
  if (window.__xiaozhuanData && !_indexCache) {
    _indexCache = window.__xiaozhuanData;
    flushPendingReady();
  }
});

/**
 * @param {string} text 含 {{xiaozhuan:字名}} 标记的源文本
 * @param {object} [opts]
 * @param {string} [opts.assetBase='./字库/原始字形/']
 * @returns {string} 已替换为 <img> 的 HTML 字符串
 */
window.renderXiaozhuan = function (text, opts = {}) {
  const assetBase = opts.assetBase ?? './字库/原始字形/';
  // 1) 用 \u0000 把"标记段"和"非标记段"交替切分
  const tmp = String(text).replace(MARK_RE, (m, name) => `\u0000${name}\u0000`);
  // 2) 偶数下标：原文片段 → escape；奇数下标：字名 → 渲染为 <img>
  return tmp.split('\u0000').map((part, i) => {
    if (i % 2 === 0) return escapeHtml(part);
    const file = _indexCache?.[part];
    if (!file) return `{{xiaozhuan:${part}}}`; // 找不到 → 保留原标记
    const safe = escapeHtml(part);
    const src = `${assetBase}${file}`;
    return `<img src="${src}" alt="${safe} 小篆" data-xiaozhuan="${safe}" style="${IMG_STYLE}" class="xiaozhuan-mark">`;
  }).join('');
};

/**
 * 把单个汉字渲染为行内小篆图 HTML 字符串。
 * 找不到索引时回退为该字本身的文字（escape 后的安全文本）。
 * @param {string} ch 单个汉字
 * @param {object} [opts]
 * @param {string} [opts.assetBase='./字库/原始字形/']
 * @param {string} [opts.className='xiaozhuan-mark']
 * @param {string} [opts.boxStyle] 固定盒子内的 style 字符串；不传则用行内默认样式
 * @returns {string} img HTML 或 escape 后的文字
 */
/** 取第一个 Unicode 码点（处理 surrogate pair，如 𠎳） */
function firstCodePoint(str) {
  if (!str) return '';
  // 用 Array.from 能正确处理代理对
  return Array.from(String(str))[0] || '';
}

window.renderXiaozhuanChar = function (ch, opts = {}) {
  const assetBase = opts.assetBase ?? './字库/原始字形/';
  const className = opts.className ?? 'xiaozhuan-mark';
  const boxStyle = opts.boxStyle;
  const name = firstCodePoint(ch); // 取第一个 Unicode 码点
  if (!name) return '';
  const file = _indexCache?.[name];
  if (!file) {
    // 回退：escape 后的文字
    return String(ch ?? '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }
  const src = `${assetBase}${file}`;
  const style = boxStyle ?? IMG_STYLE;
  return `<img src="${src}" alt="${name} 小篆" data-xiaozhuan="${name}" style="${style}" class="${className}">`;
};

/**
 * 判断一个汉字是否在索引中（能找到小篆图）。
 * @param {string} ch
 * @returns {boolean}
 */
window.hasXiaozhuan = function (ch) {
  if (!ch) return false;
  return Boolean(_indexCache?.[firstCodePoint(ch)]);
};

/**
 * 取单字对应的小篆图 src 路径。找不到返回 null。
 * @param {string} ch
 * @param {string} [assetBase='./字库/原始字形/']
 * @returns {string|null}
 */
window.xiaozhuanSrc = function (ch, assetBase = './字库/原始字形/') {
  const name = firstCodePoint(ch);
  if (!name) return null;
  const file = _indexCache?.[name];
  if (!file) return null;
  return `${assetBase}${file}`;
};

/**
 * 返回 DocumentFragment（推荐用于生产环境，避免 innerHTML 注入）
 * @param {string} text
 * @param {object} [opts]
 * @param {Document} [opts.doc]
 * @returns {DocumentFragment}
 */
window.renderXiaozhuanNode = function (text, opts = {}) {
  const doc = opts.doc ?? document;
  const assetBase = opts.assetBase ?? './字库/原始字形/';
  const frag = doc.createDocumentFragment();
  let lastIndex = 0;
  for (const m of String(text).matchAll(MARK_RE)) {
    if (m.index > lastIndex) {
      frag.appendChild(doc.createTextNode(text.slice(lastIndex, m.index)));
    }
    const name = m[1];
    const file = _indexCache?.[name];
    if (file) {
      const img = doc.createElement('img');
      img.src = `${assetBase}${file}`;
      img.alt = `${name} 小篆`;
      img.dataset.xiaozhuan = name;
      img.className = 'xiaozhuan-mark';
      img.style.height = '1.2em';
      img.style.verticalAlign = 'middle';
      img.style.margin = '0 2px';
      frag.appendChild(img);
    } else {
      frag.appendChild(doc.createTextNode(m[0]));
    }
    lastIndex = m.index + m[0].length;
  }
  if (lastIndex < text.length) {
    frag.appendChild(doc.createTextNode(text.slice(lastIndex)));
  }
  return frag;
};
