"""Structured, scoped read projections over MR-Mem bb0d296; no runtime initialization."""
import hashlib
import json
from contextlib import closing
from .mrmem_reader import MrMemReader


class MrMemFull(MrMemReader):
    def precision(self, record_id):
        with closing(self.connect('aml_source.sqlite')) as db:
            exists=db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='atlas_source_precision'").fetchone()
            if not exists: return {}
            row=db.execute('SELECT * FROM atlas_source_precision WHERE record_id=?',(record_id,)).fetchone()
        return dict(row) if row else {}

    def item(self, memory):
        result=super().item(memory)
        dates=[]
        for ref in memory['provenance'].get('source_refs',[]):
            meta=self.precision(ref['record_id'])
            if meta.get('precision')=='day': dates.append(meta['source_date'])
            elif result['ts']: dates.append(result['ts'])
        if dates: result['ts']=min(dates)
        return result

    def evidence(self, params):
        result=super().evidence(params)
        meta=self.precision(result['ref']['record_id'])
        if meta.get('precision')=='day': result['ts']=meta['source_date']
        result.update(source_kind=meta.get('source_kind'),time_precision=meta.get('precision'))
        return result

    def search(self, params):
        result=super().search(params)
        if result.get('search_mode')=='mrmem_runtime':
            for item in result['items']:
                if not item['id'].startswith('raw:'): continue
                record=item['id'][4:]
                with closing(self.connect('aml_source.sqlite')) as db:
                    row=db.execute('SELECT fingerprint FROM messages WHERE user_id=? AND record_id=?',(self.user_id,record)).fetchone()
                if row is None: continue
                try: evidence=self.raw_evidence(dict(id=record,fingerprint=row['fingerprint']))
                except (KeyError,ValueError): continue
                item['raw_source']=dict(id=record,fingerprint=row['fingerprint'])
                item['ts']=evidence['ts']
        return result

    def catalog(self, params):
        offset=max(0,int(params.get('offset',0))); limit=min(100,max(1,int(params.get('limit',50))))
        memories=self.memories(); valid=[]
        for memory in memories.values():
            try: item=self.item(memory)
            except (ValueError,KeyError): continue
            item.update(known_at=memory.get('committed_at'),compiler_version=memory['provenance'].get('extractor_version'),attributes=dict(memory.get('attributes',[])),
                        supports=memory.get('supports_memory_ids',[]),contradicts=memory.get('contradicts_memory_ids',[]))
            valid.append(item)
        valid.sort(key=lambda r:(r['ts'] is None,r['ts'] or '',r['id']))
        return dict(items=valid[offset:offset+limit],total=len(valid),offset=offset,limit=limit)

    def detail(self, params):
        item=super().detail(params)
        memory=self.memories()[params['id']]
        item.update(known_at=memory.get('committed_at'),compiler_version=memory['provenance'].get('extractor_version'),
                    attributes=dict(memory.get('attributes',[])),supports=memory.get('supports_memory_ids',[]),
                    contradicts=memory.get('contradicts_memory_ids',[]))
        return item

    def history(self, params):
        with closing(self.connect('memory.sqlite')) as db:
            rows=[json.loads(r[0]) for r in db.execute('SELECT payload FROM canonical_memory')]
        rows=[dict(id=r['memory_id'],lifecycle=r['lifecycle'],known_at=r.get('committed_at'),
                   supersedes=r.get('supersedes_memory_id')) for r in rows
              if r['scope'].get('domain')=='user' and r['scope'].get('user_id')==self.user_id]
        offset=max(0,int(params.get('offset',0)))
        return dict(items=rows[offset:offset+100],total=len(rows),offset=offset,limit=100)

    def sources(self, params):
        offset=max(0,int(params.get('offset',0))); limit=50
        with closing(self.connect('aml_source.sqlite')) as db:
            total=db.execute('SELECT COUNT(*) FROM messages WHERE user_id=?',(self.user_id,)).fetchone()[0]
            rows=db.execute('SELECT record_id,session_id,role,occurred_at,time_given,fingerprint,seq FROM messages WHERE user_id=? ORDER BY seq LIMIT ? OFFSET ?',
                            (self.user_id,limit,offset)).fetchall()
        items=[]
        for r in rows:
            meta=self.precision(r['record_id'])
            items.append(dict(id=r['record_id'],session_id=r['session_id'],session_display_name=meta.get('session_display_name'),role=r['role'],ts=meta['source_date'] if meta.get('precision')=='day' else r['occurred_at'] if r['time_given'] else None,fingerprint=r['fingerprint'],position=r['seq'],time_precision=meta.get('precision'),source_kind=meta.get('source_kind')))
        return dict(items=items,total=total,offset=offset,limit=limit)

    def raw_evidence(self, params):
        with closing(self.connect('aml_source.sqlite')) as db:
            row=db.execute('SELECT session_id FROM messages WHERE user_id=? AND record_id=?',(self.user_id,params['id'])).fetchone()
        if row is None: raise KeyError('source unavailable')
        ref=dict(source_namespace='aml',session_id=row['session_id'],record_id=params['id'],fingerprint=params['fingerprint'])
        source=self.source(ref)
        meta=self.precision(params['id'])
        return dict(ref=ref,quote=source['content'],role=source['role'],ts=meta['source_date'] if meta.get('precision')=='day' else source['occurred_at'] if source['time_given'] else None,verification='source_fingerprint_matched',source_kind=meta.get('source_kind'),time_precision=meta.get('precision'))

    def graph(self, params):
        with closing(self.connect('memory.sqlite')) as db:
            all_memories=[json.loads(r[0]) for r in db.execute('SELECT payload FROM canonical_memory')]
        scoped={m['memory_id']:m for m in all_memories if m['scope'].get('user_id')==self.user_id and m['scope'].get('domain')=='user'}
        valid=set()
        # Graph validity must not depend on the UI page size.
        for m in self.memories().values():
            try: self.item(m); valid.add(m['memory_id'])
            except (ValueError,KeyError): pass
        scope={k:None for k in ['agent_id','persona_id','relationship_id','world_id','interaction_id']}
        scope.update(domain='user',user_id=self.user_id)
        key=hashlib.sha256(json.dumps(scope,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        root=self.root/'lce_tree'/key
        if not (root/'lines.sqlite').is_file():
            return dict(available=False,lines=[],nodes=[],edges=[],reason='当前作用域尚无持久化 Line 图')
        with closing(self.connect(str((root/'lines.sqlite').resolve()))) as db:
            tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not {'line_nodes','line_node_states','line_node_memberships','line_edge_revisions'} <= tables:
                return dict(available=False,lines=[],nodes=[],edges=[],reason='Line 版本合同不完整')
            nodes=[]
            for n in db.execute('SELECT n.node_id,n.line_id,n.block_id,s.state_id,s.knowledge_at FROM line_nodes n JOIN line_node_states s ON s.node_id=n.node_id WHERE EXISTS (SELECT 1 FROM line_node_memberships m WHERE m.node_id=n.node_id AND m.retired_at IS NULL) ORDER BY s.knowledge_at'):
                if n['state_id'] in scoped:
                    memory=scoped[n['state_id']]
                    nodes.append(dict(id=n['node_id'],line_id=n['line_id'],block_id=n['block_id'],memory_id=n['state_id'],known_at=n['knowledge_at'],text=memory['content'],lifecycle=memory['lifecycle'],evidence_complete=n['state_id'] in valid))
            nodes=list({n['id']:n for n in nodes}.values()); ids={n['id'] for n in nodes}
            edges=[dict(r) for r in db.execute('SELECT e.line_id,e.parent_node_id,e.child_node_id,e.kind FROM line_edges e WHERE EXISTS (SELECT 1 FROM line_edge_revisions r WHERE r.line_id=e.line_id AND r.parent_node_id=e.parent_node_id AND r.child_node_id=e.child_node_id AND r.retired_at IS NULL)')
                   if r['parent_node_id'] in ids and r['child_node_id'] in ids]
        tense=[];settled=[]
        if (root/'tense.sqlite').is_file():
            with closing(self.connect(str((root/'tense.sqlite').resolve()))) as db:
                tense=[dict(r) for r in db.execute('SELECT memory_id,happened,known_at FROM said') if r['memory_id'] in valid]
                settled=[dict(r) for r in db.execute('SELECT memory_id,settled_at,by_memory_id FROM settled') if r['memory_id'] in valid and r['by_memory_id'] in valid]
        return dict(available=True,lines=sorted({n['line_id'] for n in nodes}),nodes=nodes,edges=edges,tense=tense,settled=settled)

    def products(self, params):
        valid=set()
        for memory in self.memories().values():
            try: self.item(memory);valid.add(memory['memory_id'])
            except (ValueError,KeyError): pass
        result={}
        with closing(self.connect('memory.sqlite')) as db:
            tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            for table in ['memory_threads','memory_attention','semantic_relations']:
                if table not in tables: result[table]=[]; continue
                if table=='semantic_relations':
                    result[table]=[dict(r) for r in db.execute('SELECT * FROM semantic_relations') if r['from_memory_id'] in valid and r['to_memory_id'] in valid]
                else:
                    rows=[json.loads(r[0]) for r in db.execute('SELECT payload FROM '+table)]
                    result[table]=[r for r in rows if ((r.get('scope',{}).get('user_id')==self.user_id and set(r.get('origin_memory_ids',[])+r.get('current_support_ids',[])) <= valid) if table=='memory_threads' else r.get('memory_id') in valid)]
        return result
