import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
const folio=require('../web/js/folio_ledger.js');
test('sealed folio retains historical author metadata and detects altered Unicode originals',()=>{
 const text='虚构园丁：保留原文 🌿';
 assert.equal(folio.sha256(text),createHash('sha256').update(text).digest('hex'));
 const sha=folio.sha256(text);
 const doc={genesis:'GENESIS',trust:{aiMayWrite:{original:false}},entries:[{id:'fiction',status:'live',versions:[{role:'original',origin:'verbatim',author:'fictional historical author',text,sha256:sha}],chain_prev:'GENESIS',chain:folio.chainLink('GENESIS',sha,'fiction'),annotations:[]}]};
 assert.deepEqual(folio.verify(doc),[]);
 doc.entries[0].versions[0].text+=' altered';
 assert.ok(folio.verify(doc).some(x=>x.includes('sha mismatch')));
});
