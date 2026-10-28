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
    showModal() { this.open = true; }
    close() { this.open = false; queueMicrotask(()=>this.emit('close')); }
  }
  const ids = Object.fromEntries(['content','evidence','evidence-body','search','search-results','sensitive','theme','toc','crumb','close-evidence'].map(id=>[id,new Element()]));
  const doc = new Element();
  doc.getElementById = id => ids[id];
  doc.querySelectorAll = () => [];
  doc.documentElement = new Element();
  const win = new Element(); win.scrollTo = () => {};
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
  win.emit('pagehide');
  assert.equal(ids.content.innerHTML,'');
  assert.equal(ids.toc.innerHTML,'');
});
