import test from 'node:test';
import assert from 'node:assert/strict';
import * as views from '../web/js/mrmem_views.js';

test('MR-Mem full-shell projection preserves unknowns and escapes all native content', () => {
  const data={memory_count:1,segment_count:0,items:[{id:'<id>',text:'<script>fiction</script>',ts:null}],segments:[]};
  const home=views.render('home',data);
  assert.match(home,/question-grid/);
  assert.match(home,/时间未知/);
  assert.doesNotMatch(home,/<script>/);
  assert.doesNotMatch(home,/准确率|已确认命题/);
  assert.match(views.toc(data),/%3Cid%3E/);
  const detail=views.render('line',{...data.items[0],evidence:[{fingerprint:'"fiction'}],segments:[]});
  assert.match(detail,/data-kind="mrmem"/);
  assert.match(detail,/&quot;fiction/);
  const evidence=views.evidence({quote:'<fiction>',ts:null,role:'user',ref:{record_id:'r'}});
  assert.match(evidence,/&lt;fiction&gt;/);
  assert.doesNotMatch(evidence,/已到文档开头|已到文档结尾/);
});
