import {read} from './db.js';
import {renderGraph} from './graph.js';
import {mountTimeline} from './timeline.js';
import * as views from './views.js';
import * as mrmem from './mrmem_views.js';

const main = document.getElementById('content');
const drawer = document.getElementById('evidence');
const drawerBody = document.getElementById('evidence-body');
const search = document.getElementById('search');
const results = document.getElementById('search-results');
let pageRequest, evidenceRequest, searchRequest, searchTimer;
let destroyGraph = () => {};
let destroyTimeline = () => {};
let pageVersion = 0, drawerVersion = 0, searchVersion = 0;
let searchSelection = -1;
let backendMode = "atlas";
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

// Fixed positioning keeps citation previews inside the viewport at either edge.
function positionQuote(ref) {
  const tooltip = ref.querySelector('.quote-tooltip');
  if (!tooltip || !tooltip.getClientRects().length) return;
  const anchor = ref.getBoundingClientRect();
  const box = tooltip.getBoundingClientRect();
  const margin = 8;
  const left = Math.max(margin, Math.min(anchor.left, innerWidth - box.width - margin));
  const above = anchor.top - box.height - margin;
  const top = Math.max(margin, Math.min(above >= margin ? above : anchor.bottom + margin, innerHeight - box.height - margin));
  tooltip.style.left = `${left}px`;
  tooltip.style.top = `${top}px`;
}
for (const event of ['pointerover','focusin']) main.addEventListener(event, e => {
  const ref = e.target.closest('.digest-ref');
  if (ref) positionQuote(ref);
});
const repositionQuotes = () => main.querySelectorAll('.digest-ref:hover,.digest-ref:focus-within').forEach(positionQuote);
window.addEventListener('resize', repositionQuotes);
window.addEventListener('scroll', repositionQuotes, true);

async function openEvidence(button) {
  closeEvidence();
  const version = ++drawerVersion;
  evidenceRequest = new AbortController();
  drawerBody.innerHTML = views.loading;
  drawer.showModal();
  try {
    const params = {kind: button.dataset.kind, id: button.dataset.id, sensitive: sensitive()};
    if (button.dataset.kind === 'mrmem') { params.index = button.dataset.index; params.fingerprint = button.dataset.fingerprint; }
    else if (button.dataset.kind.startsWith('digest_')) {
      params.doc_id = button.dataset.docId; params.quote = button.dataset.quote;
    } else { params.index = button.dataset.index; params.field = button.dataset.field; }
    const data = await read('evidence', params, evidenceRequest.signal);
    if (version === drawerVersion && drawer.open) drawerBody.innerHTML = data.verification ? mrmem.evidence(data) : views.evidenceView(data);
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
  searchSelection = -1;
  search.removeAttribute('aria-activedescendant');
  search.setAttribute('aria-expanded', 'false');
}

async function route() {
  const version = ++pageVersion;
  pageRequest?.abort();
  pageRequest = new AbortController();
  closeEvidence();
  clearSearch();
  destroyGraph();
  destroyTimeline();
  destroyTimeline = () => {};
  destroyGraph = () => {};
  main.innerHTML = views.loading;
  document.getElementById('toc').replaceChildren();
  let page, id;
  try { [page, id] = (location.hash.slice(2) || 'home').split('/').map(decodeURIComponent); }
  catch { main.innerHTML = views.empty('页面地址无效。'); return; }
  const pages = {home: ['概览', views.homeView], lines: ['判断线', views.linesView], line: ['判断线', views.lineView], entities: ['实体', views.entitiesView], entity: ['实体', views.entityView]};
  if (!pages[page]) { main.innerHTML = views.empty('页面不存在，请从左侧目录选择。'); return; }
  const [caption, render] = pages[page];
  document.getElementById('crumb').textContent = backendMode === 'mrmem' && ['line','lines'].includes(page) ? '记忆过程' : caption;
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
    backendMode = toc.backend || "atlas";
    mrmem.configureShell(backendMode);
    if (backendMode === "mrmem" && ["line","lines"].includes(page)) {
      document.getElementById("crumb").textContent = "记忆过程";
      document.title = "记忆过程 · ATLAS";
    }
    main.innerHTML = backendMode === "mrmem" ? mrmem.render(page, data) : render(data);
    globalThis.AtlasMotion?.enter(main);
    document.getElementById('toc').innerHTML = backendMode === 'mrmem' ? mrmem.toc(toc) : views.tocView(toc);
    document.getElementById('toc').classList?.toggle('long', toc.lines.length > 12);
    if (page === 'line' && backendMode !== 'mrmem') destroyTimeline = mountTimeline(main);
    if (page === 'entity' && backendMode !== 'mrmem') {
      const folded = main.querySelector('.digest-evidence');
      let dispose = () => {}, mounted = false;
      const mount = () => {
        if (mounted || (folded && !folded.open)) return;
        mounted = true;
        try { dispose = renderGraph(data); }
        catch { document.getElementById('graph-status').textContent = '关系图暂不可用，请阅读下方完整关系列表。'; }
      };
      folded?.addEventListener('toggle', mount);
      mount();
      destroyGraph = () => { folded?.removeEventListener('toggle', mount); dispose(); };
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
  searchSelection = -1;
  search.removeAttribute('aria-activedescendant');
  const query = search.value.trim();
  search.setAttribute('aria-expanded', query ? 'true' : 'false');
  if (!query) return;
  results.innerHTML = views.loading;
  searchTimer = setTimeout(async () => {
    searchRequest = new AbortController();
    try {
      const data = await read('search', {q: query, sensitive: sensitive()}, searchRequest.signal);
      if (version === searchVersion) {
        results.innerHTML = data.search_mode === 'mrmem_runtime' ? mrmem.search(data, query) : views.searchView(data, query);
        globalThis.AtlasMotion?.enter(results);
      }
    } catch (error) {
      if (error.name !== 'AbortError' && version === searchVersion) results.innerHTML = `<p role="alert">${views.esc(error.message)}</p>`;
    }
  }, 200);
});
search.addEventListener('focus', () => {
  if (!search.value.trim()) {
    results.innerHTML = '<p class="caption">输入关键词，搜索判断线、实体与记录。</p>';
    search.setAttribute('aria-expanded', 'true');
  }
});
search.addEventListener('keydown', event => {
  if (event.key === 'Escape') { clearSearch(); return; }
  if (!['ArrowDown','ArrowUp','Enter'].includes(event.key)) return;
  const links = [...results.querySelectorAll('a')];
  if (!links.length) return;
  if (event.key === 'Enter') {
    if (searchSelection >= 0) { event.preventDefault(); links[searchSelection].click(); }
    return;
  }
  event.preventDefault();
  searchSelection = event.key === 'ArrowDown' ? (searchSelection + 1) % links.length : (searchSelection <= 0 ? links.length - 1 : searchSelection - 1);
  links.forEach((a,i) => {a.classList.toggle('selected', i === searchSelection); a.setAttribute('aria-selected', String(i === searchSelection));});
  search.setAttribute('aria-activedescendant', links[searchSelection].id);
  links[searchSelection].scrollIntoView({block:'nearest'});
});
document.addEventListener('focusin', event => {
  if (!event.target.closest('.search-box')) clearSearch();
});
document.addEventListener('keydown', event => {
  const editing = ['INPUT','TEXTAREA','SELECT'].includes(event.target.tagName) || event.target.isContentEditable;
  if (!drawer.open && (((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') || (event.key === '/' && !editing))) {
    event.preventDefault(); search.focus(); search.select();
  }
});
document.addEventListener('click', event => {
  if (!event.target.closest('.search-box')) clearSearch();
  if (event.target.closest('.skip')) { event.preventDefault(); main.focus(); return; }
  const button = event.target.closest('button');
  if (button?.hasAttribute('data-evidence')) openEvidence(button);
  if (button?.hasAttribute('data-point')) {
    const point = document.getElementById('point-' + button.dataset.point);
    if (point) {
      // A target may be inside a collapsed list; open it before navigating.
      for (let parent = point.parentElement; parent; parent = parent.parentElement) {
        if (parent.tagName === 'DETAILS') parent.open = true;
      }
    }
    main.querySelectorAll('.axis-point').forEach(item => item.setAttribute('aria-current', String(item.dataset.point === button.dataset.point)));
    point?.scrollIntoView({behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block:'center'}); point?.focus({preventScroll:true});
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
  pageVersion++; pageRequest?.abort(); closeEvidence(); clearSearch(); destroyGraph(); destroyGraph = () => {}; destroyTimeline(); destroyTimeline = () => {};
  document.getElementById('sensitive').checked = false;
  main.replaceChildren(); document.getElementById('toc').replaceChildren();
}
window.addEventListener('pagehide', discard);
window.addEventListener('pageshow', event => { if (event.persisted) route(); });
document.addEventListener('visibilitychange', () => { if (document.hidden) closeEvidence(); });
route();
