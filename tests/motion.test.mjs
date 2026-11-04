import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFileSync} from 'node:fs';

test('motion cancels interrupted selections and honors live reduced-motion changes', () => {
  const events = {}, mediaEvents = {};
  const preference = {matches:false,addEventListener(name,fn) {mediaEvents[name]=fn;}};
  const document = {hidden:false,addEventListener(name,fn) {events[name]=fn;}};
  const context = {document,matchMedia:()=>preference};
  vm.runInNewContext(readFileSync(new URL('../web/js/motion.js',import.meta.url),'utf8'),context);
  const animations = [];
  const element = {animate(frames,options) {
    const animation = {frames,options,cancel() {this.cancelled=true;this.oncancel?.();}};
    animations.push(animation); return animation;
  }};
  context.AtlasMotion.enter(element,'detail');
  assert.equal(animations[0].options.duration,180);
  context.AtlasMotion.enter(element,'detail');
  assert.equal(animations[0].cancelled,true);
  preference.matches=true; mediaEvents.change();
  assert.equal(animations[1].cancelled,true);
  context.AtlasMotion.enter(element,'detail');
  assert.equal(animations[2].options.duration,70);
  assert.equal(animations[2].frames.some(frame=>'transform' in frame),false);
  document.hidden=true; events.visibilitychange();
  assert.equal(animations[2].cancelled,true);
  context.AtlasMotion.enter(element);
  assert.equal(animations.length,3);
  assert.doesNotThrow(()=>context.AtlasMotion.enter({}));
});
