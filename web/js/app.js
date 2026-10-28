import {read} from './db.js';
import {renderGraph} from './graph.js';
import * as views from './views.js';

const main = document.getElementById('content');
const drawer = document.getElementById('evidence');
const drawerBody = document.getElementById('evidence-body');
const search = document.getElementById('search');
const results = document.getElementById('search-results');
let pageRequest, evidenceRequest, searchRequest, searchTimer;
let destroyGraph = () => {};
let pageVersion = 0, drawerVersion = 0, searchVersion = 0;
const sensitive = () => document.getElementById('sensitive').checked ? '1' : '0';
const errorView = error => `<div class="empty" role="alert">${views.esc(error.message)} <button data-retry>重试</button></div>`;

function setTheme(theme) {
  document.documentElement.dataset.theme = theme === 'dark' ? 'dark' : 'light';
  document.getElementById('theme').textContent = theme === 'dark' ? '浅色' : '深色';
  document.getElementById('theme').setAttribute('aria-label', theme === 'dark' ? '切换浅色主题' : '切换深色主题');
}
try { setTheme(localStorage.getItem('atlas-theme')); } catch { setTheme('light'); }

function closeEvidence() {
  drawerVersion++;
  evidenceRequest?.abort();
  evidenceRequest = undefined;
  drawerBody.replaceChildren();
  if (drawer.open) drawer.close();
}
drawer.addEventListener('cancel', event => { event.preventDefault(); closeEvidence(); });
drawer.addEventListener('close', () => {
  // A native close event may arrive after a different record has already opened.
  if (!drawer.open) { evidenceRequest?.abort(); drawerBody.replaceChildren(); }
});
document.getElementById('close-evidence').addEventListener('click', closeEvidence);

async function openEvidence(button) {
  closeEvidence();
  const version = ++drawerVersion;
  evidenceRequest = new AbortController();
  drawerBody.innerHTML = views.loading;
  drawer.showModal();
  try {
    const data = await read('evidence', {kind: button.dataset.kind, id: button.dataset.id,
      index: button.dataset.index, field: button.dataset.field, sensitive: sensitive()}, evidenceRequest.signal);
    if (version === drawerVersion && drawer.open) drawerBody.innerHTML = views.evidenceView(data);
  } catch (error) {
    if (error.name !== 'AbortError' && version === drawerVersion && drawer.open) drawerBody.innerHTML = `<p role="alert">${views.esc(error.message)}</p>`;
  }
}

function clearSearch() {
  searchVersion++;
  clearTimeout(searchTimer);
  searchRequest?.abort();
  results.replaceChildren();
  search.value = '';
}

async function route() {
  const version = ++pageVersion;
  pageRequest?.abort();
  pageRequest = new AbortController();
  closeEvidence();
  clearSearch();
  destroyGraph();
  destroyGraph = () => {};
  main.innerHTML = views.loading;
  document.getElementById('toc').replaceChildren();
  let page, id;
  try { [page, id] = (location.hash.slice(2) || 'home').split('/').map(decodeURIComponent); }
  catch { main.innerHTML = views.empty('页面地址无效。'); return; }
  const pages = {home: ['概览', views.homeView], lines: ['判断线', views.linesView], line: ['判断线', views.lineView], entities: ['实体', views.entitiesView], entity: ['实体', views.entityView]};
  if (!pages[page]) { main.innerHTML = views.empty('页面不存在，请从左侧目录选择。'); return; }
  const [caption, render] = pages[page];
  document.getElementById('crumb').textContent = caption;
  document.title = `${caption} · ATLAS`;
  document.querySelectorAll('.primary a').forEach(a => {
    const active = a.hash === '#/' + (page === 'line' ? 'lines' : page === 'entity' ? 'entities' : page);
    a.classList.toggle('active', active);
    if (active) a.setAttribute('aria-current','page'); else a.removeAttribute('aria-current');
  });
  try {
    const [data, toc] = await Promise.all([
      read(page, {id: id || '', sensitive: sensitive()}, pageRequest.signal),
      read('toc', {sensitive: sensitive()}, pageRequest.signal),
    ]);
    if (version !== pageVersion) return;
    main.innerHTML = render(data);
    document.getElementById('toc').innerHTML = views.tocView(toc);
    if (page === 'entity') {
      try { destroyGraph = renderGraph(data); }
      catch { document.getElementById('graph-status').textContent = '关系图暂不可用，请阅读下方完整关系列表。'; }
    }
    main.focus({preventScroll:true});
    window.scrollTo({top:0});
  } catch (error) {
    if (error.name !== 'AbortError' && version === pageVersion) main.innerHTML = errorView(error);
  }
}

search.addEventListener('input', () => {
  const version = ++searchVersion;
  clearTimeout(searchTimer);
  searchRequest?.abort();
  results.replaceChildren();
  const query = search.value.trim();
  if (!query) return;
  results.innerHTML = views.loading;
  searchTimer = setTimeout(async () => {
    searchRequest = new AbortController();
    try {
      const data = await read('search', {q: query, sensitive: sensitive()}, searchRequest.signal);
      if (version === searchVersion) results.innerHTML = views.searchView(data);
    } catch (error) {
      if (error.name !== 'AbortError' && version === searchVersion) results.innerHTML = `<p role="alert">${views.esc(error.message)}</p>`;
    }
  }, 200);
});
search.addEventListener('keydown', event => { if (event.key === 'Escape') clearSearch(); });
document.addEventListener('keydown', event => {
  const editing = ['INPUT','TEXTAREA','SELECT'].includes(event.target.tagName) || event.target.isContentEditable;
  if (!drawer.open && (((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') || (event.key === '/' && !editing))) {
    event.preventDefault(); search.focus(); search.select();
  }
});
document.addEventListener('click', event => {
  if (event.target.closest('.skip')) { event.preventDefault(); main.focus(); return; }
  const button = event.target.closest('button');
  if (button?.hasAttribute('data-evidence')) openEvidence(button);
  if (button?.hasAttribute('data-point')) {
    const point = document.getElementById('point-' + button.dataset.point);
    point?.scrollIntoView({behavior:'smooth', block:'center'}); point?.focus({preventScroll:true});
  }
  if (button?.hasAttribute('data-retry')) route();
});
document.getElementById('theme').addEventListener('click', () => {
  const theme = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
  setTheme(theme);
  try { localStorage.setItem('atlas-theme', theme); } catch { /* Storage may be disabled. */ }
  route(); // The graph receives fresh data and colors; no page content cache.
});
document.getElementById('sensitive').addEventListener('change', route);
window.addEventListener('hashchange', route);
function discard() {
  pageVersion++; pageRequest?.abort(); closeEvidence(); clearSearch(); destroyGraph(); destroyGraph = () => {};
  document.getElementById('sensitive').checked = false;
  main.replaceChildren(); document.getElementById('toc').replaceChildren();
}
window.addEventListener('pagehide', discard);
window.addEventListener('pageshow', event => { if (event.persisted) route(); });
document.addEventListener('visibilitychange', () => { if (document.hidden) closeEvidence(); });
route();
