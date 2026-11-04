'use strict';
const byId = id => document.getElementById(id);
let version = 0;
let evidenceVersion = 0;
function clearEvidence() {
  evidenceVersion++;
  byId('drawer').close();
  byId('quote').textContent = '';
}
async function api(route, params) {
  const response = await fetch(`/api/${route}?${new URLSearchParams(params)}`, {cache:'no-store'});
  if (!response.ok) throw new Error(`读取失败 (${response.status})`);
  return response.json();
}
function text(parent, tag, value) {
  const element = document.createElement(tag);
  element.textContent = value;
  parent.append(element);
  return element;
}
function error(e) { byId('status').textContent = e.message; }
async function detail(id, selectedVersion) {
  clearEvidence();
  const data = await api('detail', {id});
  if (selectedVersion !== version) return;
  const root = byId('detail');
  root.replaceChildren();
  text(root, 'h2', 'SB');
  text(root, 'p', data.text);
  text(root, 'p', data.ts || '时间未知');
  text(root, 'h3', '关联成熟段（保留版本）');
  if (!data.segments.length) text(root, 'p', '暂无关联成熟段');
  for (const segment of data.segments) {
    text(root, 'p', segment.summary);
    text(root, 'small', `段版本顺序 ${segment.last_seq}`);
    for (const member of segment.member_ids) {
      const button = text(root, 'button', member === id ? '当前 SB' : '查看关联 SB');
      button.disabled = member === id;
      button.onclick = () => { const selection = ++version; detail(member, selection).catch(error); };
    }
  }
  data.evidence.forEach((ref, index) => {
    const button = text(root, 'button', `原文证据 ${index + 1}`);
    button.onclick = async () => {
      clearEvidence();
      const token = evidenceVersion;
      try {
        const source = await api('evidence', {id,index,fingerprint:ref.fingerprint});
        if (token !== evidenceVersion || selectedVersion !== version) return;
        byId('quote').textContent = `${source.ts || '时间未知'} · ${source.role}\n${source.quote}`;
        byId('drawer').showModal();
      } catch (e) { error(e); }
    };
  });
}
byId('find').onsubmit = async event => {
  event.preventDefault();
  const token = ++version;
  clearEvidence();
  byId('detail').replaceChildren();
  byId('results').replaceChildren();
  try {
    const data = await api('search', {q:byId('query').value});
    if (token !== version) return;
    byId('status').textContent = `显示 ${data.items.length} 项`;
    for (const item of data.items) {
      if (data.search_mode === 'mrmem_runtime') {
        const article = document.createElement('article');
        byId('results').append(article);
        text(article, 'p', item.text);
        if (!item.memory_ids.length) text(article, 'small', '原生读出 · 暂无可验证 SB 跳转');
        for (const id of item.memory_ids) {
          const button = text(article, 'button', '查看 SB 与证据');
          button.onclick = () => { const selection = ++version; detail(id, selection).catch(error); };
        }
      } else {
        const button = text(byId('results'), 'button', item.text);
        button.onclick = () => { const selection = ++version; detail(item.id, selection).catch(error); };
      }
    }
  } catch (e) { error(e); }
};
byId('close').onclick = clearEvidence;
byId('drawer').addEventListener('close', () => { evidenceVersion++; byId('quote').textContent = ''; });
document.addEventListener('visibilitychange', () => { if (document.hidden) clearEvidence(); });
