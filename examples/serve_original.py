"""Run the original UI with the real local MR-Mem host (optional paired source).

No provider/model calls in preservation mode. Use --runtime-config and
--runtime-writes explicitly to enable a separately configured production compiler.
"""
import argparse
from dataclasses import replace
import json
import os
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import secrets
import sys
import threading


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--archive-file',type=Path,required=True)
    parser.add_argument('--folio-file',type=Path,required=True)
    parser.add_argument('--data-dir',type=Path,required=True)
    parser.add_argument('--state-dir',type=Path,required=True)
    parser.add_argument('--user-id',required=True)
    parser.add_argument('--port',type=int,default=8794)
    parser.add_argument('--native-port',type=int,default=0)
    parser.add_argument('--ready-file',type=Path)
    parser.add_argument('--runtime-config',type=Path)
    parser.add_argument('--runtime-writes',action='store_true')
    args=parser.parse_args()
    if args.runtime_writes and not args.runtime_config:
        parser.error('--runtime-writes requires an explicit compiler configuration')
    if not (args.data_dir/'memory.sqlite').is_file():
        parser.error('an existing native store is required; import separately first')
    from mr_mem_aml.config import RuntimeConfig
    from mr_mem_aml.runtime import MemoryRuntime
    from mr_mem_aml.server import RuntimeHost, build_server
    from atlas.server import create_server
    token_env='ATLAS_LOCAL_RUNTIME_TOKEN'
    os.environ[token_env]=secrets.token_urlsafe(32)
    if args.runtime_config:
        # Preserve the chosen native read/compile policies. Provider calls may be
        # triggered by explicit searches if the supplied configuration enables them.
        cfg=replace(RuntimeConfig.load(args.runtime_config),data_dir=args.data_dir,
                    host='127.0.0.1',port=args.native_port,auth_token_env=token_env)
    else:
        cfg=RuntimeConfig(data_dir=args.data_dir,host='127.0.0.1',port=args.native_port,
            auth_token_env=token_env,compiler={'type':'command','argv':[sys.executable,'-c',
                "raise RuntimeError('Preservation mode has no compiler configured')"]},
            path_a_engine='tree',placement='points',raw_base=True,
            compile_before_search=False,embedding=None,hyde='off',decision=None,
            line_read={'raw_fill':0,'hit_anchors':True})
    host=RuntimeHost(lambda:MemoryRuntime(cfg))
    native=build_server(cfg,host)
    worker=threading.Thread(target=native.serve_forever,daemon=True);worker.start()
    try:
        ui=create_server(args.data_dir,port=args.port,mrmem_user=args.user_id,
            mrmem_url=f'http://127.0.0.1:{native.server_port}',mrmem_token_env=token_env,
            archive_file=args.archive_file,folio_file=args.folio_file,state_dir=args.state_dir,
            runtime_writes=args.runtime_writes)
        ready=dict(ui=f'http://127.0.0.1:{ui.server_port}',native=f'http://127.0.0.1:{native.server_port}',
                   mode='configured' if args.runtime_config else 'preserved-no-model',
                   mutations=args.runtime_writes)
        if args.ready_file:
            args.ready_file.parent.mkdir(parents=True,exist_ok=True)
            args.ready_file.write_text(json.dumps(ready),encoding='utf-8')
        print(json.dumps(ready),flush=True)
        try: ui.serve_forever()
        except KeyboardInterrupt: pass
        finally: ui.server_close()
    finally:
        native.shutdown();native.server_close();host.close();worker.join()


if __name__=='__main__': main()
