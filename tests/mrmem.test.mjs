import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

function page() {
  const elements = new Map();
  const element = () => ({children:[], textContent:'', value:'',
    append(child) { this.children.push(child); },
    replaceChildren() { this.children = []; },
    addEventListener() {}, close() { this.open = false; }, showModal() { this.open = true; }});
  const requests = [];
  const events = {};
  const document = {getElementById(id) {
    if (!elements.has(id)) elements.set(id, element());
    return elements.get(id);
  }, createElement:element, addEventListener(name, fn) { events[name] = fn; }};
  const context = {document, URLSearchParams, fetch(url) {
    return new Promise(resolve => requests.push({url, finish(data) { resolve({ok:true,json:async()=>data}); }}));
  }};
  vm.runInNewContext(readFileSync(new URL('../web/js/mrmem.js', import.meta.url),'utf8'),context);
  return {get:document.getElementById,requests,events,document};
}
const tick = () => new Promise(resolve => setImmediate(resolve));

test('MR-Mem reader clears evidence and rejects late responses after navigation', async () => {
  const p = page();
  const search = p.get('find').onsubmit({preventDefault(){}});
  p.requests.shift().finish({items:[{id:'m',text:'<fictional SB>'}]});
  await search;
  assert.equal(p.get('results').children[0].textContent,'<fictional SB>');
  p.get('results').children[0].onclick();
  p.requests.shift().finish({text:'fiction',ts:null,segments:[],evidence:[{fingerprint:'fp'}]});
  await tick();
  const evidence = p.get('detail').children.at(-1).onclick();
  const pending = p.requests.shift();
  const next = p.get('find').onsubmit({preventDefault(){}});
  pending.finish({quote:'must not reappear',role:'user',ts:null});
  await evidence;
  assert.equal(p.get('quote').textContent,'');
  assert.equal(p.get('drawer').open,false);
  p.requests.shift().finish({items:[]});
  await next;
});

test('MR-Mem reader clears open evidence when hidden', async () => {
  const p = page();
  p.get('quote').textContent='fictional private source';
  p.get('drawer').open=true;
  p.document.hidden=true;
  p.events.visibilitychange();
  assert.equal(p.get('quote').textContent,'');
  assert.equal(p.get('drawer').open,false);
});
