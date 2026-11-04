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
test('MR-Mem full shell: overview, navigation, native search, evidence and themes', {skip:process.env.ATLAS_TEST_BROWSER !== '1' ? 'Set ATLAS_TEST_BROWSER=1 for the installed-Chrome render check' : !existsSync(chrome) ? 'Chrome is not installed' : false,timeout:60000}, async t => {
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
  await call('Page.navigate',{url});
  await wait('document.querySelector(".primary a:nth-child(2)").textContent.includes("记忆过程")');
  assert.equal(await evaluate('document.querySelectorAll(".sidebar").length'),1);
  assert.equal(await evaluate('document.querySelector(".nums").textContent.includes("可验证记忆")'),true);
  assert.equal(await evaluate('document.getElementById("sensitive").disabled'),true);
  await delay(200); await screenshot('integrated-mrmem-home');
  await evaluate('document.querySelector(".primary a:nth-child(2)").click()');
  await wait('document.querySelector("h1")?.textContent === "记忆过程"');
  await evaluate('document.querySelector("#content .record a").click()');
  await wait('document.querySelector("h1")?.textContent === "记忆详情"');
  await evaluate('document.querySelector("[data-evidence]").click()');
  await wait('!!document.querySelector("#evidence blockquote")');
  assert.equal(requests.at(-1).params.fingerprint,'fiction-fingerprint');
  await delay(280); await screenshot('integrated-mrmem-evidence');
  await evaluate('document.getElementById("close-evidence").click()');
  await wait('!document.getElementById("evidence").open');
  assert.equal(await evaluate('document.getElementById("evidence-body").innerHTML'),'');
  await evaluate('document.getElementById("search").value="虚构"; document.getElementById("search").dispatchEvent(new Event("input"))');
  await wait('!!document.querySelector("#search-results a")');
  assert.ok(requests.some(r=>r.route==='search'));
  await evaluate('document.querySelector("#search-results a").click()');
  await wait('document.querySelector("h1")?.textContent === "记忆详情"');
  await evaluate('document.getElementById("theme").click()');
  await wait('document.documentElement.dataset.theme === "dark" && document.querySelector("h1")?.textContent === "记忆详情"');
  await delay(200); await screenshot('integrated-mrmem-dark');
  await evaluate('document.querySelector(".primary a:nth-child(3)").click()');
  await wait('document.getElementById("content").textContent.includes("当前 MR-Mem 尚无实体接口")');
  assert.equal(await evaluate('document.querySelectorAll("#graph canvas").length'),0);
  await evaluate('document.querySelector(".primary a:nth-child(1)").click()');
  await wait('!!document.querySelector(".nums")');
  await call('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
  await delay(200);
  assert.equal(await evaluate('document.documentElement.scrollWidth <= innerWidth'),true);
  await screenshot('integrated-mrmem-mobile');
  assert.deepEqual(errors,[]);
});
