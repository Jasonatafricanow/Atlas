export const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[char]));
export const gap = '<span class="gap">数据库暂无该字段</span>';
export const empty = (message = '暂无可显示的记录。') => `<div class="empty">${esc(message)}</div>`;
export const loading = '<div class="loading" role="status">正在读取本地记录…<i></i><i></i><i></i></div>';
const labels = {first:'首次记录', same:'维持', strengthen:'加强', weaken:'减弱', reverse:'转向', new_angle:'新角度', unclear:'未判明', confirmed:'后续支持', refuted:'后续反驳', mixed:'部分支持', unknown:'结果未定', proposed:'待确认', rejected:'已否定', superseded:'已取代', model:'模型标注', repaired:'修复标注', fallback:'回退标注', person:'人物', concept:'概念', place:'地点', event:'事件', instrument:'标的', topic:'主题', fact:'事实', opinion:'观点', preference:'偏好', plan:'计划'};
const label = value => esc(labels[value] || value || '未记录');
const date = value => esc(value || '时间未知');
const badge = value => `<span class="badge ${['confirmed','refuted','reverse','mixed'].includes(value) ? value : ''}">${label(value)}</span>`;
export const link = (route, id) => `#/${route}/${encodeURIComponent(id)}`;
const title = (kicker, heading, caption) => `<header class="page-head"><p class="eyebrow">${kicker}</p><h1>${esc(heading)}</h1><p class="lede">${caption}</p></header>`;
const identity = source => source.prop_id || source.statement_id || source.node_id || source.edge_id;
const kind = source => source.prop_id ? 'propositions' : source.statement_id ? 'statements' : source.node_id ? 'nodes' : 'edges';
export function evidenceButtons(source) {
  return ['evidence','counter_evidence'].map(field => (source[field] || []).map((_, index) => `<button class="evidence-button" data-evidence data-kind="${kind(source)}" data-id="${esc(identity(source))}" data-field="${field}" data-index="${index}">${field === 'counter_evidence' ? '反证' : '证据'} ${index + 1} ↗</button>`).join('')).join('');
}
const valid = source => `<p class="meta">有效期：${date(source.valid_from)} — ${source.valid_to ? date(source.valid_to) : '结束时间未记录'}</p>`;
const proposition = p => `<article class="record" id="prop-${esc(p.prop_id)}"><div class="record-meta">${badge(p.status)} ${label(p.kind)} · 置信度 ${p.confidence == null ? gap : esc(p.confidence)}</div><h3>${esc(p.text)}</h3>${valid(p)}${p.user_note ? `<p>用户补充：${esc(p.user_note)}</p>` : ''}${p.suppressed_by ? '<p class="meta">用户已否定；保留历史记录。</p>' : ''}<div class="actions">${evidenceButtons(p)}</div></article>`;
const nodeName = (nodes, id) => nodes.find(n => n.node_id === id)?.name || id;
const changed = point => point.annotations.some(a => ['strengthen','weaken','reverse','new_angle'].includes(a.shift));

export function tocView(data) {
  return data.lines.map(l => `<a href="${link('line', l.topic_node_id)}">${esc(l.name)}</a>`).join('') || '<p class="meta">暂无已归档判断线</p>';
}

export function homeView(data) {
  const changes = data.lines.flatMap(line => line.timeline.filter(changed).map(point => ({line, point})))
    .sort((a,b) => (Date.parse(b.point.source.ts) || 0) - (Date.parse(a.point.source.ts) || 0)).slice(0,4);
  const outcomes = data.lines.flatMap(line => line.timeline.filter(p => p.annotations.some(a => ['confirmed','refuted','mixed'].includes(a.outcome))).map(point => ({line,point}))).slice(0,3);
  const pending = data.propositions.filter(p => p.status === 'proposed' && !p.suppressed_by);
  const portraits = data.propositions.filter(p => p.status === 'confirmed' && !p.suppressed_by).slice(0,3);
  const row = ({line,point}) => `<a class="question-row" href="${link('line',line.topic_node_id)}"><span class="meta">${date(point.source.ts)} · ${esc(nodeName(data.nodes,line.topic_node_id))}</span><span>${esc(point.source.text)}</span></a>`;
  return title('从四个问题开始', '把记录连成理解', '先看变化，再看依据。这里展示已存储的判断，不替你补写结论。') +
    `<div class="question-grid"><section class="question-card"><div class="card-number">01 / 变化</div><h2>最近观点变了什么？</h2><p class="caption">按已知时间展示最近标注的变化；未知时间不推测。</p>${changes.map(row).join('') || empty('暂无已记录的观点变化。')}<a class="more" href="#/lines">沿时间展开判断 →</a></section>
    <section class="question-card"><div class="card-number">02 / 核对</div><h2>过去的判断，后来怎样？</h2><p class="caption">对错总数与准确率：${gap}。点级结果是记录中的标注，不等同于事实认证。</p>${outcomes.map(row).join('') || empty('暂无后续支持或反驳的标注。')}<a class="more" href="#/lines">查看后续依据 →</a></section>
    <section class="question-card"><div class="card-number">03 / 画像</div><h2>哪些认识最稳定？</h2><p class="caption">稳定性排序：${gap}。下方仅列已确认命题；置信度不代表稳定性。</p>${portraits.map(proposition).join('') || empty('暂无已确认的画像命题。')}</section>
    <section class="question-card"><div class="card-number">04 / 待确认</div><h2>还有什么需要确认？</h2><p class="caption">来自待确认命题；此页只读。纠正请使用现有 CLI 或离线导出流程。</p>${pending.slice(0,4).map(proposition).join('') || empty('暂无待确认命题。')}${pending.length > 4 ? '<p class="meta">此处显示前四条，可通过搜索查找其余命题。</p>' : ''}</section></div>`;
}

export function linesView(data) {
  return title('判断线 / 主题目录', '同一个问题，沿时间展开', '同一主题的批次合为一条线。只展示已存储的归属；零散表态不会被自动编成新主题。') +
    `<div class="line-list">${data.lines.map(line => `<a class="line-card" href="${link('line',line.topic_node_id)}"><span class="eyebrow">主题 · ${line.timeline.length} 条记录</span><h2>${esc(nodeName(data.nodes,line.topic_node_id))}</h2><p>${esc(line.timeline[0]?.source.text)}</p><span class="meta">${date(line.timeline[0]?.source.ts)} — ${date(line.timeline.at(-1)?.source.ts)}</span><span class="more">展开判断线 →</span></a>`).join('') || empty('暂无已存储的判断线。请先在已有任务流程中生成并合并判断线。')}</div>`;
}

function annotationView(a, index, pointIds) {
  const boundary = index > 0 && a.shift === 'first';
  return `<div class="annotation">${badge(a.shift)}<span class="meta">${a.shift_source ? label(a.shift_source) : '标注来源未记录'}${boundary ? ' · 批次起点，与上一条的变化未评估' : ''}</span><p>${esc(a.reason) || gap}</p><div class="outcome">${badge(a.outcome)}<span>${esc(a.outcome_reason) || '暂无可用的后续解释。'}</span></div>${(a.outcome_statement_ids || []).length ? `<div class="support-links">后续依据：${a.outcome_statement_ids.map(id => pointIds.has(id) ? `<button data-point="${esc(id)}">定位记录 ↗</button>` : '<span class="meta">依据不在本主题，未展开</span>').join(' ')}</div>` : ''}</div>`;
}

export function lineView({line, node}) {
  const ids = new Set(line.timeline.map(p => p.statement_id));
  return title('判断线 / 时间与依据', node.name, '正文是已存储的表态。点开证据查看原文；后续支持与反驳只表示已有标注。') +
    `<div class="line-facts"><span>演化摘要：${gap}</span><span>当前立场：${gap}</span><span>对错总数：${gap}</span></div>
    <nav class="axis" aria-label="按时间定位记录">${line.timeline.map((p,i) => `<button class="axis-point ${changed(p) ? 'change' : ''}" data-point="${esc(p.statement_id)}"><span class="axis-dot"></span><span>${date(p.source.ts)}</span><small>${esc(p.source.stance) || '立场未记录'} · ${i+1}</small></button>`).join('')}</nav><p class="axis-caption">时间点按顺序等距排列；未知时间置前，不推算间隔或立场。</p>
    <ol class="stream">${line.timeline.map((p,i) => `<li class="event ${changed(p) ? 'change' : ''}" id="point-${esc(p.statement_id)}" tabindex="-1"><div class="event-date">${date(p.source.ts)}<span>${String(i+1).padStart(2,'0')}</span></div><article class="event-body"><div class="record-meta">${esc(p.source.speaker) || '说话人未知'} · ${label(p.source.kind)}${p.source.status ? ' · ' + label(p.source.status) : ''}</div><h2>${esc(p.source.text)}</h2>${p.annotations.map(a => annotationView(a,i,ids)).join('')}<div class="actions">${evidenceButtons(p.source) || '<span class="meta">暂无证据指针</span>'}</div></article></li>`).join('')}</ol>
    <details class="source-lines"><summary>查看原始批次标题与来源</summary>${line.lines.map(l => `<p>${esc(l.title)} <code>${esc(l.line_id)}</code></p>`).join('')}</details>`;
}

export function entitiesView(data) {
  return title('实体 / 连接与提及', '从一个实体开始', '选择人物、概念或主题，查看局部关系与引用它的记录。') + `<div class="entity-list">${data.nodes.map(n => `<a class="entity-card" href="${link('entity',n.node_id)}"><span class="eyebrow">${label(n.type)}</span><h2>${esc(n.name)}</h2><span class="more">查看关系与反链 →</span></a>`).join('') || empty()}</div>`;
}

export function entityView(data) {
  const n = data.node;
  return title('实体 / ' + label(n.type), n.name, '局部图展示直接相连的实体。点击节点打开档案；下方保留关系方向、有效期与历史状态。') +
    `<div class="entity-layout"><section class="panel"><h2>实体档案</h2><p>摘要：${gap}</p><p>别名：${data.aliases.length ? data.aliases.map(a=>esc(a.name)).join('、') : gap}</p>${valid(n)}<div class="actions">${evidenceButtons(n)}</div><h3>相关判断线</h3>${data.lines.map(l=>`<a class="question-row" href="${link('line',l.topic_node_id)}">${esc(l.lines[0]?.title || l.topic_node_id)} →</a>`).join('') || empty('暂无关联判断线。')}</section>
    <section class="panel graph-panel"><div class="panel-head"><h2>局部关系图</h2><button data-fit>居中</button></div><p class="caption">一跳邻居 · 箭头表示方向 · 虚线为历史关系</p><div id="graph" role="img" aria-label="局部关系图，文字关系见下方列表"></div><p id="graph-status" class="meta"></p></section></div>
    <section class="reading-section"><h2>关系与有效期</h2>${data.edges.map(e => `<article class="record ${e.status === 'superseded' ? 'historical' : ''}"><h3><a href="${link('entity',e.src)}">${esc(nodeName(data.nodes,e.src))}</a> → ${esc(e.type)} → <a href="${link('entity',e.dst)}">${esc(nodeName(data.nodes,e.dst))}</a></h3><p class="meta">状态：${label(e.status)}</p>${valid(e)}<div class="actions">${evidenceButtons(e)}</div></article>`).join('') || empty('暂无相连关系。')}</section>
    <section class="reading-section"><h2>哪些记录提到了它？</h2><p class="caption">反链来自实体关联，不推测未关联的原文提及。</p>${data.statements.map(s=>`<article class="record"><p class="meta">${date(s.ts)} · ${esc(s.speaker) || '说话人未知'}</p><h3>${esc(s.text)}</h3><div class="actions">${evidenceButtons(s)}</div></article>`).join('') || empty('暂无关联表态。')}</section><section class="reading-section"><h2>关联画像命题</h2>${data.propositions.map(proposition).join('') || empty('暂无关联命题。')}</section>`;
}

export function searchView(data) {
  return data.results.map(item => item.node ? `<a href="${link('entity',item.node.node_id)}"><small>实体 · ${label(item.node.type)}</small>${esc(item.node.name)}</a>` : item.line ? `<a href="${link('line',item.line.topic_node_id)}"><small>判断线</small>${esc(item.line.name)}</a>` : `<a href="${item.proposition.subject_node_ids[0] ? link('entity',item.proposition.subject_node_ids[0]) : '#/home'}"><small>画像命题</small>${esc(item.proposition.text)}</a>`).join('') + (data.truncated ? '<p class="meta">仅显示前 100 项，请缩小搜索范围。</p>' : '') || empty('未找到匹配记录。');
}

export function evidenceView(data) {
  return `<p class="meta">${esc(data.channel) || '来源会话：数据库暂无该字段'}<br>${date(data.ts)} · ${esc(data.author) || '作者未记录'}</p>${data.quote !== undefined ? `<h3>原文</h3><blockquote>${esc(data.quote)}</blockquote><h3>相邻上下文</h3><p class="context">${esc(data.before) || '已到文档开头'}</p><p class="context highlight">${esc(data.quote)}</p><p class="context">${esc(data.after) || '已到文档结尾'}</p><p class="caption">上下文最多展示前后各 240 个字符；作者与时间为文档元数据，不推定为引文说话人和时间。</p>` : `<p>原文与上下文：${gap}</p>`}<details><summary>证据指针与校验</summary><pre>${esc(JSON.stringify(data.pointer,null,2))}</pre><p class="caption">原文仅在哈希校验通过后显示。</p></details><p class="drawer-note">仅在打开时读取。关闭即清除本页中的原文与上下文。</p>`;
}
