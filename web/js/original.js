(async()=>{
'use strict';

let runtimeToken='',runtimeVersion=0,nativeEvidenceVersion=0;
async function request(path, body) {
  const response=await fetch(path,body===undefined?{cache:'no-store'}:{method:'POST',cache:'no-store',headers:{'Content-Type':'application/json','X-Atlas-Token':runtimeToken},body:JSON.stringify(body)});
  if(!response.ok)throw Error(({403:'当前操作未启用或权限校验失败',404:'当前数据或能力尚未配置',409:'记录冲突或证据已失效',503:'后端暂不可用'}[response.status]||'读取失败')+' ('+response.status+')');
  return response.json();
}


const DATA=await request('/api/archive/data');
const Q=DATA.quotes.map(r=>r.e?Object.assign(r,{q:b64u(r.q),e:0}):r), META=DATA.meta;
const DIMS=[...new Set(Q.map(r=>r.dim))].filter(Boolean).sort((a,b)=>Q.filter(r=>r.dim==b).length-Q.filter(r=>r.dim==a).length);
const PAL=['#b5532a','#3f6e8c','#7a8a3a','#a2456e','#c38b2a','#4f7d6b','#6a5a9c','#8c5a3a','#2f8a9a','#9a8a6a','#5b5b5b','#c0605f'];
const COL={};DIMS.forEach((d,i)=>COL[d]=PAL[i%PAL.length]);
const CHATS=[...new Set(Q.filter(r=>r.chat).map(r=>r.chat))];
const S={rs:'info',hi:true,lens:'overview',dims:new Set(),chat:'',year:'',q:'',sens:false,gmode:'dim',concept:'',topic:'AI模型'};
const LENSES=[['overview','回顾'],['graph','图谱'],['reader','原文册'],['state','状态→决策'],['consist','一致性'],['topic','专题'],['portrait','画像']];
const esc=s=>s.replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
function F(){const q=S.q.trim();return Q.filter(r=>(S.sens||!r.s)&&(!S.dims.size||S.dims.has(r.dim))&&(!S.chat||r.chat==S.chat)&&(!S.year||r.date.startsWith(S.year))&&(!q||r.q.includes(q)||r.chat.includes(q)))}
function qt(r){return `<div class="qt" data-id="${r.id}">「${esc(r.q)}」<span class="m">${esc(r.chat)} · ${r.date} · ${esc(r.dim)}</span></div>`}
function nav(){document.getElementById('nav').innerHTML=LENSES.map(([k,n])=>`<button class="${S.lens==k?'on':''}" data-l="${k}">${n}</button>`).join('')}
function filters(){const yrs=[...new Set(Q.filter(r=>r.date).map(r=>r.date.slice(0,4)))].sort();
 document.getElementById('filters').innerHTML=DIMS.map(d=>`<span class="chip ${S.dims.has(d)?'on':''}" data-d="${esc(d)}"><i style="background:${COL[d]}"></i>${esc(d)}</span>`).join('')+
 `<select id="fchat"><option value="">全部会话</option>${CHATS.map(c=>`<option ${S.chat==c?'selected':''}>${esc(c)}</option>`).join('')}</select>`+
 `<select id="fyear"><option value="">全部年份</option>${yrs.map(y=>`<option ${S.year==y?'selected':''}>${y}</option>`).join('')}</select>`+
 `<span class="count" id="cnt"></span>`;
 document.getElementById('fchat').onchange=e=>{S.chat=e.target.value;render()};document.getElementById('fyear').onchange=e=>{S.year=e.target.value;render()};}
function render(){if(typeof runtimeVersion!=='undefined')runtimeVersion++;nativeEvidenceVersion++;closeCard();nav();filters();const f=F();const hid=Q.filter(r=>r.s).length;
 document.getElementById('cnt').textContent=`${f.length} / ${Q.length} 条原话`+(S.sens?'':` · 已隐藏 ${hid} 条敏感`);
 document.getElementById('privL').classList.toggle('on',S.sens);
 if(runtimeViews[S.lens])runtimeViews[S.lens](f);else if(V4L[S.lens])V4L[S.lens](f);else ({overview:review,graph,reader,state,consist,topic,portrait})[S.lens](f);bindQ();globalThis.AtlasMotion?.enter(document.getElementById('main')); }
function bindQ(){document.querySelectorAll('[data-id]').forEach(e=>e.onclick=()=>openCard(+e.dataset.id))}
const pick=(arr,n)=>{const s=[...arr];const out=[];const step=Math.max(1,Math.floor(s.length/n));for(let i=0;i<s.length&&out.length<n;i+=step)out.push(s[i]);return out};
const longest=(arr,n)=>[...arr].sort((a,b)=>b.q.length-a.q.length).slice(0,n);
const mid=(arr,n)=>{const a=[...arr].filter(r=>r.q.length>=18&&r.q.length<=90).sort((a,b)=>b.q.length-a.q.length);return (a.length?a:[...arr]).slice(0,n)};
/* ---------- portrait (画像) ---------- */
function b64u(x){const b=atob(x);const u=new Uint8Array(b.length);for(let i=0;i<b.length;i++)u[i]=b.charCodeAt(i);return new TextDecoder().decode(u)}
const POR=DATA.por||{secs:[],skipped:[],stat:{}};
function porSens(){if(!DATA.porS)return null;const b=atob(DATA.porS);const u=new Uint8Array(b.length);for(let i=0;i<b.length;i++)u[i]=b.charCodeAt(i);return JSON.parse(new TextDecoder().decode(u))}
function porSec(sec){return `<section class="psec"><h${sec.lv==2?3:4}>${esc(sec.t)}</h${sec.lv==2?3:4}>${sec.note?`<p class="src">${esc(sec.note)}</p>`:''}${sec.items.map(it=>`<div class="pit ${it.inf?'inf':''}">${it.inf?'<span class="tag">推断</span> ':''}<span>${it.h}</span>${it.ev.length?`<details><summary>证据原话 ${it.ev.length} 条（已逐字核实）</summary>${it.ev.map((e,i)=>`<div class="qt">〔原话${i+1}〕「${esc(e.q)}」<span class="m">${esc(e.d||'')} · ${esc(e.c||'')}</span></div>`).join('')}</details>`:''}${it.miss?`<div class="src">${it.miss} 处原话未在 kg_full / digest 中逐字找到，只保留断言</div>`:''}</div>`).join('')}</section>`}
function portrait(){const st=POR.stat;let h=`<div class="por"><h2>画像</h2><p class="src">来源：fullpass\\历史画像文件。每条原话都在 历史归档数据 或 digest 里逐字核对过；核对不到的只留断言。标「推断」的是笔记里的推测，不是你说过的话。本页：${st.items} 条断言，原话 ${st.verified}/${st.quotes} 条核实通过。</p>`+POR.secs.filter(x=>x.items.length).map(porSec).join('')+(POR.skipped.length?`<p class="src">未展示：${POR.skipped.map(esc).join('；')}</p>`:'');
 if(S.sens){const P=porSens();if(P)h+=`<section class="psens" data-sensitive="1"><div class="warn">敏感区块：健康 / 失去相关内容。<b>可整块删除</b>（构建时加 --no-sensitive-portrait 即可得到不含本区块的版本）。原话 ${P.stat.verified}/${P.stat.quotes} 条核实通过。</div>${P.secs.filter(x=>x.items.length).map(porSec).join('')}</section>`;}
 else if(DATA.porS)h+=`<p class="src">另有一个敏感区块（健康 / 失去）默认不显示，打开「显示敏感内容」后才会生成。</p>`;
 document.getElementById('main').innerHTML=h+'</div>'}
/* ---------- review (回顾) ---------- */
const INS=DATA.ins||{cards:[],dimdesc:{},hubsum:{},lede:[]};
const srcTag=s=>`<span class="src">〔${esc(s)}〕</span>`;
function review(f){const months=[...new Set(f.map(r=>r.date.slice(0,7)))].sort();const chats=new Set(f.map(r=>r.chat)).size;
 const mc={};f.forEach(r=>{const k=r.date.slice(0,7);mc[k]=(mc[k]||0)+1});const topM=Object.entries(mc).sort((a,b)=>b[1]-a[1])[0]||['—',0];
 const hc={};f.forEach(r=>{if(r.tm){const h=+r.tm.split(':')[0];hc[h]=(hc[h]||0)+1}});const topH=Object.entries(hc).sort((a,b)=>b[1]-a[1])[0];
 const wk=['周日','周一','周二','周三','周四','周五','周六'];const wc={};f.forEach(r=>{const d=new Date(r.date+'T00:00:00').getDay();wc[d]=(wc[d]||0)+1});const topW=Object.entries(wc).sort((a,b)=>b[1]-a[1])[0];
 const dc={};f.forEach(r=>dc[r.dim]=(dc[r.dim]||0)+1);const dl=DIMS.filter(d=>dc[d]).map(d=>[d,dc[d]]).sort((a,b)=>b[1]-a[1]);
 const W=1240,H=110,mx=Math.max(1,...Object.values(mc));const bw=(W-40)/Math.max(1,months.length);
 const bars=months.map((m,i)=>`<rect x="${20+i*bw}" y="${H-22-mc[m]*(H-34)/mx}" width="${Math.max(1.5,bw*.7)}" height="${mc[m]*(H-34)/mx}" fill="${m==topM[0]?'#9b3d1c':'#c9b79c'}"><title>${m} · ${mc[m]} 句</title></rect>${(m.endsWith('-01')||i==0)?`<text x="${20+i*bw}" y="${H-6}" font-size="11" fill="#a39886">${m}</text>`:''}`).join('');
 const cards=INS.cards.map((c,i)=>{const ev=c.ids.map(id=>Q[id]).filter(r=>r&&(S.sens||!r.s));
  return `<div class="icard"><div class="kick">洞察 ${String(i+1).padStart(2,'0')}</div><h3>${esc(c.title)}</h3><p>${esc(c.body)}</p>${c.infer?`<p class="inf"><b>推断</b>${esc(c.infer)}</p>`:''}<div class="isrc">来源：${esc(c.src)}</div>
  <details><summary>证据 · ${ev.length} 条原话</summary>${ev.map(qt).join('')}</details><button class="go" data-hub="${esc(c.hub)}">在图谱中查看「${esc(gHubName(c.hub))}」→</button></div>`}).join('');
 document.getElementById('main').innerHTML=`<div class="kick">回顾 · 基于 fullpass 的综合结论与已核实原话</div>
 <h1 class="rh">${esc(INS.headline)}</h1><div class="isrc" style="margin:6px 0 0"><span class="tag">推断</span> 出自 ${esc(INS.headline_src)}</div>
 <p class="lede rl">${INS.lede.map(([t,s])=>esc(t)+srcTag(s)).join(' ')}</p>
 <div class="nums"><div><b>${f.length}</b><span>条已核实原话</span></div><div><b>${chats}</b><span>个会话</span></div><div><b>${months[0]||'—'} – ${months[months.length-1]||''}</b><span>时间跨度（${months.length} 个月）</span></div><div><b>${topM[0]}</b><span>最活跃的月份（${topM[1]} 句）</span></div><div><b>${topH?topH[0]+'–'+(+topH[0]+1)+' 时':'—'}</b><span>最活跃时段（北京时间）</span></div><div><b>${topW?wk[topW[0]]:'—'}</b><span>最活跃的一天</span></div></div>
 <div class="panel"><div style="font-size:12px;color:var(--ink3)">每月原话数 · 按本页收录的原话统计，时段取自原始消息时间</div><svg viewBox="0 0 ${W} ${H}" width="100%" style="display:block;margin-top:6px">${bars}</svg></div>
 <section class="panel" style="margin-top:20px"><h2>主题河流</h2><p class="lede">每月各主题的原话数量；图例可筛选主题。</p><div id="river"></div><div id="river-legend">${DIMS.map(d=>`<button class="chip" data-river-d="${esc(d)}"><i style="background:${COL[d]}"></i>${esc(d)}</button>`).join('')}</div></section>
 <h2 style="margin:30px 0 10px">你在聊什么</h2><div class="band">${dl.map(([d,n])=>`<i style="width:${100*n/f.length}%;background:${COL[d]}" title="${esc(d)} ${n}"></i>`).join('')}</div>
 <div class="drows">${dl.map(([d,n])=>{const x=INS.dimdesc[d];return `<div class="drow" data-dd="${esc(d)}"><span class="dn"><i style="background:${COL[d]}"></i>${esc(d.replace(/\(.*?\)/,''))}</span><span class="dp">${Math.round(100*n/f.length)}%<small>${n} 句</small></span><span class="dd">${x?esc(x[0])+srcTag(x[1]):'<span style="color:var(--ink3)">未归入其它主题的零散内容（无综合结论）</span>'}</span></div>`}).join('')}</div>
 <h2 style="margin:34px 0 4px">洞察</h2><p class="lede" style="margin-top:0">每张卡是一句结论加两三句解释，全部来自 fullpass 里已有的综合文件；标「推断」的是推测，不是你说过的话。原话只作证据，点开可看。</p>
 <div class="igrid">${cards}</div>
 <div class="panel cov"><b>覆盖面</b><p>${esc(META.coverage||'历史编译产物；分类与综合结论保留原始来源，不作为新的编译结果。')}</p>\n <div style="margin-top:8px"><button class="go" data-l="reader">去原文册（证据库）→</button> <button class="go" data-l="graph" style="margin-left:14px">去图谱 →</button></div></div>`;
 river(f,months);document.querySelectorAll('[data-river-d]').forEach(button=>button.onclick=()=>{const d=button.dataset.riverD;const single=S.dims.size===1&&S.dims.has(d);S.dims.clear();if(!single)S.dims.add(d);render()});
 document.querySelectorAll('.go[data-l]').forEach(b=>b.onclick=()=>{S.lens=b.dataset.l;render();scrollTo(0,0)});
 document.querySelectorAll('[data-hub]').forEach(b=>b.onclick=()=>gotoHub(b.dataset.hub));
 document.querySelectorAll('[data-dd]').forEach(b=>b.onclick=()=>gotoHub('d:'+b.dataset.dd));}
function gotoHub(id){S.lens='graph';GS.sel={t:'h',id};GS.exp=new Set([id]);GS.all=false;GS.T=null;render();scrollTo(0,0)}

function river(f,months){const W=1240,H=300,P=30;const box=document.getElementById('river');if(!months.length){box.innerHTML='<p class="empty">没有数据</p>';return}
 const m={};months.forEach(x=>m[x]={});f.forEach(r=>{const k=r.date.slice(0,7);m[k][r.dim]=(m[k][r.dim]||0)+1});
 const tot=months.map(x=>DIMS.reduce((s,d)=>s+(m[x][d]||0),0));const mx=Math.max(...tot,1);
 const X=i=>P+i*(W-2*P)/Math.max(1,months.length-1),Y=v=>H-P-v*(H-2*P)/mx;
 let base=months.map(()=>0),paths='';
 const sm=pts=>{let d=`M${pts[0][0]},${pts[0][1]}`;for(let i=1;i<pts.length;i++){const [x0,y0]=pts[i-1],[x1,y1]=pts[i],cx=(x0+x1)/2;d+=` C${cx},${y0} ${cx},${y1} ${x1},${y1}`}return d};
 DIMS.forEach(d=>{const top=months.map((x,i)=>base[i]+(m[x][d]||0));const up=months.map((x,i)=>[X(i),Y(top[i])]);const lo=months.map((x,i)=>[X(i),Y(base[i])]).reverse();
  if(top.some((v,i)=>v>base[i]))paths+=`<path d="${sm(up)} L${lo[0][0]},${lo[0][1]} ${sm(lo).slice(1)} Z" fill="${COL[d]}" fill-opacity=".82" stroke="#fbf8f2" stroke-width=".6"><title>${esc(d)}</title></path>`;base=top});
 const ticks=months.map((x,i)=>x.endsWith('-01')||i==0||i==months.length-1?`<text x="${X(i)}" y="${H-8}" font-size="11" fill="#a39886" text-anchor="middle">${x}</text><line x1="${X(i)}" x2="${X(i)}" y1="${P}" y2="${H-P}" stroke="#e3dacb" stroke-dasharray="2 3"/>`:'').join('');
 box.innerHTML=`<svg viewBox="0 0 ${W} ${H}" width="100%" style="display:block;margin-top:10px">${ticks}${paths}<text x="${P}" y="${P-10}" font-size="11" fill="#a39886">峰值 ${mx} 条/月</text></svg>`;}
/* ---------- graph (hub + force layout, connected) ---------- */
let GP=[];const GS={exp:new Set(),all:false,e:{a:1,b:1,c:1,w:0},sel:null,T:null,key:'',L:null,hover:null};
const STATEH={st:'状态(睡眠/情绪)',de:'决策(仓位/止损)',t:'转折/自我矛盾'};
function gHubsOf(r){return r.hs}
const TGAP=6*60;const dtm=r=>new Date(r.date+'T'+(r.tm||'12:00')+':00').getTime()/6e4;
function gWhy(r,h){const w=(r.kw||{})[h]||[];return w.join('、')}
function gHubName(id){const t=id[0],v=id.slice(2);return t=='s'?STATEH[v]:v.replace(/\(.*?\)/,'')}
function gHubCol(id){const t=id[0];return t=='c'?'#e0b25c':t=='d'?COL[id.slice(2)]:'#7fb3d5'}
function gTypeOn(id){return id[0]=='c'?GS.e.a:GS.e.c}
function gLayout(f){const key=f.length+'|'+f.slice(0,3).map(r=>r.id)+'|'+f.slice(-3).map(r=>r.id);if(GS.L&&GS.L.key==key)return GS.L;
 const hc={},pair={},taut={};f.forEach(r=>{const h=r.hs;r.hw.forEach(x=>hc[x]=hc[x]||0);h.forEach(x=>hc[x]=(hc[x]||0)+1);for(let i=0;i<h.length;i++)for(let j=i+1;j<h.length;j++){const k=h[i]<h[j]?h[i]+'|'+h[j]:h[j]+'|'+h[i];pair[k]=(pair[k]||0)+1;const A=(r.kw||{})[h[i]]||[],B=(r.kw||{})[h[j]]||[];if(A.some(w=>B.some(v=>v.includes(w)||w.includes(v))))taut[k]=(taut[k]||0)+1}});
 const hubs=Object.keys(hc).sort();const hi={};hubs.forEach((h,i)=>hi[h]=i);const n=hubs.length;
 const P=hubs.map((h,i)=>{const a=i/n*Math.PI*2;const R=h[0]=='d'?320:h[0]=='s'?140:230;return[Math.cos(a)*R,Math.sin(a)*R]});
 const NN=f.length;const links=Object.entries(pair).map(([k,w])=>{const [a,b]=k.split('|');const e=hc[a]*hc[b]/NN;return{a:hi[a],b:hi[b],w,ka:a,kb:b,e,lift:w/e,j:w/(hc[a]+hc[b]-w),ta:(taut[k]||0)/w}}).filter(l=>l.w>=8&&l.lift>=1.5&&l.ta<.5);const mw=Math.max(1,...links.map(l=>Math.log2(l.lift)));
 for(let it=0;it<600;it++){const F=P.map(()=>[0,0]);const cool=1-it/700;
  for(let i=0;i<n;i++)for(let j=i+1;j<n;j++){let dx=P[j][0]-P[i][0],dy=P[j][1]-P[i][1];let d2=dx*dx+dy*dy+1;const d=Math.sqrt(d2);const rep=26000/d2;F[i][0]-=dx/d*rep;F[i][1]-=dy/d*rep;F[j][0]+=dx/d*rep;F[j][1]+=dy/d*rep}
  links.forEach(l=>{const dx=P[l.b][0]-P[l.a][0],dy=P[l.b][1]-P[l.a][1];const d=Math.hypot(dx,dy)||1;const s=.02*Math.sqrt(Math.log2(l.lift)/mw)*(d-120);F[l.a][0]+=dx/d*s;F[l.a][1]+=dy/d*s;F[l.b][0]-=dx/d*s;F[l.b][1]-=dy/d*s});
  P.forEach((p,i)=>{F[i][0]-=p[0]*.012;F[i][1]-=p[1]*.012;const m=Math.hypot(F[i][0],F[i][1]);const c=Math.min(m,20*cool)/(m||1);p[0]+=F[i][0]*c;p[1]+=F[i][1]*c})}
 const H=hubs.map((h,i)=>({id:h,x:P[i][0],y:P[i][1],n:hc[h],r:5+Math.sqrt(hc[h])*.9}));
 // quote nodes: centroid of hubs + spiral per signature, then collision relax via grid
 const sigc={};const N=f.map(r=>{const hs=r.hs.length?r.hs:r.hw.filter(h=>hi[h]!=null);let x=0,y=0,wt=0;hs.filter(h=>hi[h]!=null).map(h=>hi[h]).forEach(i=>{const w=hubs[i][0]=='c'?2:1;x+=P[i][0]*w;y+=P[i][1]*w;wt+=w});x/=wt;y/=wt;const sg=hs.join('|');const j=sigc[sg]=(sigc[sg]||0)+1;const rad=7*Math.sqrt(j);const a=j*2.39996;return{r,hs:r.hs,hw:r.hw.filter(h=>hi[h]!=null),x:x+Math.cos(a)*rad,y:y+Math.sin(a)*rad,ox:x,oy:y,s:1.6+Math.min(2.4,r.q.length/40)}});
 for(let it=0;it<25;it++){const grid=new Map();const cs=9;N.forEach((p,i)=>{const k=Math.floor(p.x/cs)+','+Math.floor(p.y/cs);(grid.get(k)||grid.set(k,[]).get(k)).push(i)});
  N.forEach((p,i)=>{const gx=Math.floor(p.x/cs),gy=Math.floor(p.y/cs);for(let a=-1;a<=1;a++)for(let b=-1;b<=1;b++){const L=grid.get((gx+a)+','+(gy+b));if(!L)continue;for(const j of L){if(j<=i)continue;const q=N[j];const dx=q.x-p.x,dy=q.y-p.y,d=Math.hypot(dx,dy)||.01;if(d<8){const m=(8-d)/2;p.x-=dx/d*m;p.y-=dy/d*m;q.x+=dx/d*m;q.y+=dy/d*m}}}});
  N.forEach(p=>{p.x+=(p.ox-p.x)*.02;p.y+=(p.oy-p.y)*.02})}
 // time chain within chat
 const byChat={};N.forEach((p,i)=>(byChat[p.r.chat]=byChat[p.r.chat]||[]).push(i));const TE=[];Object.values(byChat).forEach(a=>{a.sort((x,y)=>(dtm(N[x].r)-dtm(N[y].r))||N[x].r.id-N[y].r.id);for(let i=1;i<a.length;i++){const p=N[a[i-1]],q=N[a[i]];const g=dtm(q.r)-dtm(p.r);const sh=p.hs.filter(h=>q.hs.includes(h));if(g>=0&&g<=TGAP&&sh.length)TE.push([a[i-1],a[i],g,sh])}});
 const hubQ={};N.forEach((p,i)=>p.hs.forEach(h=>(hubQ[h]=hubQ[h]||[]).push(i)));
 const hubQw={};N.forEach((p,i)=>p.hw.forEach(h=>(hubQw[h]=hubQw[h]||[]).push(i)));
 GS.L={key,hubs,H,hi,links,mw,N,TE,hubQ,hubQw,NN};GS.T=null;return GS.L}
function graph(fAll){const f=Q.filter(r=>(S.sens||!r.s)&&(!S.dims.size||S.dims.has(r.dim))&&(!S.chat||r.chat==S.chat)&&(!S.year||r.date.startsWith(S.year)));
 document.getElementById('main').innerHTML=`<div class="kick">Graph lens</div><h2>认知图谱</h2><p class="lede" style="margin-bottom:14px">大节点是<b style="color:#b8892f">概念</b>、<b>主题</b>和<b style="color:#3f7aa0">状态</b>，连线粗细 = 两者在多少句原话里同时出现。<b>点节点</b>看你在这个话题上讲了什么、怎么变化、常和什么一起出现；<b>点连线</b>看它们为什么连（实际共现 vs 随机预期、依据词）；<b>点小点</b>看这句话的前后文。滚轮或双指缩放，拖动平移。</p>
 <div class="night"><div class="gbar"><span>连线：</span><button data-ge="a" class="${GS.e.a?'on':''}">━ 同概念</button><button data-ge="b" class="${GS.e.b?'on':''}">┅ 同会话时间链</button><button data-ge="c" class="${GS.e.c?'on':''}">┈ 主题/状态</button><button data-ge="w" class="${GS.e.w?'on':''}" title="只命中一个弱关键词、或主题没有佐证词的归属">┄ 弱关联</button>
 <span style="margin-left:10px"></span><button id="gall" class="${GS.all?'on':''}">${GS.all?'收起全部':'展开全部'}</button><button id="gclr">清空展开</button><button id="gfit">重置视图</button><span id="ginfo" style="margin-left:auto"></span></div><div class="gwrap"><canvas id="gc"></canvas><div id="gpanel"></div></div></div>`;
 document.querySelectorAll('[data-ge]').forEach(b=>b.onclick=()=>{GS.e[b.dataset.ge]=GS.e[b.dataset.ge]?0:1;render()});
 document.getElementById('gall').onclick=()=>{GS.all=!GS.all;render()};document.getElementById('gclr').onclick=()=>{GS.exp.clear();GS.all=false;GS.sel=null;render()};document.getElementById('gfit').onclick=()=>{GS.T=null;drawGraph()};
 GS.f=f;gLayout(f);if(GS.sel&&GS.sel.t=='q'&&!GS.L.N.some(p=>p.r.id==GS.sel.id))GS.sel=null;if(GS.sel&&GS.sel.t=='h'&&GS.L.hi[GS.sel.id]==null)GS.sel=null;
 if(!GS.sel&&!GS.seen){GS.seen=1;GS.guide=true;const big=[...GS.L.H].sort((a,b)=>b.n-a.n)[0];if(big)GS.sel={t:'h',id:big.id}}bindGraph();drawGraph();gPanel();}
function gClickHub(id){GS.guide=false;GS.sel={t:'h',id};GS.exp=new Set([id]);drawGraph();gPanel();gScrollPanel()}
function gScrollPanel(){if(innerWidth<900){const p=document.getElementById('gpanel');if(p)p.scrollIntoView({behavior:'smooth',block:'start'})}}
function gVisible(){const L=GS.L;const q=S.q.trim();const hit=new Set();if(q)L.N.forEach((p,i)=>{if(p.r.q.includes(q)||p.r.chat.includes(q))hit.add(i)});
 const vis=new Set(hit);if(GS.sel&&GS.sel.t=='q'){const i=L.N.findIndex(p=>p.r.id==GS.sel.id);if(i>=0)vis.add(i)}if(GS.sel&&GS.sel.t=='e'){const A=new Set(L.hubQ[GS.sel.ka]||[]);(L.hubQ[GS.sel.kb]||[]).forEach(i=>{if(A.has(i))vis.add(i)})}if(GS.all)L.N.forEach((p,i)=>vis.add(i));else GS.exp.forEach(h=>(L.hubQ[h]||[]).forEach(i=>vis.add(i)));return{vis,hit}}
function gXY(x,y){const T=GS.T;return GS.rot?[y*T.k+T.x,x*T.k+T.y]:[x*T.k+T.x,y*T.k+T.y]}
function drawGraph(){const cv=document.getElementById('gc');if(!cv||!GS.L)return;const L=GS.L;const dpr=devicePixelRatio||1;const W=cv.clientWidth,H=cv.clientHeight;GS.rot=H>W*1.05;cv.width=W*dpr;cv.height=H*dpr;const g=cv.getContext('2d');g.scale(dpr,dpr);
 if(!GS.T){let x0=1e9,x1=-1e9,y0=1e9,y1=-1e9;L.H.forEach(h=>{const a=GS.rot?h.y:h.x,b=GS.rot?h.x:h.y;x0=Math.min(x0,a);x1=Math.max(x1,a);y0=Math.min(y0,b);y1=Math.max(y1,b)});const pad=W<600?70:160;const k=Math.min(W/(x1-x0+pad),H/(y1-y0+pad*.75));GS.T={k,x:W/2-(x0+x1)/2*k,y:H/2-(y0+y1)/2*k}}
 const T=GS.T;
 const {vis,hit}=gVisible();L.N.forEach(p=>{p.dx=p.x;p.dy=p.y});
 if(!GS.all){const done=new Set();GS.exp.forEach(h=>{const hb=L.H[L.hi[h]];if(!hb)return;const a=(L.hubQ[h]||[]).filter(i=>!done.has(i)).sort((x,y)=>L.N[x].r.date<L.N[y].r.date?-1:1);a.forEach((i,j)=>{done.add(i);const ang=j*2.39996,rad=hb.r+10+8.5*Math.sqrt(j+1);L.N[i].dx=hb.x+Math.cos(ang)*rad;L.N[i].dy=hb.y+Math.sin(ang)*rad})})}
 GP=[...vis].map(i=>L.N[i]);
 // neighbourhood of selection
 let nbH=null,nbQ=null;if(GS.sel){nbH=new Set();nbQ=new Set();if(GS.sel.t=='h'){const id=GS.sel.id;nbH.add(id);L.links.forEach(l=>{if(gTypeOn(l.ka)&&gTypeOn(l.kb)){if(l.ka==id)nbH.add(l.kb);if(l.kb==id)nbH.add(l.ka)}});(L.hubQ[id]||[]).forEach(i=>{if(vis.has(i))nbQ.add(i)})}
  else{if(GS.sel.t=='e'){nbH.add(GS.sel.ka);nbH.add(GS.sel.kb);vis.forEach(i=>{const hs=L.N[i].hs;if(hs.includes(GS.sel.ka)&&hs.includes(GS.sel.kb))nbQ.add(i)})}else{const i=L.N.findIndex(p=>p.r.id==GS.sel.id);if(i>=0){nbQ.add(i);L.N[i].hs.forEach(h=>{if(gTypeOn(h))nbH.add(h)});if(GS.e.b)L.TE.forEach(([a,b])=>{if(a==i&&vis.has(b))nbQ.add(b);if(b==i&&vis.has(a))nbQ.add(a)})}}}}
 const aH=id=>!nbH||nbH.has(id)?1:.12,aQ=i=>!nbQ||nbQ.has(i)?1:.08;
 g.fillStyle='#16130f';g.fillRect(0,0,W,H);
 // skeleton hub-hub edges
 L.links.forEach(l=>{if(!gTypeOn(l.ka)||!gTypeOn(l.kb))return;const A=L.H[L.hi[l.ka]],B=L.H[L.hi[l.kb]];const isE=GS.sel&&GS.sel.t=='e'&&((l.ka==GS.sel.ka&&l.kb==GS.sel.kb)||(l.ka==GS.sel.kb&&l.kb==GS.sel.ka));const on=isE||(!nbH||(GS.sel.t!='e'&&nbH.has(l.ka)&&nbH.has(l.kb)&&(GS.sel.t!='h'||l.ka==GS.sel.id||l.kb==GS.sel.id)));if(isE){g.globalAlpha=1;g.strokeStyle='#fff3c4';g.lineWidth=3+3.2*Math.sqrt(Math.log2(l.lift)/L.mw);g.setLineDash([]);g.beginPath();g.moveTo(...gXY(A.x,A.y));g.lineTo(...gXY(B.x,B.y));g.stroke();return}g.globalAlpha=on?(nbH?.75:.38):.05;g.strokeStyle=(l.ka[0]=='c'&&l.kb[0]=='c')?'#e0b25c':'#b9a88c';g.lineWidth=.6+3.2*Math.sqrt(Math.log2(l.lift)/L.mw);g.setLineDash([]);g.beginPath();g.moveTo(...gXY(A.x,A.y));g.lineTo(...gXY(B.x,B.y));g.stroke()});
 // quote -> hub edges
 const many=vis.size>600;
 vis.forEach(i=>{const p=L.N[i];p.hs.forEach(h=>{if(!gTypeOn(h))return;if(!GS.all&&!GS.exp.has(h)&&!hit.has(i)&&!(GS.sel&&GS.sel.t=='q'&&L.N[i].r.id==GS.sel.id)&&!(GS.sel&&GS.sel.t=='e'&&(h==GS.sel.ka||h==GS.sel.kb)))return;const hb=L.H[L.hi[h]];const a=Math.min(aQ(i),aH(h));g.globalAlpha=(many?.10:.32)*(nbQ&&nbQ.has(i)?3:a);g.strokeStyle=h[0]=='c'?'#e0b25c':gHubCol(h);g.lineWidth=.6;g.setLineDash(h[0]=='c'?[]:[1.5,2.5]);g.beginPath();g.moveTo(...gXY(p.dx,p.dy));g.lineTo(...gXY(hb.x,hb.y));g.stroke()})});
 if(GS.e.w){g.setLineDash([2,4]);g.lineWidth=.6;vis.forEach(i=>{const p=L.N[i];p.hw.forEach(h=>{if(!gTypeOn(h))return;const hb=L.H[L.hi[h]];if(!hb)return;g.globalAlpha=.2*aQ(i);g.strokeStyle='#9a9080';g.beginPath();g.moveTo(...gXY(p.dx,p.dy));g.lineTo(...gXY(hb.x,hb.y));g.stroke()})});g.setLineDash([])}
 // time chain
 if(GS.e.b){g.setLineDash([4,3]);g.strokeStyle='#8fc1e3';g.lineWidth=.9;L.TE.forEach(([a,b])=>{if(!vis.has(a)||!vis.has(b))return;g.globalAlpha=(many?.22:.6)*Math.min(aQ(a),aQ(b));g.beginPath();g.moveTo(...gXY(L.N[a].dx,L.N[a].dy));g.lineTo(...gXY(L.N[b].dx,L.N[b].dy));g.stroke()})}
 g.setLineDash([]);
 // quote dots
 vis.forEach(i=>{const p=L.N[i];g.globalAlpha=.95*aQ(i);g.fillStyle=COL[p.r.dim];const rr=Math.max(1.4,p.s*Math.sqrt(T.k));g.beginPath();g.arc(...gXY(p.dx,p.dy),rr,0,7);g.fill();if(hit.has(i)){g.globalAlpha=1;g.strokeStyle='#fff3c4';g.lineWidth=1.6;g.beginPath();g.arc(...gXY(p.dx,p.dy),rr+3,0,7);g.stroke()}if(GS.sel&&GS.sel.t=='q'&&GS.sel.id==p.r.id){g.globalAlpha=1;g.strokeStyle='#fff';g.lineWidth=2;g.beginPath();g.arc(...gXY(p.dx,p.dy),rr+5,0,7);g.stroke()}});
 // hubs
 const ff=getComputedStyle(document.body).fontFamily;
 const LR=[];const CR=W<600?L.H.filter(h=>gTypeOn(h.id)).map(h=>{const [x,y]=gXY(h.x,h.y),r=h.r*Math.max(.7,Math.sqrt(T.k));return[x-r,y-r,2*r,2*r,h.id]}):[];[...L.H].sort((p,q)=>(GS.exp.has(q.id)-GS.exp.has(p.id))||q.n-p.n).forEach(h=>{if(!gTypeOn(h.id))return;const a=aH(h.id);const [x,y]=gXY(h.x,h.y),r=h.r*Math.max(.7,Math.sqrt(T.k));g.globalAlpha=a;g.fillStyle=gHubCol(h.id);g.beginPath();g.arc(x,y,r,0,7);g.fill();g.lineWidth=GS.exp.has(h.id)?2.5:1.2;g.strokeStyle=GS.exp.has(h.id)?'#fff':'#16130f';g.stroke();
  if(a<.5&&nbH)return;const lb=gHubName(h.id);g.font=(h.id[0]=='c'?'600 12.5px ':'600 13px ')+ff;g.textAlign='center';const w=g.measureText(lb).width+10;const box=[x-w/2,y-r-19,w,16];if(CR.some(b=>b[4]!=h.id&&b[0]<box[0]+box[2]&&box[0]<b[0]+b[2]&&b[1]<box[1]+box[3]&&box[1]<b[1]+b[3])&&!(GS.sel&&GS.sel.id==h.id))return;if(LR.some(b=>b[0]<box[0]+box[2]&&box[0]<b[0]+b[2]&&b[1]<box[1]+box[3]&&box[1]<b[1]+b[3]))return;LR.push(box);g.globalAlpha=a*.85;g.fillStyle='rgba(22,19,15,.8)';g.fillRect(x-w/2,y-r-19,w,16);g.globalAlpha=a;g.fillStyle=h.id[0]=='c'?'#f3d79a':h.id[0]=='s'?'#bfe0f5':'#efe6d6';g.fillText(lb,x,y-r-7)});
 g.globalAlpha=1;
 document.getElementById('ginfo').textContent=`${L.H.length} 个节点 · 显示 ${vis.size}/${L.N.length} 句`+(hit.size?` · 搜索命中 ${hit.size}`:'')+(GS.sel?' · 点空白处取消选择':' · 点节点或连线看详情');}
function gPick(mx,my){const L=GS.L,T=GS.T;let best=null,bd=1e9;L.H.forEach(h=>{if(!gTypeOn(h.id))return;const r=h.r*Math.max(.7,Math.sqrt(T.k))+4;const [hx,hy]=gXY(h.x,h.y);const d=Math.hypot(hx-mx,hy-my);if(d<r&&d<bd){bd=d;best={t:'h',h}}});if(best)return best;
 GP.forEach(p=>{const [px,py]=gXY(p.dx,p.dy);const d=Math.hypot(px-mx,py-my);if(d<10&&d<bd){bd=d;best={t:'q',p}}});if(best)return best;
 L.links.forEach(l=>{if(!gTypeOn(l.ka)||!gTypeOn(l.kb))return;const A=L.H[L.hi[l.ka]],B=L.H[L.hi[l.kb]];const [ax,ay]=gXY(A.x,A.y),[bx,by]=gXY(B.x,B.y);const vx=bx-ax,vy=by-ay;const t=Math.max(0,Math.min(1,((mx-ax)*vx+(my-ay)*vy)/(vx*vx+vy*vy||1)));const d=Math.hypot(ax+t*vx-mx,ay+t*vy-my);if(d<7&&d<bd){bd=d;best={t:'e',l}}});return best}
function bindGraph(){const cv=document.getElementById('gc');const tip=document.getElementById('tip');const pts=new Map();let drag=null,moved=0,pinch=null;
 const loc=e=>{const b=cv.getBoundingClientRect();return[e.clientX-b.left,e.clientY-b.top]};
 cv.onwheel=e=>{e.preventDefault();const [mx,my]=loc(e);const T=GS.T;const f=Math.exp(-e.deltaY*.0015);const k=Math.max(.2,Math.min(12,T.k*f));T.x=mx-(mx-T.x)*k/T.k;T.y=my-(my-T.y)*k/T.k;T.k=k;drawGraph()};
 cv.onpointerdown=e=>{cv.setPointerCapture(e.pointerId);pts.set(e.pointerId,loc(e));moved=0;if(pts.size==1)drag=loc(e);if(pts.size==2){const [a,b]=[...pts.values()];pinch={d:Math.hypot(a[0]-b[0],a[1]-b[1]),k:GS.T.k}}};
 cv.onpointermove=e=>{const [mx,my]=loc(e);if(pts.has(e.pointerId)){pts.set(e.pointerId,[mx,my]);if(pts.size==2&&pinch){const [a,b]=[...pts.values()];const d=Math.hypot(a[0]-b[0],a[1]-b[1]);const T=GS.T;const cx=(a[0]+b[0])/2,cy=(a[1]+b[1])/2;const k=Math.max(.2,Math.min(12,pinch.k*d/pinch.d));T.x=cx-(cx-T.x)*k/T.k;T.y=cy-(cy-T.y)*k/T.k;T.k=k;moved=99;drawGraph();return}
   if(drag){const dx=mx-drag[0],dy=my-drag[1];moved+=Math.abs(dx)+Math.abs(dy);if(moved>4){GS.T.x+=dx;GS.T.y+=dy;drag=[mx,my];drawGraph()}}return}
  if(e.pointerType!='mouse')return;const hit=gPick(mx,my);
  if(hit){tip.style.display='block';tip.style.left=Math.min(innerWidth-360,e.clientX+14)+'px';tip.style.top=(e.clientY+14)+'px';tip.innerHTML=hit.t=='h'?`<b>${esc(gHubName(hit.h.id))}</b><small>${hit.h.n} 句 · 点击查看你在这里讲了什么</small>`:hit.t=='e'?`<b>${esc(gHubName(hit.l.ka))} — ${esc(gHubName(hit.l.kb))}</b><small>共同出现 ${hit.l.w} 句 · 点击查看关联</small>`:`「${esc(hit.p.r.q.length>80?hit.p.r.q.slice(0,80)+'…':hit.p.r.q)}」<small>${esc(hit.p.r.chat)} · ${hit.p.r.date} · ${esc(hit.p.r.dim)}</small>`;cv.style.cursor='pointer'}else{tip.style.display='none';cv.style.cursor='grab'}};
 const up=e=>{const wasTap=moved<=4&&pts.size==1;pts.delete(e.pointerId);if(pts.size<2)pinch=null;if(!pts.size)drag=null;if(!wasTap)return;const [mx,my]=loc(e);const hit=gPick(mx,my);
  GS.guide=false;if(!hit){GS.sel=null;drawGraph();gPanel();return}if(hit.t=='h')gClickHub(hit.h.id);else if(hit.t=='e'){GS.sel={t:'e',ka:hit.l.ka,kb:hit.l.kb};drawGraph();gPanel();gScrollPanel()}else{GS.sel={t:'q',id:hit.p.r.id};drawGraph();gPanel();gScrollPanel()}};
 cv.onpointerup=up;cv.onpointercancel=e=>{pts.delete(e.pointerId);drag=null;pinch=null};cv.onmouseleave=()=>tip.style.display='none';}
/* ---------- graph info panel ---------- */
const ivSort=a=>[...a].sort((x,y)=>(y.iv-x.iv)||(Math.abs(x.q.length-60)-Math.abs(y.q.length-60)));
function gSum(id){const s=INS.hubsum[id]||(id[0]=='d'?INS.dimdesc[id.slice(2)]:null);return s}
function gFacts(rs){const ms=rs.map(r=>r.date.slice(0,7)).sort();const cc={};rs.forEach(r=>cc[r.chat]=(cc[r.chat]||0)+1);const tc=Object.entries(cc).sort((a,b)=>b[1]-a[1]);
 const dc={};rs.forEach(r=>dc[r.dim]=(dc[r.dim]||0)+1);const td=Object.entries(dc).sort((a,b)=>b[1]-a[1]);
 return{from:ms[0]||'—',to:ms[ms.length-1]||'—',nch:tc.length,tc:tc.slice(0,3).map(x=>x[0]),td:td.slice(0,2).map(x=>x[0].replace(/\(.*?\)/,''))}}
function gSpark(rs){const L=GS.L;const all=[...new Set(L.N.map(p=>p.r.date.slice(0,7)))].sort();const c={};rs.forEach(r=>{const k=r.date.slice(0,7);c[k]=(c[k]||0)+1});const mx=Math.max(1,...Object.values(c));const W=340,H=56,bw=W/Math.max(1,all.length);
 return `<svg viewBox="0 0 ${W} ${H+14}" width="100%">${all.map((m,i)=>c[m]?`<rect x="${i*bw}" y="${H-c[m]*H/mx}" width="${Math.max(1.2,bw*.75)}" height="${c[m]*H/mx}" fill="#9b3d1c"><title>${m} · ${c[m]} 句</title></rect>`:'').join('')}<text x="0" y="${H+12}" font-size="10" fill="#a39886">${all[0]||''}</text><text x="${W}" y="${H+12}" font-size="10" fill="#a39886" text-anchor="end">${all[all.length-1]||''}</text></svg>`}
const pq=r=>`<div class="qt" data-id="${r.id}">「${esc(r.q)}」<span class="m">${r.date} · ${esc(r.chat)}</span></div>`;
function gPanel(){const el=document.getElementById('gpanel');if(!el||!GS.L)return;const L=GS.L,sel=GS.sel;let h='';
 if(!sel){el.innerHTML=`<div class="kick">思维地图</div><p>这里是你的思维地图：点任何一个大节点，看你在这个话题上讲了什么、怎么变化；点两个节点之间的连线，看它们为什么一起出现；点小点看那句原话的前后文。</p>`;return}
 if(sel.t=='h'){const id=sel.id;const rs=(L.hubQ[id]||[]).map(i=>L.N[i].r);const fx=gFacts(rs);const s=gSum(id);
  const hi=rs.filter(r=>r.iv>=3).sort((a,b)=>a.date<b.date?-1:1);const early=hi.slice(0,Math.min(2,Math.floor(hi.length/2))),late=hi.slice(-Math.min(2,Math.ceil(hi.length/2)));
  const rel=L.links.filter(l=>l.ka==id||l.kb==id).map(l=>[l.ka==id?l.kb:l.ka,l.w,l.lift]).sort((a,b)=>b[2]-a[2]).slice(0,8);const nw=(L.hubQw[id]||[]).length;
  h=`${GS.guide?`<div class="guide">这里是你的思维地图：点任何一个大节点，看你在这个话题上讲了什么、怎么变化。下面先用最大的节点做示范。</div>`:''}
  <div class="kick">${id[0]=='c'?'概念':id[0]=='d'?'主题':'状态'}</div><h3>${esc(gHubName(id))}</h3>
  <p class="sum">${s?esc(s[0])+`<span class="src">〔${esc(s[1])}〕</span>`:`共 ${rs.length} 句，${fx.from} 至 ${fx.to}，主要出现在 ${fx.tc.map(esc).join('、')} 等 ${fx.nch} 个会话。<span class="src">〔统计描述；fullpass 里没有这个节点的综合结论〕</span>`}</p>
  <div class="facts">${rs.length} 句强归属 · ${fx.from} → ${fx.to} · ${fx.nch} 个会话${nw?` · 另有 ${nw} 句弱关联（默认不画）`:''}</div>
  <h4>时间轨迹（每月句数）</h4>${gSpark(rs)}
  <h4>观点演变</h4>${hi.length>=2?`<div class="lab">早期</div>${early.map(pq).join('')}<div class="lab">近期</div>${late.map(pq).join('')}`:'<p class="empty">高信息量句子太少，无法比较</p>'}
  <h4>显著相关（比随机预期多）</h4><div class="rel">${rel.map(([k,w,lf])=>`<button data-hub="${esc(k)}">${esc(gHubName(k))} <small>${w} 句 · ×${lf.toFixed(1)}</small></button>`).join('')||'<span class="empty">没有显著相关的节点</span>'}</div><p class="src" style="margin:4px 0 0">×n = 实际共现 ÷ 随机预期。只列共现≥8 句且 ≥1.5 倍的。</p>
  <h4>代表原话（按信息量）</h4>${ivSort(rs).slice(0,5).map(pq).join('')}`}
 else if(sel.t=='e'){const A=new Set(L.hubQ[sel.ka]||[]);const co=(L.hubQ[sel.kb]||[]).filter(i=>A.has(i)).map(i=>L.N[i].r);const fx=gFacts(co);
  h=`<div class="kick">关联</div><h3>${esc(gHubName(sel.ka))} — ${esc(gHubName(sel.kb))}</h3>
  ${(()=>{const l=L.links.find(l=>(l.ka==sel.ka&&l.kb==sel.kb)||(l.ka==sel.kb&&l.kb==sel.ka));const tw=h=>{const c={};co.forEach(r=>((r.kw||{})[h]||[]).forEach(w=>c[w]=(c[w]||0)+1));return Object.entries(c).sort((a,b)=>b[1]-a[1]).slice(0,5).map(([w,n])=>`「${esc(w)}」${n}`).join(' ')||'—'};
  return l?`<div class="why"><b>为什么连</b><br>实际共现 <b>${l.w}</b> 句；如果两者互不相关，按各自句数随机预期约 <b>${l.e.toFixed(1)}</b> 句 → 是预期的 <b>${l.lift.toFixed(1)} 倍</b>（Jaccard ${l.j.toFixed(2)}）。<br>${esc(gHubName(sel.ka))} 的依据词：${tw(sel.ka)}<br>${esc(gHubName(sel.kb))} 的依据词：${tw(sel.kb)}</div>`:''})()}
  <p class="sum">这两者在 <b>${co.length}</b> 句里同时出现，时间 ${fx.from} 至 ${fx.to}，集中在 ${fx.tc.map(esc).join('、')} 等 ${fx.nch} 个会话；这些句子主要属于「${fx.td.map(esc).join('」「')}」主题。<span class="src">〔统计描述〕</span></p>
  <h4>时间轨迹</h4>${gSpark(co)}<h4>代表原话（按信息量）</h4>${ivSort(co).slice(0,4).map(pq).join('')||'<p class="empty">无</p>'}
  <div class="rel"><button data-hub="${esc(sel.ka)}">看「${esc(gHubName(sel.ka))}」</button><button data-hub="${esc(sel.kb)}">看「${esc(gHubName(sel.kb))}」</button></div>`}
 else{const r=Q[sel.id];const same=Q.filter(x=>x.chat==r.chat&&(S.sens||!x.s));const k=same.findIndex(x=>x.id==r.id);const ctx=same.slice(Math.max(0,k-3),k+4);
  h=`<div class="kick">原话</div><blockquote class="pb">「${esc(r.q)}」</blockquote><div class="facts">${esc(r.chat)} · ${r.date}${r.tm?' '+r.tm:''} · ${esc(r.dim)}</div>
  <h4>属于哪些节点 · 依据</h4><div class="basis">${r.hs.filter(x=>L.hi[x]!=null).map(x=>`<div><button data-hub="${esc(x)}">${esc(gHubName(x))}</button> <span>${x[0]=='d'?'fullpass 笔记归类 + 句中佐证词：':'命中：'}${esc(gWhy(r,x))}</span></div>`).join('')||'<p class="empty">没有强归属</p>'}${r.hw.filter(x=>L.hi[x]!=null).map(x=>`<div class="wk"><button data-hub="${esc(x)}">${esc(gHubName(x))}</button> <span>弱：${esc(gWhy(r,x))}（默认不画线）</span></div>`).join('')}</div>
  <h4>前后文脉络</h4><p class="src" style="margin:0 0 4px">同一会话里相邻的已收录原话（只有你说的、且通过筛选的句子，不是完整聊天记录）</p>${ctx.map((x,i)=>{const pv=ctx[i-1];let lk='';if(pv){const g=dtm(x)-dtm(pv);const sh=pv.hs.filter(h=>x.hs.includes(h));lk=g>TGAP?`距上一句 ${g>=1440?Math.round(g/1440)+' 天':Math.round(g/60)+' 小时'} · 超过 6 小时，不连`:!sh.length?`距上一句 ${g<60?Math.round(g)+' 分钟':Math.round(g/60)+' 小时'} · 没有共同节点，不连`:`距上一句 ${g<60?Math.round(g)+' 分钟':Math.round(g/60)+' 小时'} · 共同节点「${sh.map(gHubName).join('、')}」，时间链相连`}
   return `${lk?`<div class="gap">${lk}</div>`:''}<div class="qt ${x.id==r.id?'cur':''}" data-id="${x.id}">「${esc(x.q)}」<span class="m">${x.date}${x.tm?' '+x.tm:''}</span></div>`}).join('')}
  <button class="go" id="gopen" style="margin-top:10px">打开原话卡片（指纹、同概念相关）→</button>`}
 el.innerHTML=h;el.scrollTop=0;
 el.querySelectorAll('[data-hub]').forEach(b=>b.onclick=()=>{const id=b.dataset.hub;if(L.hi[id]==null)return;GS.guide=false;GS.sel={t:'h',id};GS.exp=new Set([id]);drawGraph();gPanel()});
 el.querySelectorAll('[data-id]').forEach(b=>b.onclick=()=>{if(GS.sel&&GS.sel.t=='q'&&GS.sel.id==+b.dataset.id)return openCard(+b.dataset.id);GS.guide=false;GS.sel={t:'q',id:+b.dataset.id};drawGraph();gPanel()});
 const go=document.getElementById('gopen');if(go)go.onclick=()=>openCard(sel.id);}

/* ---------- reader ---------- */
function reader(f0){const f=S.hi?f0.filter(r=>r.iv>=3):f0;const ent=r=>`<div class="entry" data-id="${r.id}"><div class="d">${r.date.slice(S.rs=='info'?0:5)}<br>${esc(r.chat.slice(0,10))}<code>#${r.h.slice(0,8)}</code></div><div class="t">${esc(r.q)}</div></div>`;
 const by={};f.forEach(r=>(by[r.date.slice(0,7)]=by[r.date.slice(0,7)]||[]).push(r));const ms=Object.keys(by).sort().reverse();
 const LIM=S.rs=='info'?200:(S.q||S.chat||S.dims.size||S.year?99999:6);
 const body=S.rs=='info'?ivSort(f).slice(0,LIM).map(ent).join('')+(f.length>LIM?`<p class="empty">按信息量显示前 ${LIM} 条，共 ${f.length} 条。<button class="go" id="more">显示全部</button></p>`:''):ms.slice(0,LIM).map(m=>`<h3 id="m${m}">${m}</h3>`+by[m].map(ent).join('')).join('')+(ms.length>LIM?`<p class="empty">只显示最近 ${LIM} 个月。<button class="go" id="more">显示全部 ${ms.length} 个月</button></p>`:'');
 document.getElementById('main').innerHTML=`<div class="kick">Evidence · 原文册（证据库）</div><h2>原文册 <span class="seal" id="seal">哈希链未校验</span></h2>
 <p class="lede">这里是证据库，不是首页内容：回顾里的每个结论都能在这里找到原话。默认按「信息量」排序（长度适中、含观点/判断/因果的句子靠前），并隐藏 ≤12 字且无观点的碎片。信息量是关键词打分，粗糙。所有原话按时间连成哈希链。 <button class="go" id="verify">在本机校验整条链 →</button> <button class="go" id="tamper" style="margin-left:12px;color:var(--ink3)">演示：篡改一个字</button></p>
 <div class="rbar">排序：<button data-rs="info" class="${S.rs=='info'?'on':''}">按信息量</button><button data-rs="time" class="${S.rs=='time'?'on':''}">按时间</button><label style="margin-left:10px"><input type="checkbox" id="rhi" ${S.hi?'checked':''}> 只看高信息量</label><span style="color:var(--ink3)">${f.length} / ${f0.length} 条</span></div>
 <div class="reader"><div class="months">${S.rs=='time'?ms.map(m=>`<a href="#m${m}"><span>${m}</span><span>${by[m].length}</span></a>`).join(''):''}</div>
 <div class="page">${body||'<p class="empty">没有符合条件的原话</p>'}</div></div>`;
 document.querySelectorAll('[data-rs]').forEach(b=>b.onclick=()=>{S.rs=b.dataset.rs;render()});document.getElementById('rhi').onchange=e=>{S.hi=e.target.checked;render()};
 const mo=document.getElementById('more');if(mo)mo.onclick=()=>{document.querySelector('.page').innerHTML=S.rs=='info'?ivSort(f).map(ent).join(''):ms.map(m=>`<h3 id="m${m}">${m}</h3>`+by[m].map(ent).join('')).join('');bindQ()};
 document.getElementById('verify').onclick=async()=>{const v=await request('/api/archive/verify');document.getElementById('seal').textContent=v.valid?`链完整 · ${v.count} 条`:'原始链校验失败';};
 document.getElementById('tamper').onclick=()=>{document.getElementById('seal').textContent='篡改演练请进入原文与旁注；原始档案不改写';};}

function verifyChain(arr){let prev='0'.repeat(64);for(let i=0;i<arr.length;i++){const h=sha256(prev+'|'+arr[i].date+'|'+arr[i].chat+'|'+arr[i].q);if(h!==Q[i].h)return i;prev=h}return -1}
function sha256(str){const b=new TextEncoder().encode(str);const K=[0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2];
 const l=b.length,nb=((l+9+63)>>6)<<6,m=new Uint8Array(nb);m.set(b);m[l]=0x80;const bits=l*8;const dv=new DataView(m.buffer);dv.setUint32(nb-4,bits>>>0);dv.setUint32(nb-8,Math.floor(bits/4294967296));
 let H=[0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19];const w=new Uint32Array(64);const r=(x,n)=>(x>>>n)|(x<<(32-n));
 for(let o=0;o<nb;o+=64){for(let i=0;i<16;i++)w[i]=dv.getUint32(o+i*4);for(let i=16;i<64;i++){const s0=r(w[i-15],7)^r(w[i-15],18)^(w[i-15]>>>3),s1=r(w[i-2],17)^r(w[i-2],19)^(w[i-2]>>>10);w[i]=(w[i-16]+s0+w[i-7]+s1)|0}
  let [a,b2,c,d,e,f,g,h]=H;for(let i=0;i<64;i++){const S1=r(e,6)^r(e,11)^r(e,25),ch=(e&f)^(~e&g),t1=(h+S1+ch+K[i]+w[i])|0,S0=r(a,2)^r(a,13)^r(a,22),mj=(a&b2)^(a&c)^(b2&c),t2=(S0+mj)|0;h=g;g=f;f=e;e=(d+t1)|0;d=c;c=b2;b2=a;a=(t1+t2)|0}
  H=[H[0]+a,H[1]+b2,H[2]+c,H[3]+d,H[4]+e,H[5]+f,H[6]+g,H[7]+h].map(x=>x|0)}
 return H.map(x=>(x>>>0).toString(16).padStart(8,'0')).join('')}
/* ---------- state ---------- */
function state(f){const st=f.filter(r=>r.st&&!r.de),de=f.filter(r=>r.de&&!r.st&&r.dim.includes('交易')),both=f.filter(r=>r.st&&r.de);
 const months=[...new Set(f.map(r=>r.date.slice(0,7)))].sort();const a=months.map(m=>f.filter(r=>r.st&&r.date.startsWith(m)).length),b=months.map(m=>f.filter(r=>r.de&&r.date.startsWith(m)).length);const mx=Math.max(1,...a,...b);
 const W=1240,H=150;const X=i=>20+i*(W-40)/Math.max(1,months.length-1);const bw=Math.max(2,(W-40)/months.length/2.6);
 document.getElementById('main').innerHTML=`<div class="kick">State → Decision · 合并自 v2 的 01 门禁 / 02 知行册 / 07 状态模型</div><h2>睡眠和情绪，怎么流进你的交易决定</h2>
 <p class="lede">左边是只谈状态的话，右边是只谈交易决策的话，中间是两者出现在同一句里的话——那是你自己写下的因果。分类靠关键词，是粗筛，不是诊断。</p>
 <div class="panel" style="margin-bottom:18px"><svg viewBox="0 0 ${W} ${H}" width="100%">${months.map((m,i)=>`<rect x="${X(i)-bw}" y="${H-20-a[i]*(H-40)/mx}" width="${bw}" height="${a[i]*(H-40)/mx}" fill="#3f6e8c"><title>${m} 状态 ${a[i]}</title></rect><rect x="${X(i)}" y="${H-20-b[i]*(H-40)/mx}" width="${bw}" height="${b[i]*(H-40)/mx}" fill="#b5532a"><title>${m} 决策 ${b[i]}</title></rect>${m.endsWith('-01')?`<text x="${X(i)}" y="${H-4}" font-size="11" fill="#a39886" text-anchor="middle">${m}</text>`:''}`).join('')}</svg>
 <div class="legend"><span><i style="background:#3f6e8c"></i>谈状态（睡眠/情绪）</span><span><i style="background:#b5532a"></i>谈决策（仓位/止损/开仓）</span></div></div>
 <div class="cols"><div class="col"><h3>状态</h3><div class="s">${st.length} 句 · 只谈睡眠、情绪、精力</div><div class="scroll">${longest(st,40).map(qt).join('')||'<p class="empty">无</p>'}</div></div>
 <div class="col mid"><h3>同一句里的因果</h3><div class="s">${both.length} 句 · 状态和决策写在一起</div><div class="scroll">${[...both].sort((x,y)=>y.date<x.date?-1:1).map(qt).join('')||'<p class="empty">无</p>'}</div></div>
 <div class="col"><h3>决策</h3><div class="s">${de.length} 句 · 交易主题里谈仓位、止损、开仓</div><div class="scroll">${longest(de,40).map(qt).join('')||'<p class="empty">无</p>'}</div></div></div>`;}
/* ---------- consistency ---------- */
function consist(f){const cs=S.concept?[S.concept]:META.concepts;
 const rows=cs.map(c=>{const a=f.filter(r=>r.c.includes(c)&&r.q.length>=12);return[c,a]}).filter(x=>x[1].length>=4);
 const turns=f.filter(r=>r.t&&r.q.length>=20);
 document.getElementById('main').innerHTML=`<div class="kick">Consistency · 合并自 v2 的 08 同一扇门</div><h2>同一个概念，你早期和最近怎么说</h2>
 <p class="lede">同一扇门这一秒到底开还是关？这里把每个概念最早的两句和最近的两句并排放，让你自己判断是改变了、深化了，还是一直没变。另有带"但是/其实/矛盾"的转折句。</p>
 <div class="tabs">${['',...META.concepts].map(c=>`<button data-k="${esc(c)}" class="${S.concept==c?'on':''}">${c||'全部概念'}</button>`).join('')}</div>
 ${rows.map(([c,a])=>`<div class="pair"><div class="k">${esc(c)}<small>${a.length} 句 · ${a[0].date.slice(0,7)} → ${a[a.length-1].date.slice(0,7)}</small></div><div><div class="lab">早期</div>${a.slice(0,2).map(qt).join('')}</div><div><div class="lab">最近</div>${a.slice(-2).map(qt).join('')}</div></div>`).join('')||'<p class="empty">筛选后没有足够的句子</p>'}
 <h2 style="margin-top:30px">转折句</h2><p class="lede">${turns.length} 句 · 你在话里自己转了个弯的地方（随机抽 24 句，按时间）。</p><div class="mgrid">${pick(turns,24).map(r=>`<div class="mcard">${qt(r)}</div>`).join('')}</div>`;
 document.querySelectorAll('[data-k]').forEach(b=>b.onclick=()=>{S.concept=b.dataset.k;render()});}
/* ---------- topic ---------- */
function topic(f){const T={'AI模型':'合并自 v2 的 10 手感','非洲/海外':'从未被整理过的一线经历','记忆与连续性':'MR 的起点'};
 let body='';
 if(S.topic=='AI模型'){const ms={};f.forEach(r=>r.m.forEach(m=>(ms[m]=ms[m]||[]).push(r)));const arr=Object.entries(ms).sort((a,b)=>b[1].length-a[1].length);const mx=arr.length?arr[0][1].length:1;const used=new Set();const pk=a=>{let p=mid(a.filter(r=>!used.has(r.id)),3);if(!p.length)p=mid(a,1);p.forEach(r=>used.add(r.id));return p};
  body=`<div class="mgrid">${arr.map(([m,a])=>`<div class="mcard"><h3>${esc(m)}<small>${a.length} 句 · ${a[0].date.slice(0,7)} 起</small></h3><div class="bar"><i style="width:${100*a.length/mx}%"></i></div>${pk(a).map(qt).join('')}</div>`).join('')||'<p class="empty">无</p>'}</div>`}
 else{const a=f.filter(r=>S.topic=='非洲/海外'?(r.c.includes('非洲/海外')||r.dim.startsWith('海外')):(r.c.includes('记忆')||r.c.includes('连续性/原文')));
  const by={};a.forEach(r=>(by[r.date.slice(0,4)]=by[r.date.slice(0,4)]||[]).push(r));
  body=`<p class="lede">${a.length} 句，按年份。</p>`+Object.keys(by).sort().map(y=>`<div class="pair"><div class="k">${y}<small>${by[y].length} 句</small></div><div>${mid(by[y],4).slice(0,2).map(qt).join('')}</div><div>${mid(by[y],4).slice(2).map(qt).join('')}</div></div>`).join('')}
 document.getElementById('main').innerHTML=`<div class="kick">Topic cut · ${T[S.topic]}</div><h2>专题：${S.topic}</h2><div class="tabs" style="margin-top:12px">${Object.keys(T).map(t=>`<button data-tp="${t}" class="${S.topic==t?'on':''}">${t}</button>`).join('')}</div>${body}`;
 document.querySelectorAll('[data-tp]').forEach(b=>b.onclick=()=>{S.topic=b.dataset.tp;render()});}
/* ---------- card ---------- */
function openCard(id){const r=Q[id];const rel=Q.filter(x=>x.id!=id&&(S.sens||!x.s)&&x.c.some(c=>r.c.includes(c))).sort((a,b)=>Math.abs(new Date(a.date)-new Date(r.date))-Math.abs(new Date(b.date)-new Date(r.date))).slice(0,6);
 const same=Q.filter(x=>x.chat==r.chat&&x.date==r.date&&x.id!=id&&(S.sens||!x.s)).slice(0,4);
 document.getElementById('dbody').innerHTML=`<div class="kick" style="color:${COL[r.dim]}">${esc(r.dim)}</div><blockquote>「${esc(r.q)}」</blockquote>
 <div class="meta">${esc(r.chat)} · ${r.date}${r.s?' · <b style="color:var(--acc)">敏感</b>':''}</div>
 <div style="margin-top:10px">${r.c.map(c=>`<span class="chip">${esc(c)}</span>`).join(' ')}</div>
 <h4>指纹（哈希链第 ${id+1} 环）</h4><code>${r.h}</code>
 <h4>同一天同一会话</h4>${same.map(qt).join('')||'<p class="empty">无</p>'}
 <h4>同概念、时间最近</h4>${rel.map(qt).join('')||'<p class="empty">无</p>'}
 <p class="empty">原文已逐字核对 fullpass\\_digest 中"我:"发言；上下文请到原始导出里查看。</p>`;
 document.getElementById('drawer').classList.add('open');document.querySelectorAll('#dbody [data-id]').forEach(e=>e.onclick=()=>openCard(+e.dataset.id));}
function closeCard(){nativeEvidenceVersion++;document.getElementById('drawer').classList.remove('open');document.getElementById('drawer').setAttribute('aria-hidden','true');document.getElementById('dbody').replaceChildren();}
document.addEventListener('keydown',e=>{if(e.key=='Escape')closeCard()});
document.getElementById('nav').onclick=e=>{const l=e.target.dataset.l;if(l){S.lens=l;render();scrollTo(0,0)}};
document.getElementById('filters').onclick=e=>{const c=e.target.closest('[data-d]');if(c){const d=c.dataset.d;S.dims.has(d)?S.dims.delete(d):S.dims.add(d);render()}};
const esc4=v=>esc(String(v==null?'':v));
const V4L={cards:v4Cards,hollow:v4Hollow,lab:v4Lab};
LENSES.push(['cards','观察卡'],['hollow','空心叙事'],['lab','交易实验']);
const v4Style='<style>#main .v4{min-width:0;max-width:100%;overflow-wrap:anywhere}'+
  '#main .v4 *{box-sizing:border-box;min-width:0}'+
  '#main .v4 .tabs,#main .v4 .controls{display:flex;flex-wrap:wrap;gap:8px}'+
  '#main .v4 .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,260px),1fr));gap:12px}'+
  '#main .v4 input,#main .v4 svg{max-width:100%}'+
  '#main .v4 .table-wrap{max-width:100%;overflow-x:auto}'+
  '#main .v4 th,#main .v4 td{padding:6px;text-align:left}'+
  '#main .v4 .badge{display:inline-block;padding:2px 6px;border:1px solid currentColor;border-radius:4px}'+
  '#main .v4 .controls label{display:flex;flex-direction:column;max-width:100%}</style>';
function v4Ids(f){return new Set(f.map(r=>r.id));}
function v4Quote(id,ids){return ids.has(id)&&Q[id]?qt(Q[id]):'';}
function v4Show(html){document.getElementById('main').innerHTML=v4Style+'<div class="v4">'+html+'</div>';bindQ();}
function v4Bind(selector,fn){document.querySelectorAll('#main '+selector).forEach(el=>{el.onclick=()=>fn(el);});}
function v4Reasons(item){return '<ul>'+item.reasons.map(r=>'<li>'+esc4(r)+'</li>').join('')+'</ul>';}
function v4Cards(f){
  const d=DATA.v4,ids=v4Ids(f),topics=Array.from(new Set(d.cards.map(c=>c.topic)));
  if(!topics.includes(S.v4Topic))S.v4Topic=topics[0];
  const visible=d.cards.filter(c=>ids.has(c.id)),legacy=d.legacy;
  v4Show('<div class="kick">观察卡</div><p>卡片总数：'+d.cards.length+'；当前筛选可见：'+visible.length+
    '。旧版总数：'+legacy.total+'；保留：'+legacy.kept+'；剔除：'+legacy.dropped.length+'。</p>'+
    '<details><summary>旧版剔除记录</summary><ul>'+legacy.dropped.map(c=>'<li>'+esc4(c.id)+'：'+esc4(c.why)+'</li>').join('')+
    '</ul></details><div class="tabs">'+topics.map((t,i)=>'<button data-topic="'+i+'" class="'+(t===S.v4Topic?'on':'')+'">'+esc4(t)+'</button>').join('')+
    '</div><div class="grid">'+visible.filter(c=>c.topic===S.v4Topic).map(c=>'<article class="mcard"><h3>'+esc4(c.topic)+
    '</h3>'+v4Quote(c.id,ids)+'<small>'+esc4(Q[c.id].chat)+' · '+esc4(Q[c.id].date)+'</small><p>'+esc4(c.why)+
    '</p><span class="badge">'+esc4(c.src)+'</span></article>').join('')+'</div>'+
    (visible.some(c=>c.topic===S.v4Topic)?'':'<p>当前主题没有可见卡片。</p>'));
  v4Bind('[data-topic]',el=>{S.v4Topic=topics[Number(el.dataset.topic)];v4Cards(f);});
}
function v4Hollow(f){
  const d=DATA.v4,ids=v4Ids(f),items=d.hollow.filter(h=>ids.has(h.id));
  v4Show('<div class="kick">空心叙事</div><p class="panel">这是启发式：只看句子里有没有写出 尺度/对手盘/定价位置/资金 四类锚点词，不代表观点对错。</p>'+
    items.map((h,i)=>'<article class="panel"><span class="badge">启发式：'+esc4(h.label)+'</span>'+v4Quote(h.id,ids)+
    '<button data-reason="'+i+'" aria-expanded="false" aria-controls="v4-reason-'+i+'">看理由</button><div id="v4-reason-'+i+'" hidden>'+v4Reasons(h)+'</div></article>').join('')+
    (items.length?'':'<p>当前筛选没有可见语录。</p>')+
    '<h3>09 历史案例</h3><div class="table-wrap"><table><thead><tr>'+['案例','日期','尺度','对手盘','定价位置','资金','状态','语录数','可见语录'].map(s=>'<th>'+s+'</th>').join('')+
    '</tr></thead><tbody>'+d.cases.map(c=>'<tr>'+[c.title,c.date,c.scale,c.cp,c.px,c.cap,c.status,c.nq].map(v=>'<td>'+esc4(v)+'</td>').join('')+
    '<td>'+c.ids.filter(id=>ids.has(id)&&Q[id]).map(id=>'<button data-id="'+esc4(id)+'">语录 '+esc4(id)+'</button>').join(' ')+'</td></tr>').join('')+
    '</tbody></table></div><details><summary>09 判定规则</summary><ol>'+d.rules09.map(r=>'<li>顺序 '+esc4(r.order)+'：'+
    Object.keys(r.when).map(k=>esc4(({scale:'尺度',cp:'对手盘',px:'定价位置',cap:'资金',status:'状态'})[k]||k)+' = '+esc4(r.when[k].join(' / '))).join('；')+
    ' → '+esc4(r.verdict)+'</li>').join('')+'</ol></details>');
  v4Bind('[data-reason]',el=>{
    const box=document.getElementById('v4-reason-'+el.dataset.reason);
    box.hidden=!box.hidden;el.setAttribute('aria-expanded',String(!box.hidden));el.textContent=box.hidden?'看理由':'收起理由';
  });
}
// Returns percentages for pnl and fractions for winRate / wilson. Null means undefined.
function labStats(idx){
  const bp=DATA.v4.lab.cols.bp,values=idx.map(i=>bp[i]).sort((a,b)=>a-b),n=values.length;
  let wins=0,gain=0,loss=0,total=0;
  values.forEach(v=>{total+=v;if(v>0){wins++;gain+=v;}else if(v<0)loss-=v;});
  if(!n)return {n:0,wins:0,winRate:null,wilson:[null,null],mean:null,median:null,profitFactor:null,sum:0};
  const p=wins/n,z=1.959963984540054,z2=z*z,den=1+z2/n,center=(p+z2/(2*n))/den;
  const half=z*Math.sqrt(p*(1-p)/n+z2/(4*n*n))/den,mid=Math.floor(n/2);
  return {n,wins,winRate:p,wilson:[Math.max(0,center-half),Math.min(1,center+half)],mean:total/n/100,
    median:(n%2?values[mid]:(values[mid-1]+values[mid])/2)/100,
    profitFactor:loss?gain/loss:(gain?Infinity:null),sum:total/100};
}
function v4LabFilters(){
  if(!S.labFilters)S.labFilters={ma20Max:'',ma20Min:'',dzMax:'',zcMin:'',nhMin:'',t1Min:'',from:'',to:'',strictMin:false};
  return S.labFilters;
}
function labIndices(filters){
  const c=DATA.v4.lab.cols,p=filters||v4LabFilters();
  const bound=(key,fallback)=>p[key]===''||p[key]==null?fallback:Number(p[key]);
  const max=bound('ma20Max',Infinity)*100,min=bound('ma20Min',-Infinity)*100;
  const from=(p.from||'').replace(/-/g,''),to=(p.to||'').replace(/-/g,'');
  return c.s.map((s,i)=>i).filter(i=>c.ma20[i]<=max&&(p.strictMin?c.ma20[i]>min:c.ma20[i]>=min)&&
    c.dz[i]<=bound('dzMax',Infinity)&&c.zc[i]>=bound('zcMin',-Infinity)&&c.nh[i]>=bound('nhMin',-Infinity)&&
    c.t1[i]>=bound('t1Min',-Infinity)*100&&(!from||c.s[i]>=from)&&(!to||c.s[i]<=to));
}
function v4Histogram(idx){
  const counts=Array(23).fill(0);
  idx.forEach(i=>{const p=Math.max(-15,Math.min(30,DATA.v4.lab.cols.bp[i]/100));counts[Math.min(22,Math.floor((p+15)/2))]++;});
  const peak=Math.max(1,...counts);
  return '<p>盈亏分布：每箱 2%，截断至 −15%～+30%；边缘箱含超界值，末箱为 29%～30%。</p>'+
    '<svg viewBox="0 0 460 150" width="460" role="img" aria-label="盈亏分布直方图">'+counts.map((n,i)=>{
      const h=n/peak*100,lo=-15+2*i,hi=Math.min(30,lo+2);
      return '<rect x="'+(i*19+12)+'" y="'+(115-h)+'" width="17" height="'+h+'" fill="currentColor"><title>'+lo+'%～'+hi+'%：'+n+' 笔</title></rect>';
    }).join('')+'<text x="4" y="140" fill="currentColor">−15%</text><text x="150" y="140" fill="currentColor">0%</text><text x="405" y="140" fill="currentColor">+30%</text></svg>';
}
function v4LabPreset(preset){
  S.labFilters=null;const p=v4LabFilters();
  if(preset==='near')p.ma20Max='3';
  if(preset==='far'){p.ma20Min='8';p.strictMin=true;}
}
function v4Lab(f){
  const d=DATA.v4,meta=d.lab.meta,p=v4LabFilters(),ids=v4Ids(f),idx=labIndices(p),stats=labStats(idx);
  const pct=v=>v===null?'暂无':v.toFixed(2)+'%',exits={};
  idx.forEach(i=>{const key=d.lab.cols.bx[i];exits[key]=(exits[key]||0)+1;});
  const exitNames={take_profit:'止盈',stop_loss:'止损',ma5_trail:'跟踪五日均线出场',ma10_trail:'跟踪十日均线出场',ma20_trail:'跟踪二十日均线出场',timeout:'到期出场'};
  const controls=[['ma20Max','距二十日均线上限（%）','number','0.1'],['ma20Min','距二十日均线下限（%）'+(p.strictMin?'，严格大于':''),'number','0.1'],
    ['dzMax','距涨停锚点天数上限','number','1'],['zcMin','涨停次数下限','number','1'],['nhMin','连续新高天数下限','number','1'],
    ['t1Min','次日开盘跳空下限（%）','number','0.1'],['from','信号日起','date',''],['to','信号日止','date','']];
  const trade=d.tradeq.filter(id=>ids.has(id)&&Q[id]);
  v4Show('<div class="kick">交易实验</div>'+(S.labFrom!=null&&ids.has(S.labFrom)?'<div class="panel"><h3>由这条语录进入</h3>'+v4Quote(S.labFrom,ids)+'</div>':'')+
    '<p class="panel">数据：v2/04 龙头二波样本 '+esc4(meta.n)+' 笔 / '+esc4(meta.codes)+' 只，信号日 '+esc4(meta.smin)+'–'+esc4(meta.smax)+
    '；盈亏用原表出场（未在本页重放出场规则，完整出场重放请用独立版 v2\\04-dragon-backtest\\index.html）；无佣金印花税滑点；不是全市场回测，不是买卖建议。</p>'+
    '<div class="tabs"><button data-preset="all">全样本</button><button data-preset="near">靠近MA20(≤3%)</button><button data-preset="far">远离MA20(&gt;8%)</button></div>'+
    '<p>留空表示不限；均线距离与跳空均以百分比输入。</p><div class="controls">'+controls.map(([key,label,type,step])=>
    '<label>'+label+'<input data-filter="'+key+'" type="'+type+'"'+(step?' step="'+step+'"':'')+' value="'+esc4(p[key])+'"></label>').join('')+'</div>'+
    '<div class="panel" aria-live="polite"><p>样本数：'+stats.n+(stats.n<30?' · 样本太少':stats.n<80?' · 区间还宽':'')+'</p>'+
    '<p>胜率：'+pct(stats.winRate===null?null:stats.winRate*100)+'；威尔逊 95% 区间：'+stats.wilson.map(v=>pct(v===null?null:v*100)).join('～')+
    '</p><p>平均盈亏：'+pct(stats.mean)+'；中位盈亏：'+pct(stats.median)+'；盈利因子：'+(stats.profitFactor===null?'暂无':stats.profitFactor===Infinity?'∞':stats.profitFactor.toFixed(2))+
    '；盈亏百分比之和：'+pct(stats.sum)+'（非复利收益）</p>'+v4Histogram(idx)+
    '<h3>出场类型计数</h3><ul>'+Object.keys(exits).map(k=>'<li>'+esc4(exitNames[k]||('其他出场（'+k+'）'))+'：'+exits[k]+'</li>').join('')+'</ul></div>'+
    '<h3>交易相关语录</h3>'+trade.slice(0,S.labAll?trade.length:12).map(id=>v4Quote(id,ids)).join('')+
    (trade.length>12?'<button data-expand="trade">'+(S.labAll?'收起':'展开全部')+'</button>':'')+(trade.length?'':'<p>当前筛选没有可见语录。</p>'));
  document.querySelectorAll('#main [data-filter]').forEach(el=>{el.onchange=()=>{
    p[el.dataset.filter]=el.value;if(el.dataset.filter==='ma20Min')p.strictMin=false;v4Lab(f);
  };});
  v4Bind('[data-preset]',el=>{v4LabPreset(el.dataset.preset);v4Lab(f);});
  v4Bind('[data-expand]',()=>{S.labAll=!S.labAll;v4Lab(f);});
}
function openLab(id){S.lens='lab';S.labFrom=id;render();scrollTo(0,0);}
const _oc4=openCard;
openCard=function(id){
  _oc4(id);
  if(!DATA.v4)return;
  const key=Number(id),d=DATA.v4,body=document.getElementById('dbody');
  if(!body)return;
  const h=d.hollow.find(item=>item.id===key),cards=d.cards.filter(item=>item.id===key);
  let html='';
  if(h)html+='<section><h4>空心叙事（启发式）</h4><p>启发式：'+esc4(h.label)+'</p>'+v4Reasons(h)+'</section>';
  if(d.tradeq.includes(key))html+='<button id="v4-open-lab">去交易实验 →</button>';
  if(cards.length)html+='<section><h4>观察卡</h4>'+cards.map(c=>'<p>'+esc4(c.topic)+'：'+esc4(c.why)+'</p>').join('')+'</section>';
  if(html)body.insertAdjacentHTML('beforeend',html);
  if(d.tradeq.includes(key)){
    const button=document.getElementById('v4-open-lab');
    if(button)button.onclick=()=>{closeCard();openLab(key);};
  }
};


let qtm;document.getElementById('q').oninput=e=>{clearTimeout(qtm);qtm=setTimeout(()=>{S.q=e.target.value;render()},200)};
document.getElementById('priv').onchange=async e=>{closeCard();S.sens=e.target.checked;const fresh=await request('/api/archive/data?sensitive='+Number(S.sens));DATA.porS=fresh.porS;Q.splice(0,Q.length,...fresh.quotes);DIMS.splice(0,DIMS.length,...new Set(Q.filter(r=>r.dim).map(r=>r.dim)));CHATS.splice(0,CHATS.length,...new Set(Q.filter(r=>r.chat).map(r=>r.chat)));DIMS.forEach((d,i)=>COL[d]=PAL[i%PAL.length]);render()};
addEventListener('resize',()=>{if(S.lens=='graph'){GS.T=null;drawGraph()}});
document.getElementById('foot').textContent=`构建于 ${META.built} · 数据 历史归档数据（${META.src_mtime}）· 保留 ${META.stats.kept} 条，核对未命中丢弃 ${META.stats.unverified_dropped||0} 条，隐私排除 ${META.stats.excluded_private||0} 条 · 历史档案 + 本机后端；统计口径保留来源`;

const caps=await request('/api/runtime/capabilities');runtimeToken=caps.token;
const safe=v=>esc(String(v??''));
const when=v=>safe(v||'时间未知');
const memoryLink=id=>`<button class="go" data-memory="${safe(id)}">查看 SB 与依据 →</button>`;
const runtimeViews={native:runtimeSearch,evolution:runtimeEvolution,sources:runtimeSources,operations:runtimeOperations};
LENSES.push(['native','记忆检索'],['evolution','记忆演进'],['sources','来源与版本'],['operations','后端管理']);
if(!DATA.v4){LENSES.splice(LENSES.findIndex(x=>x[0]==='cards'),3);}

function runtimeShell(title,caption){closeCard();document.getElementById('main').innerHTML=`<h1>${safe(title)}</h1><p class="lede">${safe(caption)}</p><div id="runtime-body" aria-live="polite"></div>`;return document.getElementById('runtime-body');}
function runtimeStatus(root,error){root.innerHTML=`<p class="empty" role="status">${safe(error.message||error)}</p>`;}
function nativeReady(root){if(caps.storage)return true;runtimeStatus(root,'尚未连接 MR-Mem 原生存储。历史回顾、图谱、原文册与画像仍可使用。');return false;}
function bindNative(root){root.querySelectorAll('[data-memory]').forEach(button=>button.onclick=()=>runtimeDetail(button.dataset.memory));root.querySelectorAll('[data-native-evidence]').forEach(button=>button.onclick=()=>runtimeEvidence(button));}
async function runtimeDetail(id){
  const root=runtimeShell('记忆详情','SB、成熟段与原文保持各自来源，不将模型理解当作原话。');
  const v=++runtimeVersion;runtimeStatus(root,'正在读取…');
  try{const data=await request('/api/runtime/detail?id='+encodeURIComponent(id));if(v!==runtimeVersion||!Object.values(runtimeViews).includes(runtimeViews[S.lens]))return;
    root.innerHTML=`<article class="panel"><h2>${safe(data.text)}</h2><p class="src">${when(data.ts)}</p><div class="actions">${data.evidence.map((e,i)=>`<button data-native-evidence data-id-native="${safe(id)}" data-index="${i}" data-fingerprint="${safe(e.fingerprint)}">原文证据 ${i+1}</button>`).join(' ')}</div></article><h2 class="runtime-section">关联成熟段</h2>`+
      (data.segments.map(s=>`<article class="panel"><p>${safe(s.summary)}</p><small>来源版本顺序 ${safe(s.last_seq)}</small><p>${s.member_ids.map(memoryLink).join(' · ')}</p></article>`).join('')||'<p class="empty">暂无可验证成熟段。</p>');
    bindNative(root);globalThis.AtlasMotion?.enter(root,'detail');
  }catch(error){if(v===runtimeVersion)runtimeStatus(root,error);}
}

async function runtimeEvidence(button){
  closeCard();const v=++nativeEvidenceVersion;
  try{const route=button.dataset.raw?'raw-evidence':'evidence';const p=new URLSearchParams({id:button.dataset.idNative,index:button.dataset.index||'0',fingerprint:button.dataset.fingerprint});
    const data=await request('/api/runtime/'+route+'?'+p);if(v!==nativeEvidenceVersion)return;
    const drawer=document.getElementById('drawer');
    document.getElementById('dbody').innerHTML=`<h2>${data.source_kind==='legacy_quote_extract'?'历史原话摘录':'来源原文'}</h2>${data.source_kind==='legacy_quote_extract'?'<p class="meta">这是既有编译档案中的已核对摘录，不冒充完整原始消息。</p>':''}<p class="meta">${when(data.ts)} · ${safe(data.role)}</p><blockquote>${safe(data.quote)}</blockquote><details><summary>版本与来源指针</summary><pre>${safe(JSON.stringify(data.ref,null,2))}</pre><p>来源作用域与内容指纹已校验。</p></details>`;
    drawer.classList.add('open');drawer.setAttribute('aria-hidden','false');document.getElementById('close-original').focus();
  }catch(error){if(v===nativeEvidenceVersion)document.getElementById('dbody').textContent=error.message;}
}
async function runtimeSearch(){
  ++runtimeVersion;
  const root=runtimeShell('记忆检索','使用 MR-Mem 原生检索与排序；按服务配置可能调用查询向量或模型。');
  if(!nativeReady(root)||!caps.service)return runtimeStatus(root,'尚未连接 MR-Mem 检索服务。');
  root.innerHTML='<form id="native-find"><label for="native-q">检索记忆</label><input id="native-q" type="search" required><button>检索</button></form><p id="native-state" role="status"></p><div id="native-results"></div>';
  document.getElementById('native-find').onsubmit=async e=>{e.preventDefault();const v=++runtimeVersion;document.getElementById('native-state').textContent='正在检索…';
    try{const data=await request('/api/runtime/search?q='+encodeURIComponent(document.getElementById('native-q').value));if(v!==runtimeVersion||S.lens!=='native')return;
      document.getElementById('native-state').textContent=`按后端顺序显示 ${data.items.length} 项`;
      const results=document.getElementById('native-results');results.innerHTML=data.items.map(item=>`<article class="panel"><p class="native-readout">${safe(item.text)}</p>${item.memory_ids.map(memoryLink).join(' ')}${item.raw_source?`<button data-native-evidence data-raw="1" data-id-native="${safe(item.raw_source.id)}" data-fingerprint="${safe(item.raw_source.fingerprint)}">查看来源原文 →</button>`:''}${item.memory_ids.length||item.raw_source?'':'<small>原生读出暂无 SB 跳转</small>'}</article>`).join('');bindNative(results);globalThis.AtlasMotion?.enter(results);
    }catch(error){if(v===runtimeVersion&&document.getElementById('native-state'))document.getElementById('native-state').textContent=error.message;}
  };
}
async function runtimeEvolution(){
  const v=++runtimeVersion;const root=runtimeShell('记忆演进','Line 保留原生身份、分支和承接；段摘要只描述已成熟的一截。');if(!nativeReady(root))return;
  runtimeStatus(root,'正在读取原生结构…');
  try{const [graph,segments,products,catalog]=await Promise.all(['graph','segments','products','catalog'].map(route=>request('/api/runtime/'+route)));if(v!==runtimeVersion||S.lens!=='evolution')return;
    const names=new Map(catalog.items.map(m=>[m.id,m.text]));
    root.innerHTML=`<div class="nums"><div><b>${graph.lines.length}</b><span>原生 Line</span></div><div><b>${segments.segment_count}</b><span>成熟段版本</span></div><div><b>${catalog.total}</b><span>可验证 SB</span></div></div>`+
      (!graph.available?`<p class="empty">${safe(graph.reason)}</p>`:graph.lines.map(line=>`<article class="panel"><h2>Line <code>${safe(line)}</code></h2>${graph.nodes.filter(n=>n.line_id===line).map(n=>`<p>${safe(n.text||names.get(n.memory_id)||'已编译 SB')} ${n.evidence_complete?memoryLink(n.memory_id):'<span class="tag">来源不完整，保留历史投影</span>'}</p>`).join('')}<details><summary>承接与分支</summary><pre>${safe(JSON.stringify(graph.edges.filter(e=>e.line_id===line),null,2))}</pre></details></article>`).join(''))+
      '<h2 class="runtime-section">成熟段</h2>'+segments.segments.map(s=>`<article class="panel"><p>${safe(s.summary)}</p><small>来源版本顺序 ${safe(s.last_seq)}</small><p>${s.member_ids.map(memoryLink).join(' ')}</p></article>`).join('')+
      '<h2 class="runtime-section">晨昏线</h2><details><summary>记忆侧判断与后续落定（不等于事实认证）</summary><pre>'+safe(JSON.stringify({said:graph.tense||[],settled:graph.settled||[]},null,2))+'</pre></details>'+'<h2 class="runtime-section">Thread 与语义关系</h2><details><summary>原生投影数据（不补写缺失字段）</summary><pre>'+safe(JSON.stringify(products,null,2))+'</pre></details>';
    bindNative(root);
  }catch(error){if(v===runtimeVersion)runtimeStatus(root,error);}
}
async function runtimeSources(){
  const v=++runtimeVersion;const root=runtimeShell('来源与版本','消息时间未知则保留未知；known_at 表示语义提交时间，不冒充事件时间。');if(!nativeReady(root))return;
  try{const [catalog,history,sources]=await Promise.all(['catalog?offset='+(S.nativeOffset||0),'history','sources?offset='+(S.sourceOffset||0)].map(r=>request('/api/runtime/'+r)));if(v!==runtimeVersion||S.lens!=='sources')return;
    root.innerHTML=`<h2>语义记忆 · ${catalog.total}</h2><div class="mgrid">${catalog.items.map(item=>`<article class="mcard"><p>${safe(item.text)}</p><p class="src">消息时间 ${when(item.ts)} · 提交时间 ${when(item.known_at)}</p>${memoryLink(item.id)}${item.attributes.standing==='true'?'<span class="tag">长期指令或偏好</span>':''}</article>`).join('')}</div><button id="native-prev">上一页</button><button id="native-next">下一页</button>`+
      `<h2 class="runtime-section">来源消息 · ${sources.total}</h2>${sources.items.map(r=>`<article class="record"><p>${when(r.ts)} · ${safe(r.role)} · ${safe(r.session_display_name||r.session_id)}${r.time_precision==='day'?' · 日期精度':''}</p><button data-native-evidence data-raw="1" data-id-native="${safe(r.id)}" data-fingerprint="${safe(r.fingerprint)}">查看来源原文</button></article>`).join('')}<button id="source-prev">上一页来源</button><button id="source-next">下一页来源</button>`+
      `<details><summary>生命周期与取代历史 · ${history.total}</summary><pre>${safe(JSON.stringify(history.items,null,2))}</pre></details>`;
    for(const [id,key,total] of [['native','nativeOffset',catalog.total],['source','sourceOffset',sources.total]]){
      const offset=S[key]||0;document.getElementById(id+'-prev').disabled=offset===0;document.getElementById(id+'-next').disabled=offset+50>=total;
      document.getElementById(id+'-prev').onclick=()=>{S[key]=Math.max(0,offset-50);runtimeSources()};document.getElementById(id+'-next').onclick=()=>{S[key]=offset+50;runtimeSources()};
    }bindNative(root);
  }catch(error){if(v===runtimeVersion)runtimeStatus(root,error);}
}
async function runtimeOperations(){
  ++runtimeVersion;const root=runtimeShell('后端管理','健康检查不调用模型。Add 和补编只由显式操作触发，费用与行为遵循 MR-Mem 服务配置。');
  root.innerHTML=`<p>原生存储：${caps.storage?'已配置':'未配置'} · 服务：${caps.service?'已配置':'未配置'} · 写操作：${caps.mutations?'已启用':'未启用'}</p><button id="runtime-health">检查健康状态</button><pre id="runtime-status"></pre><form id="runtime-add"><h2>新增消息</h2><label>会话 ID <input name="session" required></label><label>请求 ID（重试保持相同）<input name="request" required value="${safe(crypto.randomUUID())}"></label><label>消息时间（可留空）<input name="timestamp" placeholder="ISO 8601"></label><label>原文<textarea name="content" rows="6" required></textarea></label><button ${caps.mutations?'':'disabled'}>提交到 MR-Mem</button></form><h2 class="runtime-section">补编待处理窗口</h2><p>现有服务的 Flush 作用于整个实例的所有待处理用户，不仅是当前作用域。</p><label><input type="checkbox" id="runtime-flush-all"> 我确认编译当前实例的全部待处理窗口</label><button id="runtime-flush" disabled>执行实例补编</button><p id="runtime-result" role="status"></p>`;
  document.getElementById('runtime-health').disabled=!caps.service;
  const statusElement=document.getElementById('runtime-status');
  document.getElementById('runtime-health').onclick=async()=>{try{const health=await request('/api/runtime/health');if(statusElement.isConnected)statusElement.textContent=JSON.stringify(health,null,2)}catch(error){if(statusElement.isConnected)statusElement.textContent=error.message}};
  const resultElement=document.getElementById('runtime-result');const result=()=>resultElement;
  document.getElementById('runtime-add').onsubmit=async e=>{e.preventDefault();if(!caps.mutations)return;const form=e.target;const fields=new FormData(form);const message={role:'user',content:fields.get('content')};if(fields.get('timestamp'))message.timestamp=fields.get('timestamp');
    const button=form.querySelector('button');button.disabled=true;result().textContent='正在提交…';
    try{const response=await request('/api/runtime/add',{request_id:fields.get('request'),session_id:fields.get('session'),messages:[message]});result().textContent=JSON.stringify(response);}
    catch(error){result().textContent=error.message;}finally{button.disabled=false;}
  };
  document.getElementById('runtime-flush-all').onchange=e=>{document.getElementById('runtime-flush').disabled=!e.target.checked||!caps.mutations};
  document.getElementById('runtime-flush').onclick=async e=>{e.target.disabled=true;result().textContent='正在补编…';try{result().textContent=JSON.stringify(await request('/api/runtime/flush',{scope:'all_users'}))}catch(error){result().textContent=error.message}finally{e.target.disabled=false}};
}

const h=location.hash.slice(1);if(LENSES.some(l=>l[0]==h))S.lens=h;if(h=='graph-ai'){S.lens='graph';GS.exp.add('c:AI模型');GS.sel={t:'h',id:'c:AI模型'}}
document.getElementById('close-original').onclick=closeCard;document.addEventListener('visibilitychange',()=>{if(document.hidden)closeCard()});
render();
addEventListener('hashchange',()=>{const h=location.hash.slice(1);if(LENSES.some(l=>l[0]==h)){S.lens=h;render();scrollTo(0,0)}});

})().catch(e=>{document.getElementById('main').textContent='界面载入失败：'+e.message;});