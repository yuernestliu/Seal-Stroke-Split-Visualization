/* 自由描写：画布保留到切换字形或离开描写模式，不对书写正确性评分。 */
(() => {
  const canvas = document.querySelector('#traceCanvas');
  let context, drawing = false, activeGlyph = null, active = false, lastPoint;
  function clear() { if (context) context.clearRect(0, 0, canvas.width, canvas.height); }
  function resize() {
    if (!active) return;
    const rect = canvas.getBoundingClientRect();
    if (!rect.width || !rect.height) return;
    const snapshot = document.createElement('canvas'); snapshot.width = canvas.width; snapshot.height = canvas.height;
    if (context && canvas.width && canvas.height) snapshot.getContext('2d').drawImage(canvas, 0, 0);
    const ratio = Math.min(window.devicePixelRatio || 1, 3);
    canvas.width = Math.round(rect.width * ratio); canvas.height = Math.round(rect.height * ratio);
    context = canvas.getContext('2d');
    context.drawImage(snapshot, 0, 0, canvas.width, canvas.height);
    context.lineWidth = Math.max(4, rect.width / 40) * ratio;
    context.lineCap = 'round'; context.lineJoin = 'round'; context.strokeStyle = '#dfb57e';
  }
  function setMode(glyphId, enabled) {
    if (enabled && (!active || activeGlyph !== glyphId)) { active = true; activeGlyph = glyphId; context = canvas.getContext('2d'); clear(); resize(); }
    else if (!enabled) { active = false; drawing = false; activeGlyph = null; clear(); }
  }
  function point(event) {
    const rect = canvas.getBoundingClientRect();
    return [(event.clientX - rect.left) * canvas.width / rect.width, (event.clientY - rect.top) * canvas.height / rect.height];
  }
  canvas.addEventListener('pointerdown', event => {
    if (!active || (event.pointerType === 'mouse' && event.button !== 0)) return;
    event.preventDefault(); canvas.setPointerCapture(event.pointerId); drawing = true; lastPoint = point(event);
    context.beginPath(); context.moveTo(...lastPoint); context.lineTo(lastPoint[0] + .1, lastPoint[1] + .1); context.stroke();
  });
  canvas.addEventListener('pointermove', event => {
    if (!drawing) return; event.preventDefault();
    const next = point(event); context.beginPath(); context.moveTo(...lastPoint); context.lineTo(...next); context.stroke(); lastPoint = next;
  });
  for (const name of ['pointerup','pointercancel','lostpointercapture']) canvas.addEventListener(name, () => {drawing = false;});
  if (window.ResizeObserver) new ResizeObserver(() => resize()).observe(canvas);
  else window.addEventListener('resize', resize);
  window.GlyphTracing = {setMode, clear};
})();
