// Optional real-browser acceptance using only Node built-ins and an installed Chrome.
import test from 'node:test';
import assert from 'node:assert/strict';
import {existsSync} from 'node:fs';
import {mkdtemp,readFile,rm,writeFile,mkdir} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join,resolve,basename} from 'node:path';
import {spawn} from 'node:child_process';
import {setTimeout as delay} from 'node:timers/promises';
import {previewServer} from './ui_v2_fixture.mjs';
const chrome = process.env.ATLAS_TEST_CHROME || join(process.env.ProgramFiles || '', 'Google','Chrome','Application','chrome.exe');
test('MR-Mem browser: motion, keyboard, immediate evidence clearing and reduced motion', {skip:process.env.ATLAS_TEST_BROWSER !== '1' ? 'Set ATLAS_TEST_BROWSER=1 for the installed-Chrome render check' : !existsSync(chrome) ? 'Chrome is not installed' : false,timeout:60000}, async t => {
  const profile = await mkdtemp(join(tmpdir(),'atlas-ui-browser-'));
  const {server,url,requests,setDigests} = await previewServer({mrmem:true});
  const child = spawn(chrome,['--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check','--disable-background-networking','--disable-sync','--disable-extensions','--remote-debugging-port=0',`--user-data-dir=${profile}`,'about:blank'],{windowsHide:true,stdio:['ignore','ignore','pipe']});
  child.stderr.on('data',chunk=>{if(process.env.ATLAS_BROWSER_DEBUG) process.stderr.write(chunk);});
  let ws;
  t.after(async () => {
    ws?.close(); child.kill(); server.close();
    // Only remove the unique temporary browser profile created by this test.
    assert.equal(resolve(profile).startsWith(resolve(tmpdir())),true);
    assert.ok(basename(profile).startsWith('atlas-ui-browser-'));
    await rm(profile,{recursive:true,force:true,maxRetries:20,retryDelay:100});
  });
  let port;
  for (let i=0;i<100;i++) {try {port=(await readFile(join(profile,'DevToolsActivePort'),'utf8')).split('\n')[0];break;} catch {await delay(100);}}
  assert.ok(port,'Chrome must start its local debugging endpoint');
  const targets=await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
  ws=new WebSocket(targets.find(x=>x.type==='page').webSocketDebuggerUrl);
  await new Promise((res,rej)=>{ws.onopen=res;ws.onerror=rej;});
  let serial=0; const pending=new Map(); const errors=[];
  ws.onmessage=event=>{
    const msg=JSON.parse(event.data);
    if(msg.id){const [res,rej]=pending.get(msg.id)||[];pending.delete(msg.id);msg.error?rej?.(msg.error):res?.(msg.result);}
    if(msg.method==='Runtime.exceptionThrown') errors.push(msg.params.exceptionDetails.text);
    if(msg.method==='Runtime.consoleAPICalled' && ['error','warning'].includes(msg.params.type)) errors.push(msg.params.args.map(a=>a.value).join(' '));
  };
  const call=(method,params={})=>new Promise((res,rej)=>{const id=++serial;const timer=setTimeout(()=>{pending.delete(id);rej(new Error(`CDP timeout: ${method} ${params.expression || ''}`));},10000);pending.set(id,[value=>{clearTimeout(timer);res(value);},err=>{clearTimeout(timer);rej(err);}]);ws.send(JSON.stringify({id,method,params}));});
  const evaluate=async expression=>{const r=await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});assert.ok(!r.exceptionDetails,JSON.stringify(r.exceptionDetails));return r.result.value;};
  const wait=async expression=>{for(let i=0;i<100;i++){if(await evaluate(expression))return;await delay(50);}assert.fail(`UI condition timed out: ${expression}`);};
  const screenshot=async name=>{if(process.env.ATLAS_UI_SCREENSHOTS){await mkdir(process.env.ATLAS_UI_SCREENSHOTS,{recursive:true});const r=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});await writeFile(join(process.env.ATLAS_UI_SCREENSHOTS,`${name}.png`),Buffer.from(r.data,'base64'));}};

  await call('Runtime.enable'); await call('Page.enable');
  await call('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false});
  await call('Page.navigate',{url:url+'/mrmem.html'});
  await wait('!!globalThis.AtlasMotion');
  await evaluate("document.getElementById('query').value='虚构'; document.getElementById('find').requestSubmit()");
  await wait('!!document.querySelector("#results article button")');
  await evaluate('document.querySelector("#results article button").click()');
  await wait('document.getElementById("status").textContent === "SB 已更新"');
  assert.ok(await evaluate('document.getElementById("detail").getAnimations().length > 0'));
  await delay(220);
  await screenshot('mrmem-desktop');
  await evaluate('[...document.querySelectorAll("#detail button")].find(b=>b.textContent.startsWith("原文证据")).click()');
  await wait('document.getElementById("drawer").open');
  await delay(280);
  assert.equal(await evaluate('Math.round(document.getElementById("drawer").getBoundingClientRect().right)'),1440);
  await screenshot('mrmem-evidence');
  // Escape follows the native dialog path and clears contents without waiting for an exit.
  await call('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});
  await call('Input.dispatchKeyEvent',{type:'keyUp',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});
  await wait('!document.getElementById("drawer").open');
  await wait('document.getElementById("quote").textContent === ""');
  await call('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-motion',value:'reduce'}]});
  await evaluate('AtlasMotion.enter(document.getElementById("detail"), "detail")');
  assert.equal(await evaluate('document.getElementById("detail").getAnimations().some(a=>a.effect.getKeyframes().some(k=>k.transform && k.transform !== "none"))'),false);
  await delay(100);
  for (const width of [390,768]) {
    await call('Emulation.setDeviceMetricsOverride',{width,height:844,deviceScaleFactor:1,mobile:true});
    assert.equal(await evaluate('document.documentElement.scrollWidth <= innerWidth'),true);
    await evaluate('[...document.querySelectorAll("#detail button")].find(b=>b.textContent.startsWith("原文证据")).click()');
    await wait('document.getElementById("drawer").open');
    assert.equal(await evaluate('getComputedStyle(document.getElementById("drawer")).transform'),'none');
    await screenshot(`mrmem-evidence-reduced-${width}`);
    await evaluate('document.getElementById("close").click()');
    await wait('!document.getElementById("drawer").open');
    assert.equal(await evaluate('document.getElementById("quote").textContent'), '');
  }
  assert.deepEqual(errors,[]);
});
