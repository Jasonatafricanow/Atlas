"""Import preserved legacy sources and existing insight projections without model calls.

Requires the existing MR-Mem package on PYTHONPATH; never overwrites a dataset.
No Line, Thread, stance, entity or relation is inferred during import.
"""
import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def run(archive_file, destination, user_id):
    from atlas.archive import Archive
    from mr_mem import MemoryCore
    from mr_mem.memory.contracts import SemanticMemoryCandidate
    from mr_mem_aml.source_store import AmlSourceStore, user_scope
    archive=Archive(archive_file)
    if not archive.verify()['valid']: raise ValueError('legacy chain invalid')
    destination=Path(destination)
    if destination.exists(): raise ValueError('destination already exists; refusing overwrite')
    data=archive.read(); rows=[r for r in data['quotes'] if not r.get('s')]
    source_hash=hashlib.sha256(Path(archive_file).read_bytes()).hexdigest()
    request_id='legacy-'+source_hash[:20]
    messages=[]
    for row in rows:
        stamp=row['date']+'T'+(row.get('tm') or '00:00')+':00+08:00'
        # Legacy source explicitly documents Beijing wall-clock timestamps.
        messages.append(dict(role='user',content=archive.text(row),timestamp=stamp))
    destination.mkdir(parents=True)
    source=AmlSourceStore(destination/'aml_source.sqlite')
    core=MemoryCore(destination/'memory.sqlite')
    imported=0; skipped=0
    try:
        now=datetime.now(UTC)
        source._conn.execute('CREATE TABLE atlas_source_precision(record_id TEXT PRIMARY KEY, source_date TEXT NOT NULL, precision TEXT NOT NULL, legacy_id INTEGER NOT NULL, session_display_name TEXT NOT NULL, source_kind TEXT NOT NULL)')
        source._conn.commit()
        by_id={}
        for i,row in enumerate(rows):
            # One request per preserved artifact keeps source order and original session grouping.
            rid=request_id+':'+str(row['id'])
            session='legacy-session:'+hashlib.sha256(row['chat'].encode()).hexdigest()[:24]
            source.put_request(dict(request_id=rid,user_id=user_id,session_id=session,messages=[messages[i]]),received_at=now)
            record=rid+':0'
            precision='minute' if row.get('tm') else 'day'
            source._conn.execute('INSERT INTO atlas_source_precision VALUES(?,?,?,?,?,?)',(record,row['date'],precision,row['id'],row['chat'],'legacy_quote_extract'))
            if precision=='day': source._conn.execute('UPDATE messages SET time_given=0 WHERE record_id=?',(record,))
            source._conn.commit()
            by_id[row['id']]=source.request_messages(rid)[0]
            source.set_done(rid)
        class Clock:
            def now(self): return now
        admission=core.semantic_admission(sources=source,clock=Clock(),origin_runtime_id='atlas-legacy-import')
        for index,card in enumerate(data.get('ins',{}).get('cards',[])):
            ids=list(dict.fromkeys(card.get('ids',[])))
            if not ids or any(i not in by_id for i in ids): skipped+=1;continue
            content='历史综合（旧版投影，未重新编译）：'+card['title']+'。'+card.get('body','')
            admission.admit(SemanticMemoryCandidate(semantic_id='legacy-insight:'+source_hash[:20]+':'+str(index),
                scope=user_scope(user_id),content=content,source_refs=tuple(by_id[i].ref for i in ids),
                compiler_version='atlas-legacy-preserved-v1',attributes=(('kind','legacy_projection'),('source_archive',source_hash),
                ('legacy_source',card.get('src') or 'historical compilation'),('inference',card.get('infer') or 'historical model projection'))))
            imported+=1

    finally:
        core.close();source.close()
    report=dict(source_archive_sha256=source_hash,user_id=user_id,raw_sources=len(rows),sessions=len({r['chat'] for r in rows}),source_kind='legacy_quote_extract',
                excluded_sensitive=len(data['quotes'])-len(rows),preserved_projections=imported,
                skipped_projections=skipped,model_calls=0,inferred_lines=0,inferred_threads=0,
                original_sources_modified=False,known_at_semantics='native import commit time; historical compile time is unknown')
    (destination/'import-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--archive-file',required=True)
    parser.add_argument('--out-dir',required=True)
    parser.add_argument('--user-id',required=True)
    args=parser.parse_args()
    print(json.dumps(run(args.archive_file,args.out_dir,args.user_id),ensure_ascii=True))
