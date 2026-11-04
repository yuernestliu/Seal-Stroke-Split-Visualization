/* 抽签猜字：点「抽签」→ 抽签桶摇动动画 → 给出小篆谜面与谜语提示，四选一猜今字。
   谜语提示在 谜语数据.js 里按字形 id 补充；选项策略见 pickOptions，可后期调整。 */
(() => {
  const $ = s => document.querySelector(s);
  const SHAKE_MS = 900;

  let pool = [];
  let onReveal = null;
  let answer = null;
  let solved = false;
  let shaking = false;

  const shuffle = arr => arr.slice().sort(() => Math.random() - .5);

  /* 选项策略：优先取同部首（形式/意思相近）的字作干扰项，不够再随机补足。 */
  function pickOptions(glyph) {
    const same = pool.filter(g => g.id !== glyph.id && g.source?.section === glyph.source?.section);
    const rest = pool.filter(g => g.id !== glyph.id && g.source?.section !== glyph.source?.section);
    const distractors = [...shuffle(same), ...shuffle(rest)].slice(0, 3);
    return shuffle([glyph, ...distractors]);
  }

  function showStage() {
    answer = null; solved = false;
    $('#fortuneQuiz').hidden = true;
    $('#fortuneStage').hidden = false;
    $('#fortuneTip').textContent = '心里默想，点击抽签。';
    $('#fortuneDraw').disabled = false;
  }

  function showQuiz(glyph) {
    answer = glyph; solved = false;
    $('#fortuneStage').hidden = true;
    const quiz = $('#fortuneQuiz');
    quiz.hidden = false;
    const img = $('#fortuneImage');
    img.src = glyph.assets.original;
    img.alt = '抽到的小篆字形';
    const hints = (window.DRAW_RIDDLES || {})[glyph.id] || [];
    $('#fortuneHints').innerHTML = hints.length
      ? hints.map(h => `<li>${h}</li>`).join('')
      : '<li class="fortune-hint-empty">谜语提示待补充。</li>';
    const box = $('#fortuneOptions');
    box.replaceChildren();
    for (const option of pickOptions(glyph)) {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'fortune-option';
      btn.dataset.id = option.id;
      btn.innerHTML = `${option.mark}<small>${option.pinyin || ''}</small>`;
      btn.addEventListener('click', () => answerQuiz(btn, option));
      box.append(btn);
    }
    $('#fortuneResult').textContent = '';
    $('#fortuneReveal').hidden = true;
  }

  function answerQuiz(btn, option) {
    if (solved) return;
    if (option.id === answer.id) {
      solved = true;
      btn.classList.add('is-correct');
      document.querySelectorAll('.fortune-option').forEach(b => { b.disabled = true; });
      $('#fortuneResult').textContent = `答对了，就是「${answer.mark}」。`;
      $('#fortuneReveal').hidden = false;
    } else {
      btn.classList.remove('is-wrong');
      void btn.offsetWidth;
      btn.classList.add('is-wrong');
      $('#fortuneResult').textContent = '不对，再想想。';
    }
  }

  function draw() {
    if (shaking || !pool.length) return;
    shaking = true;
    $('#fortuneDraw').disabled = true;
    $('#fortuneTip').textContent = '抽签中…';
    const bucket = $('#fortuneBucket');
    bucket.classList.remove('is-shaking');
    void bucket.offsetWidth;
    bucket.classList.add('is-shaking');
    const glyph = pool[Math.floor(Math.random() * pool.length)];
    window.setTimeout(() => { shaking = false; showQuiz(glyph); }, SHAKE_MS);
  }

  function open(glyphPool, revealCallback) {
    pool = Array.isArray(glyphPool) ? glyphPool.filter(g => g?.assets?.original) : [];
    onReveal = typeof revealCallback === 'function' ? revealCallback : null;
    if (!pool.length) return;
    showStage();
    $('#fortuneDialog').showModal();
  }

  document.addEventListener('DOMContentLoaded', () => {
    $('#fortuneDraw').addEventListener('click', draw);
    $('#fortuneAgain').addEventListener('click', showStage);
    $('#fortuneReveal').addEventListener('click', () => {
      if (answer && onReveal) { $('#fortuneDialog').close(); onReveal(answer.id); }
    });
    $('#closeFortune').addEventListener('click', () => $('#fortuneDialog').close());
    $('#fortuneDialog').addEventListener('click', event => {
      if (event.target !== $('#fortuneDialog')) return;
      const rect = event.target.getBoundingClientRect();
      if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) event.target.close();
    });
  });

  window.FortuneDraw = { open };
})();
