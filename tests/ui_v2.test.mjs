import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import * as views from '../web/js/views.js';

const point = {statement_id:'fiction-s0', source:{statement_id:'fiction-s0',text:'虚构试种',about:['fiction-topic'],ts:null,evidence:[]}, annotations:[{shift:'first',outcome:'unknown'}]};
const line = {topic_node_id:'fiction-topic',lines:[{line_id:'fiction-line',title:'虚构主题'}],timeline:[point]};
const node = {node_id:'fiction-topic',name:'虚构主题',type:'topic'};

test('views preserve unknowns and escape source text and identifiers', () => {
  const html = views.lineView({line,node});
  assert.match(html,/时间未知/);
  assert.match(html,/数据库暂无该字段/);
  assert.match(html,/标注来源未记录/);
  assert.doesNotMatch(html,/模型标注/);
  const hostile = {quote:'<img src=x onerror="alert(1)">',pointer:{doc_id:'<fiction>'}};
  const evidence = views.evidenceView(hostile);
  assert.doesNotMatch(evidence,/<img/);
  assert.match(evidence,/&lt;img/);
  assert.match(views.evidenceView({pointer:{}}),/数据库暂无该字段/);
  assert.match(views.linesView({lines:[],nodes:[]}),/暂无已存储的判断线/);
  assert.doesNotMatch(views.homeView({lines:[],nodes:[],propositions:[]}),/虚构主题/);
});

test('batch starts remain explicitly unassessed after merging', () => {
  const html = views.lineView({node,line:{...line,timeline:[point,{...point,statement_id:'fiction-s1'}]}});
  assert.match(html,/批次起点，与上一条的变化未评估/);
  assert.doesNotMatch(html,/badge reverse/);
});

test('local graph dependencies load offline and compute finite positions', () => {
  const sandbox = {console,setTimeout,clearTimeout,performance};
  sandbox.self = sandbox;
  vm.createContext(sandbox);
  for (const name of ['cytoscape','layout-base','cose-base','cytoscape-fcose']) {
    vm.runInContext(readFileSync(new URL(`../web/js/vendor/${name}.js`,import.meta.url),'utf8'),sandbox);
  }
  vm.runInContext(`
    var graph = cytoscape({headless:true,elements:[{data:{id:'a'}},{data:{id:'b'}},{data:{id:'ab',source:'a',target:'b'}}]});
    graph.layout({name:'fcose',animate:false}).run();
    var positions = graph.nodes().map(n=>n.position());
    graph.destroy();
  `,sandbox);
  for (const p of sandbox.positions) assert.ok(Number.isFinite(p.x) && Number.isFinite(p.y));
});

test('drawer cancellation and navigation discard late evidence; only theme persists', async () => {
  class Element {
    constructor() { this.listeners = {}; this.dataset = {}; this.value = ''; this.checked = false; this.innerHTML = ''; this.open = false; this.tagName = 'DIV'; }
    addEventListener(name,fn) { (this.listeners[name] ||= []).push(fn); }
    emit(name,event={}) { for (const fn of this.listeners[name] || []) fn(event); }
    replaceChildren() { this.innerHTML = ''; }
    focus() { document.activeElement = this; }
    select() {}
    setAttribute() {}
    removeAttribute() {}
    querySelectorAll() { return []; }
    showModal() { this.open = true; }
    close() { this.open = false; queueMicrotask(()=>this.emit('close')); }
  }
  const ids = Object.fromEntries(['content','evidence','evidence-body','search','search-results','sensitive','theme','toc','crumb','close-evidence'].map(id=>[id,new Element()]));
  const doc = new Element();
  doc.getElementById = id => ids[id];
  doc.querySelectorAll = () => [];
  doc.documentElement = new Element();
  const win = new Element(); win.scrollTo = () => {}; win.matchMedia = () => ({matches:false});
  globalThis.document = doc; globalThis.window = win; globalThis.location = {hash:'#/home'};
  const storage = new Map();
  globalThis.localStorage = {getItem:key=>storage.get(key),setItem:(key,value)=>storage.set(key,value)};
  const requests = []; const pending = [];
  globalThis.fetch = (url,options) => {
    requests.push({url,options});
    const route = new URL(url,'http://localhost').pathname;
    if (route === '/api/evidence') return new Promise(resolve=>pending.push(resolve));
    return Promise.resolve({ok:true,json:async()=>route === '/api/toc' ? {lines:[],nodes:[]} : {lines:[],nodes:[],propositions:[]}});
  };
  const tick = () => new Promise(resolve=>setImmediate(resolve));
  await import('../web/js/app.js'); await tick();
  assert.equal(requests.filter(r=>r.url.includes('/evidence')).length,0);
  const button = new Element(); button.dataset = {kind:'statements',id:'fiction-s0',field:'evidence',index:'0'};
  button.hasAttribute = name => name === 'data-evidence';
  const clickEvidence = () => doc.emit('click',{target:{closest:selector=>selector === 'button' ? button : null}});
  clickEvidence();
  assert.equal(ids.evidence.open,true);
  ids['close-evidence'].emit('click');
  pending.shift()({ok:true,json:async()=>({quote:'late fictional evidence',pointer:{}})});
  await tick();
  assert.equal(ids.evidence.open,false);
  assert.equal(ids['evidence-body'].innerHTML,'');
  clickEvidence();
  pending.shift()({ok:true,json:async()=>({quote:'visible fictional evidence',pointer:{}})});
  await tick();
  assert.match(ids['evidence-body'].innerHTML,/visible fictional evidence/);
  win.emit('hashchange'); await tick();
  assert.equal(ids['evidence-body'].innerHTML,'');
  assert.equal(storage.size,0);
  ids.theme.emit('click'); await tick();
  assert.deepEqual([...storage.keys()],['atlas-theme']);
  assert.ok(requests.every(r=>r.options.cache === 'no-store'));
  let prevented = false;
  doc.emit('keydown',{target:{tagName:'DIV'},key:'/',preventDefault(){prevented=true;}});
  assert.equal(prevented,true);
  assert.equal(doc.activeElement,ids.search);
  let scrolled;
  ids['point-fiction-jump'] = new Element();
  ids['point-fiction-jump'].scrollIntoView = options => {scrolled=options;};
  const jump = new Element(); jump.dataset={point:'fiction-jump'};
  jump.hasAttribute = name => name === 'data-point';
  doc.emit('click',{target:{closest:selector=>selector === 'button' ? jump : null}});
  assert.equal(scrolled.block,'center');
  assert.equal(doc.activeElement,ids['point-fiction-jump']);
  win.emit('pagehide');
  assert.equal(ids.content.innerHTML,'');
  assert.equal(ids.toc.innerHTML,'');
});

// Shared formatter is independent of machine timezone and preserves unknown precision.
test('time formatter validates calendar dates and keeps source wall-clock precision', async () => {
  const {formatTime} = await import('../web/js/time.js');
  const now = new Date(2026, 5, 1);
  assert.equal(formatTime('2024-11-08T16:27:49+08:00',now),'2024-11-08 16:27');
  assert.equal(formatTime('2026-11-08T16:27:00Z',now),'11-08 16:27');
  assert.equal(formatTime('2026-11-08 16:27',now),'11-08 16:27');
  assert.equal(formatTime('2024-02-29',now),'2024-02-29');
  for (const value of [null,'','unknown','2025-02-29','2024-02-30','2024-13-01','2024-01-01T24:00','2024-01-01T01:60','2024-01-01T01:00+24:00',0]) {
    assert.equal(formatTime(value,now),'时间未知');
  }
});

test('timeline visible range follows internal scroll, resize and partial points', async () => {
  const {visibleRange} = await import('../web/js/timeline.js');
  const bounds = Array.from({length:24},(_,i)=>({start:i*160,end:(i+1)*160}));
  assert.deepEqual(visibleRange(bounds,0,480),{first:1,last:3,total:24});
  assert.deepEqual(visibleRange(bounds,320,1120),{first:3,last:9,total:24});
  assert.deepEqual(visibleRange(bounds,350,280),{first:3,last:4,total:24});
  assert.deepEqual(visibleRange(bounds,3360,480),{first:22,last:24,total:24});
  assert.deepEqual(visibleRange([],0,480),{first:0,last:0,total:0});
});

test('timeline indicator updates from DOM geometry and releases listeners on departure', async () => {
  const {mountTimeline} = await import('../web/js/timeline.js');
  let onScroll, onResize, disconnected = false, removed = false;
  const axis = {
    scrollLeft:0, clientLeft:0, clientWidth:336,
    getBoundingClientRect:()=>({left:50}),
    querySelectorAll:()=>Array.from({length:24},(_,i)=>({getBoundingClientRect:()=>({left:50+i*168-axis.scrollLeft,right:50+(i+1)*168-axis.scrollLeft})})),
    addEventListener:(name,fn)=>{assert.equal(name,'scroll');onScroll=fn;},
    removeEventListener:(name,fn)=>{removed=name==='scroll' && fn===onScroll;},
  };
  const indicator = {};
  const previous = globalThis.ResizeObserver;
  globalThis.ResizeObserver = class {constructor(fn){onResize=fn;} observe(){} disconnect(){disconnected=true;}};
  try {
    const destroy = mountTimeline({querySelector:selector=>selector==='.axis' ? axis : indicator});
    assert.equal(indicator.textContent,'第 1–2 / 24 点');
    axis.scrollLeft=336; onScroll();
    assert.equal(indicator.textContent,'第 3–4 / 24 点');
    axis.clientWidth=504; onResize();
    assert.equal(indicator.textContent,'第 3–5 / 24 点');
    destroy(); assert.ok(disconnected && removed);
  } finally {globalThis.ResizeObserver=previous;}
});

test('entity graph caps single and two-node views and recenters on resize', async () => {
  const {renderGraph} = await import('../web/js/graph.js');
  const saved = Object.fromEntries(['document','getComputedStyle','cytoscape','ResizeObserver'].map(key=>[key,globalThis[key]]));
  try {
    for (const size of [1,2]) {
      let options, fit=0, center=0, resize, disposed=false;
      globalThis.document={getElementById:()=>({}),documentElement:{},querySelector:()=>null};
      globalThis.getComputedStyle=()=>({getPropertyValue:key=>({'--graph-center':'44px','--graph-min':'20px','--graph-max':'32px','--fs-xs':'12px','--dur-graph':'150ms'}[key] || '1')});
      globalThis.cytoscape=opts=>{options=opts;return {on(){},fit(_elements,padding){assert.equal(padding,45);fit++;},center(){center++;},resize(){},destroy(){disposed=true;}};};
      globalThis.ResizeObserver=class {constructor(fn){resize=fn;} observe(){} disconnect(){}};
      const destroy=renderGraph({node,nodes:Array.from({length:size},(_,i)=>({...node,node_id:`fiction-${i}`})),edges:[]});
      assert.equal(options.maxZoom,1);
      assert.equal(options.style.find(s=>s.selector==='node').style.width,'data(size)');
      assert.equal(options.style.find(s=>s.selector==='node.focus').style.width,44);
      assert.equal(fit,1); assert.equal(center,1);
      resize(); assert.equal(fit,2); assert.equal(center,2);
      destroy(); assert.ok(disposed);
    }
  } finally {Object.assign(globalThis,saved);}
});

test('derived facts render escaped, with common time formatting and contained axis', () => {
  const derived={current_stance:'<fictional>',shift_count:2,outcome_counts:{supported:1,contradicted:2,unknown:3},time_span:{first:'2024-11-08T16:27:00Z',last:'2025-01-08T10:00:00Z'}};
  const html=views.lineView({node,line:{...line,derived,timeline:Array.from({length:24},(_,i)=>({...point,statement_id:`fiction-${i}`,source:{...point.source,ts:'2024-11-08T16:27:00Z'}}))}});
  assert.match(html,/派生/); assert.match(html,/&lt;fictional&gt;/);
  assert.match(html,/支持 1 · 反驳 2 · 未知 3/);
  assert.match(html,/2024-11-08 16:27/); assert.doesNotMatch(html,/16:27:00Z/);
  assert.equal((html.match(/class="axis-point /g)||[]).length,24);
  assert.match(html,/data-axis-position/);
  assert.match(html,/data-point="fiction-23"/);
  const css=readFileSync(new URL('../web/theme.css',import.meta.url),'utf8');
  assert.match(css,/\.axis\{[^}]*width:100%[^}]*overflow-x:auto/);
  assert.match(css,/\.timeline-panel\{[^}]*min-width:0[^}]*overflow:hidden/);
  const dark=css.match(/:root\[data-theme="dark"\]\s*\{([^}]+)\}/)[1];
  for (const hex of dark.match(/#[0-9a-f]{6}\b/g)) {
    const r=parseInt(hex.slice(1,3),16),b=parseInt(hex.slice(5,7),16);
    assert.ok(r>=b,`warm palette: ${hex}`);
  }
});


test('round 4 accuracy and stability show derived values and small-sample gaps', () => {
  const base = {outcome_counts:{supported:2,contradicted:1,unknown:1},accuracy_basis:'已知 3 / 共 4',accuracy:2/3,stability:0.5};
  const html = views.lineView({node,line:{...line,derived:base}});
  assert.match(html,/派生/); assert.match(html,/准确率 66.7%/); assert.match(html,/稳定性：50.0%/);
  const small = views.lineView({node,line:{...line,derived:{...base,accuracy:null,accuracy_basis:'已知 2 / 共 4',stability:null}}});
  assert.match(small,/已知 2 \/ 共 4/); assert.doesNotMatch(small,/准确率 [0-9]/);
  assert.match(small,/至少需要 3 个点/);
});

test('pending items honor backend priority and escape template questions', () => {
  const props = ['low','high'].map(id=>({prop_id:id,text:`fiction-${id}`,status:'proposed',subject_node_ids:[]}));
  const html = views.homeView({lines:[],nodes:[],propositions:props,derived:{outcome_counts:{},pending_items:[
    {prop_id:'high',priority:1,affected_line_count:3,question:'<fiction-question>'},
    {prop_id:'low',priority:2,affected_line_count:0,question:'fiction-followup'}]}});
  assert.ok(html.indexOf('fiction-high') < html.indexOf('fiction-low'));
  assert.match(html,/派生/); assert.match(html,/优先级 1 · 影响 3 条/);
  assert.match(html,/&lt;fiction-question&gt;/); assert.doesNotMatch(html,/<fiction-question>/);
});

test('entity mention backlinks are lazy drawer actions and suggestions never execute', () => {
  const mentionRef = 'fiction-ref';
  const data = {node,nodes:[node],edges:[],aliases:[],lines:[],statements:[],propositions:[],
    mentions_index_available:true,mention_count:1,
    mentions:[{doc_id:'fiction-doc',display_name:'<fiction-session>',associated_node_count:3,ts:null,token:mentionRef}],
    merge_suggestions:[{a_node_id:node.node_id,b_node_id:'fiction-other',rule:'cooccurrence',score:.6}]};
  const html = views.entityView(data);
  assert.match(html,/提及 <span class="meta">来自提及索引 · 1/); assert.match(html,/&lt;fiction-session&gt;/); assert.match(html,/时间未知 · 关联节点 3/);
  assert.match(html,/data-kind="mentions"/); assert.match(html,/data-field="fiction-ref"/);
  assert.match(html,/建议合并（未执行）/); assert.doesNotMatch(html,/data-merge/);
  assert.match(html,/<dt>摘要<\/dt><dd><span class="gap">数据库暂无该字段/);
  const empty = views.entityView({...data,mentions:[],mention_count:0,mentions_index_available:false});
  assert.match(empty,/尚未建立提及索引/);
  const ref = views.evidenceView({ref:{kind:'message_paragraphs',record_id:'<fiction>',paragraphs:[0,2]}});
  assert.match(ref,/message_paragraphs/); assert.match(ref,/&lt;fiction&gt;/);
});

// Round 5 design contract: colors and type live only in the two root token blocks.
test('design tokens are complete and component colors and font sizes are variable-only', () => {
  const css=readFileSync(new URL('../web/theme.css',import.meta.url),'utf8');
  const blocks=[...css.matchAll(/:root(?:\[data-theme="dark"\])?\s*\{([^}]+)\}/g)];
  assert.equal(blocks.length,2);
  const tokens=new Set([...blocks[0][1].matchAll(/(--[\w-]+)\s*:/g)].map(m=>m[1]));
  for(const name of ['bg','bg-sunken','surface','surface-2','ink','ink-2','ink-3','ink-4','line','line-strong','accent','accent-hover','accent-weak','accent-ink','focus','confirmed','confirmed-bg','refuted','refuted-bg','change','change-bg','unknown','unknown-bg','font-serif','font-sans','font-mono','fs-xs','fs-sm','fs-base','fs-md','fs-lg','fs-xl','fs-2xl','sp-1','sp-2','sp-3','sp-4','sp-5','sp-6','sp-8','sp-10','sp-12','r-sm','r-md','r-lg','r-pill','shadow-1','shadow-2','dur-1','dur-2']) assert.ok(tokens.has(`--${name}`),name);
  const components=css.replace(/:root(?:\[data-theme="dark"\])?\s*\{[^}]+\}/g,'');
  assert.doesNotMatch(components, /#[\da-f]{3,8}\b|\brgba?\(|\bhsla?\(/i);
  assert.doesNotMatch(components, /font(?:-size)?\s*:[^;}]*\d+(?:px|rem|em)/);
  for(const match of blocks[0][1].matchAll(/--fs-[\w-]+\s*:\s*(\d+)px/g)) assert.ok(Number(match[1])>=12);
  for(const match of css.matchAll(/var\((--[\w-]+)/g)) assert.ok(tokens.has(match[1]),`undefined token ${match[1]}`);
  assert.doesNotMatch(css,/radial-gradient|0 0 13px/);
});

test('search groups and literal highlights escape hostile text and regex syntax', () => {
  assert.equal(views.highlight('<fiction> [a].*','[a].*'),'&lt;fiction&gt; <mark>[a].*</mark>');
  assert.equal(views.highlight('Fiction fiction','fiction'),'<mark>Fiction</mark> <mark>fiction</mark>');
  const html=views.searchView({results:[{node},{line:{name:'虚构主题',topic_node_id:node.node_id}},{proposition:{text:'虚构判断',subject_node_ids:[]}}]},'虚构');
  assert.equal((html.match(/class="search-group"/g)||[]).length,3);
  assert.equal((html.match(/<mark>虚构<\/mark>/g)||[]).length,3);
});

test('expanded mentions keep original indices and timeline changes retain their annotations', () => {
  const mentions=Array.from({length:10},(_,i)=>({doc_id:`fiction-${i}`,token:`fiction-ref-${i}`,associated_node_count:1}));
  const html=views.entityView({node,nodes:[node],edges:[],aliases:[],lines:[],statements:[],propositions:[],mentions,mention_count:10,mentions_index_available:true});
  assert.match(html,/展开 5 条/);
  assert.match(html,/data-index="9" data-field="fiction-ref-9"/);
  const timeline=Array.from({length:10},(_,i)=>({...point,statement_id:`fiction-${i}`,annotations:[{shift:i===1?'reverse':'same',outcome:'unknown',reason:'fictional annotation'}]}));
  const stream=views.lineView({node,line:{...line,timeline}});
  assert.match(stream,/class="event change" id="point-fiction-1"/);
  assert.match(stream,/class="annotation-details"/);
  assert.match(stream,/class="stream-more"><details><summary>展开 5 条/);
  assert.match(stream,/id="point-fiction-9"/);
  assert.match(stream,/fictional annotation/);
});
