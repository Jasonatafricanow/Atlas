import argparse,json,hashlib,threading,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from pathlib import Path
class DemoCompiler:
    """Deterministic fictional protocol fixture; not a semantic compiler."""
    def complete(self,prompt):
        material=json.loads(prompt.split("INPUT:\n",1)[1])
        return json.dumps(dict(matters=[],blocks=[dict(content=m['text'],sources=[m['id']],**{'in':[]}) for m in material['NEW']],carry_from=None))
from mr_mem_aml.compiler import SemanticCompiler
from mr_mem_aml.config import RuntimeConfig
from mr_mem_aml.runtime import MemoryRuntime
from mr_mem_aml.server import RuntimeHost,build_server
from atlas.server import create_server
parser=argparse.ArgumentParser();parser.add_argument('--out-dir',type=Path,required=True)
base=parser.parse_args().out_dir
base.mkdir(exist_ok=True)
rows=[];prev='0'*64
for i,(date,text,dim) in enumerate([('2024-01-01','虚构园丁计划先试种蓝色花朵。','试种计划'),('2024-02-02','虚构园丁观察雨水收集的效果。','观察记录'),('2024-03-03','虚构园丁决定继续记录，再考虑扩大规模。','试种计划')]):
    h=hashlib.sha256((prev+'|'+date+'|虚构会话|'+text).encode()).hexdigest()
    rows.append(dict(id=i,q=text,date=date,tm='',chat='虚构会话',dim=dim,h=h,s=False,e=0,c=['花圃'],hs=['c:花圃'],kw={'c:花圃':['花朵']},hw=[],m=[],iv=5,st=False,de=True,t=False));prev=h
archive=dict(meta=dict(built='2024-03-03',src_mtime='2024-03-03',concepts=['花圃'],stats=dict(kept=3,excluded_private=0,unverified_dropped=0)),quotes=rows,ins=dict(headline='虚构花圃的观察与试种',headline_src='虚构笔记',lede=[['只展示虚构样例，用于界面与后端验收。','虚构来源']],cards=[],dimdesc={},hubsum={}),por=dict(secs=[],skipped=[],stat=dict(items=0,quotes=0,verified=0)))
(base/'archive.json').write_text(json.dumps(archive,ensure_ascii=False),encoding='utf-8')
text='虚构园丁决定先试种，再记录结果。';sha=hashlib.sha256(text.encode()).hexdigest();identifier='fiction-page';chain=hashlib.sha256(('GENESIS\n'+sha+'\n'+identifier).encode()).hexdigest()
folio=dict(format='folio-sealed-v1',title='虚构原文册',bound='2024-03-03',genesis='GENESIS',trust=dict(aiMayRead=True,aiMayWrite=dict(original=False)),audit=[],meta=dict(pages=1,chars=len(text),bound='2024-03-03',note='虚构样例'),entries=[dict(id=identifier,diary_date='2024-03-03',spoken_at='2024-03-03 10:00',time_precision='minute',time_note='',title='虚构试种',topic='试种',status='live',tombstone_at=None,cut=[],text_note='',source=dict(file='fiction.txt',line=1,author='虚构园丁',kind='verbatim'),versions=[dict(n=1,role='original',origin='verbatim',author='虚构园丁',text=text,sha256=sha,at='2024-03-03 10:00',note='')],annotations=[],chain_prev='GENESIS',chain=chain)])
(base/'folio.json').write_text(json.dumps(folio,ensure_ascii=False),encoding='utf-8')
cfg=RuntimeConfig(data_dir=base/'native',compiler={'type':'command','argv':['unused']},host='127.0.0.1',port=0,path_a_engine='tree',placement='points',raw_base=True,line_read={'raw_fill':0,'hit_anchors':True})
host=RuntimeHost(lambda:MemoryRuntime(cfg,compiler=SemanticCompiler(DemoCompiler(),schema='tree')))
backend=build_server(cfg,host);threading.Thread(target=backend.serve_forever,daemon=True).start()
host.add(dict(request_id='fiction-request',user_id='fiction-user',session_id='fiction-session',messages=[dict(role='user',content='Fictional garden has blue flowers.',timestamp=1704067200000)]));host.flush('fiction-user')
ui=create_server(base/'native',port=0,mrmem_user='fiction-user',mrmem_url=f'http://127.0.0.1:{backend.server_port}',archive_file=base/'archive.json',folio_file=base/'folio.json',state_dir=base/'state',runtime_writes=True)
(base/'ready.json').write_text(json.dumps(dict(ui=f'http://127.0.0.1:{ui.server_port}',native=f'http://127.0.0.1:{backend.server_port}')),encoding='utf-8')
print('SYNTHETIC FULL APP READY',flush=True)
try:ui.serve_forever()
finally:ui.server_close();backend.shutdown();backend.server_close();host.close()
