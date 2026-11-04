// Optional real-browser acceptance using only Node built-ins and an installed Chrome.
import test from 'node:test';
import assert from 'node:assert/strict';
import {existsSync} from 'node:fs';
import {mkdtemp,readFile,rm,writeFile,mkdir} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join,resolve,basename} from 'node:path';
import {spawn} from 'node:child_process';
import {setTimeout as delay} from 'node:timers/promises';

const chrome = process.env.ATLAS_TEST_CHROME || join(process.env.ProgramFiles || '', 'Google','Chrome','Application','chrome.exe');
test('Original full Atlas: archive lenses, real native runtime and sealed folio', {skip:process.env.ATLAS_TEST_BROWSER !== '1' ? 'Set ATLAS_TEST_BROWSER=1 for the installed-Chrome render check' : !existsSync(chrome) ? 'Chrome is not installed' : false,timeout:60000}, async t => {
  const profile = await mkdtemp(join(tmpdir(),'atlas-ui-browser-'));
  const fixture=await mkdtemp(join(tmpdir(),'atlas-full-fixture-'));
  const fixtureProcess=spawn(process.env.ATLAS_TEST_PYTHON || 'python',['-B','examples/tasks_demo/full_original.py','--out-dir',fixture],{windowsHide:true,stdio:['ignore','ignore','pipe']});
  let fixtureErrors='';fixtureProcess.stderr.on('data',c=>fixtureErrors+=c);
  const server={close(){fixtureProcess.kill();}};
  t.after(async()=>{server.close();assert.ok(resolve(fixture).startsWith(resolve(tmpdir())));assert.ok(basename(fixture).startsWith('atlas-full-fixture-'));await rm(fixture,{recursive:true,force:true,maxRetries:20,retryDelay:100});});
  let ready;
  for(let i=0;i<150;i++){try{ready=JSON.parse(await readFile(join(fixture,'ready.json'),'utf8'));break;}catch{if(fixtureProcess.exitCode!==null)assert.fail(fixtureErrors);await delay(100);}}
  assert.ok(ready,fixtureErrors || 'Native fixture must start');
  const {ui:url}=ready;
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
    if(msg.method==='Runtime.exceptionThrown') errors.push(msg.params.exceptionDetails.exception?.description || msg.params.exceptionDetails.text);
    if(msg.method==='Runtime.consoleAPICalled' && ['error','warning'].includes(msg.params.type)) errors.push(msg.params.args.map(a=>a.value).join(' '));
  };
  const call=(method,params={})=>new Promise((res,rej)=>{const id=++serial;const timer=setTimeout(()=>{pending.delete(id);rej(new Error(`CDP timeout: ${method} ${params.expression || ''}`));},10000);pending.set(id,[value=>{clearTimeout(timer);res(value);},err=>{clearTimeout(timer);rej(err);}]);ws.send(JSON.stringify({id,method,params}));});
  const evaluate=async expression=>{const r=await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});assert.ok(!r.exceptionDetails,JSON.stringify(r.exceptionDetails));return r.result.value;};
  const wait=async expression=>{for(let i=0;i<100;i++){if(await evaluate(expression))return;await delay(50);}assert.fail(`UI condition timed out: ${expression}`);};
  const screenshot=async name=>{if(process.env.ATLAS_UI_SCREENSHOTS){await mkdir(process.env.ATLAS_UI_SCREENSHOTS,{recursive:true});const r=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});await writeFile(join(process.env.ATLAS_UI_SCREENSHOTS,`${name}.png`),Buffer.from(r.data,'base64'));}};



  await call('Runtime.enable'); await call('Page.enable');
  await call('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false});
  await call('Page.navigate',{url});
  await wait('!!document.querySelector("#nav button") || document.getElementById("main").textContent.includes("失败")');
  
  assert.equal(await evaluate('document.getElementById("main").textContent.includes("界面载入失败")'),false);
  await screenshot('original-overview');
  for (const lens of ['graph','reader','state','consist','topic','portrait']) {
    await evaluate(`document.querySelector('[data-l="${lens}"]').click()`);
    await delay(180);
    assert.ok(await evaluate('document.getElementById("main").textContent.length > 0'));
  }
  await evaluate('document.querySelector("[data-l=native]").click()');
  await wait('!!document.getElementById("native-find")');
  await evaluate('document.getElementById("native-q").value="flowers";document.getElementById("native-find").requestSubmit()');
  await wait('!!document.querySelector("[data-memory]")');
  await evaluate('document.querySelector("[data-memory]").click()');
  await wait('!!document.querySelector("[data-native-evidence]")');
  await evaluate('document.querySelector("[data-native-evidence]").click()');
  await wait('!!document.querySelector("#drawer.open blockquote")');
  await screenshot('original-native-evidence');
  await evaluate('document.getElementById("close-original").click()');
  assert.equal(await evaluate('document.getElementById("dbody").innerHTML'),'');
  await evaluate('document.querySelector("[data-l=evolution]").click()');
  await wait('document.getElementById("runtime-body").textContent.includes("成熟段")');
  await evaluate('document.querySelector("[data-l=sources]").click()');
  await wait('!!document.getElementById("native-next")');
  await screenshot('original-native-sources');
  await evaluate('document.querySelector("[data-l=operations]").click()');
  await wait('!!document.getElementById("runtime-health")');
  await evaluate('document.getElementById("runtime-health").click()');
  await wait('document.getElementById("runtime-status").textContent.includes("ok")');
  await screenshot('original-runtime-operations');
  await evaluate(`document.querySelector('#runtime-add [name=session]').value='fiction-browser';document.querySelector('#runtime-add [name=content]').value='Fictional purple flowers in a small garden.';document.getElementById('runtime-add').requestSubmit()`);
  await wait('document.getElementById("runtime-result").textContent.includes("success")');
  await evaluate('document.getElementById("runtime-flush-all").checked=true;document.getElementById("runtime-flush-all").dispatchEvent(new Event("change"));document.getElementById("runtime-flush").click()');
  await wait('document.getElementById("runtime-result").textContent.includes("ok")');
  await call('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
  assert.equal(await evaluate('document.documentElement.scrollWidth <= innerWidth'),true);
  await screenshot('original-mobile');
  await call('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false});
  await call('Page.navigate',{url:url+'/folio.html'});
  await wait('document.getElementById("fatal")?.textContent || document.getElementById("sheet")?.textContent.includes("虚构试种")');
  
  assert.equal(await evaluate('document.getElementById("fatal").textContent'),'');
  assert.equal(await evaluate('document.getElementById("seal")?.textContent.includes("裂") || document.body.textContent.includes("处对不上")'),false);
  await screenshot('original-folio');
  await evaluate('document.getElementById("marginDraft").value="虚构旁注：继续记录，不改原文。";document.getElementById("marginDraft").dispatchEvent(new Event("input",{bubbles:true}));document.querySelector("form[data-action=save-note]").requestSubmit()');
  await wait('document.getElementById("foot").textContent.includes("旁注已保存")');
  await call('Page.reload');
  await wait('document.getElementById("margin")?.textContent.includes("虚构旁注：继续记录")');
  assert.deepEqual(errors,[]);
});
