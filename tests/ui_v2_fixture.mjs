// Fictional, in-memory HTTP fixture. No database, generation task or data directory.
import {createServer} from 'node:http';
import {readFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
export async function previewServer() {
  const node = {node_id:'fiction-topic',name:'虚构花圃的用水计划',type:'topic',evidence:[]};
  const nodes = [node, ...['雨水收集','试种记录','虚构园丁'].map((name,i) => ({node_id:`fiction-${i}`,name,type:'concept'}))];
  const pointer = {doc_id:'fiction-doc',span:[0,8],quote_hash:'fiction-hash'};
  const timeline = Array.from({length:14},(_,i) => ({statement_id:`fiction-s${i}`,source:{statement_id:`fiction-s${i}`,text:i%3===1 ? '雨水收集的效果低于预期，下一轮试种将改用分区浇灌。' : '继续记录虚构花圃的用水情况，等待下一次试种结果。',kind:'opinion',speaker:'虚构园丁',ts:i ? `2025-06-${String(i+1).padStart(2,'0')}T10:30:00Z` : null,stance:'试种观察',about:[node.node_id],evidence:[pointer]},annotations:[{shift:i===0?'first':i%3===1?'reverse':'same',shift_source:'model',reason:'依据虚构试种记录调整已有判断。',outcome:i%2?'confirmed':'unknown',outcome_reason:'仅为虚构标注。',outcome_statement_ids:[]}]}));
  const derived = {line_count:1,shift_count:5,confirmed_count:4,pending_count:4,point_count:14,current_stance:'试种观察',outcome_counts:{supported:7,contradicted:0,unknown:7},accuracy:1,accuracy_basis:'已知 7 / 共 14',stability:.6,time_span:{first:'2025-06-02',last:'2025-06-14'}};
  const line = {topic_node_id:node.node_id,name:node.name,lines:[{line_id:'fiction-line',title:node.name}],timeline,derived};
  const props = Array.from({length:8},(_,i) => ({prop_id:`fiction-p${i}`,text:'虚构园丁倾向先小规模试种，再决定是否扩大雨水收集。',status:i<4?'confirmed':'proposed',kind:'preference',confidence:.7,subject_node_ids:[node.node_id],evidence:[pointer]}));
  const entity = {node,nodes,edges:nodes.slice(1).map((n,i)=>({edge_id:`fiction-e${i}`,src:node.node_id,dst:n.node_id,type:'related_to',status:i===2?'superseded':'active',evidence:[]})),aliases:[{name:'虚构用水试验'}],lines:[line],statements:timeline.map(p=>p.source),propositions:props,mentions_index_available:true,mention_count:12,mentions:Array.from({length:12},(_,i)=>({doc_id:`fiction-doc-${i}`,display_name:`虚构试种会话 ${i+1}`,ts:i?'2025-06-01':null,associated_node_count:3,token:`fiction-mention-${i}`})),merge_suggestions:[]};
  const server = createServer(async (req,res) => {
    try {
      const url = new URL(req.url,'http://127.0.0.1');
      res.setHeader('Cache-Control','no-store');
      if (url.pathname.startsWith('/api/')) {
        const route = url.pathname.slice(5);
        const data = {home:{nodes,lines:[line],propositions:props,derived},toc:{nodes,lines:[line]},lines:{nodes,lines:[line]},line:{node,line},entities:{nodes},entity,search:{results:[{line},{node},{proposition:props[0]}]},evidence:{quote:'虚构花圃的雨水收集需要更多试种证据。',before:'本段仅用于离线界面验收。',after:'后续记录继续保留未知，不补写事实。',pointer,ts:null,author:'虚构园丁',derived:{session_display_name:'虚构试种会话'}}}[route];
        res.setHeader('Content-Type','application/json; charset=utf-8'); res.end(JSON.stringify(data));
      } else {
        const path = url.pathname === '/' ? '/app.html' : url.pathname;
        if (!/^\/(?:app\.html|theme\.css|js\/[\w/-]+\.js)$/.test(path)) {res.writeHead(404).end();return;}
        const content = await readFile(new URL(`../web${path}`,import.meta.url));
        res.setHeader('Content-Type',path.endsWith('.css')?'text/css':path.endsWith('.js')?'text/javascript':'text/html; charset=utf-8');res.end(content);
      }
    } catch {res.writeHead(500).end();}
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  return {server,url:`http://127.0.0.1:${server.address().port}`};
}
if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const {url} = await previewServer(); console.log(url);
}
