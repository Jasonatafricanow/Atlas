/* Shared, interruptible feedback. Content stays visible without this enhancement. */
globalThis.AtlasMotion = (() => {
  const running = new WeakMap();
  const preference = globalThis.matchMedia?.('(prefers-reduced-motion: reduce)');
  const active = new Set();
  function cancel(element) {
    const animation = running.get(element);
    animation?.cancel();
    running.delete(element);
    active.delete(animation);
  }
  function enter(element, kind = 'content') {
    if (!element?.animate || document.hidden) return;
    cancel(element);
    const reduced = preference?.matches;
    const frames = reduced ? [{opacity:0.65}, {opacity:1}] : kind === 'detail'
      ? [{opacity:0.55, transform:'translateX(6px)'}, {opacity:1, transform:'translateX(0)'}]
      : [{opacity:0.65}, {opacity:1}];
    const animation = element.animate(frames, {
      duration:reduced ? 70 : kind === 'detail' ? 180 : 140,
      easing:'cubic-bezier(0.16, 1, 0.3, 1)',
    });
    running.set(element, animation);
    active.add(animation);
    const done = () => {
      active.delete(animation);
      if (running.get(element) === animation) running.delete(element);
    };
    animation.onfinish = animation.oncancel = done;
  }
  function stopAll() { for (const animation of [...active]) animation.cancel(); active.clear(); }
  preference?.addEventListener('change', stopAll);
  document.addEventListener('visibilitychange', () => { if (document.hidden) stopAll(); });
  return {enter, cancel};
})();
