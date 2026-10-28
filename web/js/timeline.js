// Actual element bounds accommodate font changes, resizing and long timelines.
export function visibleRange(bounds, scrollLeft, width) {
  const left = Math.max(0, scrollLeft);
  const visible = bounds.map((b,i) => b.end > left + 0.5 && b.start < left + width - 0.5 ? i + 1 : 0).filter(Boolean);
  return {first: visible[0] || 0, last: visible.at(-1) || 0, total: bounds.length};
}

export function mountTimeline(root) {
  const axis = root.querySelector('.axis');
  const indicator = root.querySelector('[data-axis-position]');
  if (!axis || !indicator) return () => {};
  const update = () => {
    const origin = axis.getBoundingClientRect().left + axis.clientLeft;
    const bounds = [...axis.querySelectorAll('.axis-point')].map(item => {
      const rect = item.getBoundingClientRect();
      return {start: rect.left - origin + axis.scrollLeft, end: rect.right - origin + axis.scrollLeft};
    });
    const range = visibleRange(bounds, axis.scrollLeft, axis.clientWidth);
    indicator.textContent = range.total ? `第 ${range.first}–${range.last} / ${range.total} 点` : '暂无时间点';
  };
  axis.addEventListener('scroll', update, {passive:true});
  const observer = new ResizeObserver(update);
  observer.observe(axis);
  update();
  return () => { observer.disconnect(); axis.removeEventListener('scroll', update); };
}
