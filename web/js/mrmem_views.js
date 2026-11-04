import {esc, link, empty, highlight} from './views.js';
import {formatTime} from './time.js';

const when = value => esc(formatTime(value));
const heading = (title, caption) => `<header class="page-head"><h1>${esc(title)}</h1><p class="lede">${esc(caption)}</p></header>`;
const memory = item => `<article class="record"><p class="meta">${when(item.ts)}</p><h3><a href="${link('line',item.id)}">${esc(item.text)}</a></h3><a class="digest-source" href="${link('line',item.id)}">查看 SB 与证据 ↗</a></article>`;
const segment = item => `<article class="record"><p class="meta">成熟段 · 保留来源版本顺序 ${esc(item.last_seq)}</p><p>${esc(item.summary)}</p><div class="actions">${item.member_ids.map((id,i)=>`<a href="${link('line',id)}">关联 SB ${i+1}</a>`).join(' · ')}</div></article>`;

export function configureShell(mode) {
  if (mode !== 'mrmem') return;
  const nav = document.querySelector?.('.primary a[href="#/lines"]');
  if (nav) nav.innerHTML = '记忆过程 <span>02</span>';
  const label = document.querySelector?.('.section-label');
  if (label) label.textContent = '记忆目录';
  const searchLabel = document.querySelector?.('.search-label');
  if (searchLabel) searchLabel.textContent = 'MR-Mem 原生搜索';
  const footer = document.querySelector?.('footer');
  if (footer) footer.textContent = '本地阅读 · 理解沿记忆过程，核对回到原文';
  const brand = document.querySelector?.('.brand span');
  if (brand) brand.textContent = '个人记忆';
  const note = document.querySelector?.('.sidebar-note');
  if (note) note.textContent = '沿着记忆过程理解，回到原文核对来源。';
  const sensitive = document.getElementById('sensitive');
  if (sensitive) {
    sensitive.disabled = true;
    sensitive.title = '当前 MR-Mem 接口未提供敏感分类过滤；按固定用户作用域读取';
  }
}

export function toc(data) {
  return data.items.slice(0,30).map(item=>`<a href="${link('line',item.id)}" title="${esc(item.text)}">${esc(item.text.slice(0,36))}</a>`).join('') || empty('暂无可验证记忆');
}

export function render(page, data) {
  if (page === 'entities' || page === 'entity') {
    return heading('实体与画像', '当前后端的能力边界') + empty(data.message);
  }
  if (page === 'line') {
    return heading('记忆详情', 'SB 是对来源的理解，具体细节请核对原文。') +
      `<article class="digest-card"><h2>${esc(data.text)}</h2><p class="meta">${when(data.ts)}</p><div class="actions">${data.evidence.map((ref,index)=>`<button data-evidence data-kind="mrmem" data-id="${esc(data.id)}" data-index="${index}" data-fingerprint="${esc(ref.fingerprint)}">原文证据 ${index+1} ↗</button>`).join('')}</div></article>` +
      `<h2>关联成熟段</h2>${data.segments.map(segment).join('') || empty('暂无可验证的关联成熟段。')}`;
  }
  if (page === 'lines') return heading('记忆过程', '成熟段保留各自版本；不将原生 Line 重新命名为主题判断线。') +
    (data.segments.map(segment).join('') || empty('暂无可验证成熟段，下面展示已有 SB。')) +
    '<h2>已有 SB</h2>' + (data.items.map(memory).join('') || empty());
  return heading('把记录连成理解', '从已有记忆开始，沿成熟段理解经过，再回到原文核对。') +
    `<div class="nums"><div><strong>${esc(data.memory_count)}</strong><span>可验证记忆</span></div><div><strong>${esc(data.segment_count)}</strong><span>成熟段版本</span></div></div>` +
    `<div class="question-grid"><section class="question-card"><h2>记忆过程</h2>${data.segments.slice(0,3).map(segment).join('') || empty('尚无成熟段，保留未知。')}<a class="digest-source" href="#/lines">查看全部记忆过程 ↗</a></section>` +
    `<section class="question-card"><h2>已有记忆</h2>${data.items.slice(0,6).map(memory).join('') || empty('暂无可验证记忆。')}</section></div>`;
}

export function search(data, query) {
  let index = 0;
  return data.items.map(item=>`<section class="search-group"><p>${highlight(item.text, query)}</p>${item.memory_ids.map(id=>`<a role="option" aria-selected="false" id="search-result-${index++}" href="${link('line',id)}">查看 SB 与证据 ↗</a>`).join('') || '<p class="meta">原生读出暂无可验证 SB 跳转</p>'}</section>`).join('') || empty('未找到匹配记录。');
}

export function evidence(data) {
  return `<p class="meta">${when(data.ts)} · ${esc(data.role || '作者未记录')}</p><h3>来源消息原文</h3><blockquote>${esc(data.quote)}</blockquote><details><summary>来源指针与校验</summary><pre>${esc(JSON.stringify(data.ref,null,2))}</pre><p>用户作用域、来源版本与内容指纹已校验；显示整条来源消息。</p></details><p class="drawer-note">关闭即清除原文。</p>`;
}
