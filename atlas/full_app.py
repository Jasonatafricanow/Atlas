"""Original Atlas composition: archive lenses, MR-Mem runtime, sealed folio."""
import secrets
from .archive import Archive
from .folio_store import FolioStore, digest
from .backends.mrmem_full import MrMemFull


class FullApp:
    def __init__(self, archive_file, *, data_dir=None, user_id=None, service=None,
                 folio_file=None, state_dir=None, runtime_writes=False):
        self.archive=Archive(archive_file)
        if not self.archive.verify()['valid']: raise ValueError('archive integrity failed')
        self.native=MrMemFull(data_dir,user_id,service) if user_id else None
        self.service=service; self.user_id=user_id
        self.folio=FolioStore(folio_file,state_dir) if folio_file and state_dir else None
        self.token=secrets.token_urlsafe(32)
        self.runtime_writes=runtime_writes

    def get(self, route, params):
        if route=='archive/data': return self.archive.projection(params.get('sensitive')=='1')
        if route=='archive/verify': return self.archive.verify()
        if route=='archive/evidence': return self.archive.evidence(params['id'],params.get('sensitive')=='1')
        if route=='runtime/capabilities':
            return dict(storage=self.native is not None,service=self.service is not None,
                        mutations=self.runtime_writes and self.service is not None,folio=self.folio is not None,
                        token=self.token,source_contract='MR-Mem bb0d296')
        if route=='runtime/health':
            return self.service.call('health') if self.service else dict(status='disconnected')
        if route=='folio':
            if not self.folio: raise KeyError('folio not configured')
            doc=self.folio.read()
            return dict(doc=doc,revision=digest(doc),scope=digest(str(self.folio.seed.resolve()))[:20],token=self.token)
        if route.startswith('runtime/'):
            if not self.native: raise KeyError('native store not configured')
            methods={'catalog':self.native.catalog,'detail':self.native.detail,'segments':self.native.overview,
                     'graph':self.native.graph,'products':self.native.products,'history':self.native.history,
                     'sources':self.native.sources,'raw-evidence':self.native.raw_evidence,
                     'evidence':self.native.evidence,'search':self.native.search}
            return methods[route[8:]](params)
        raise KeyError('unknown full-app route')

    def post(self, route, payload):
        if route=='folio':
            if not self.folio: raise KeyError('folio unavailable')
            return dict(revision=self.folio.save(payload['doc'],payload['revision']))
        if not self.runtime_writes or not self.service:
            raise PermissionError('runtime mutations disabled')
        if route=='runtime/add':
            # The browser cannot switch the configured user scope.
            return self.service.call('add',dict(payload,user_id=self.user_id))
        if route=='runtime/flush':
            # Upstream endpoint is instance-wide, not scoped; explicit acknowledgement required.
            if payload.get('scope')!='all_users': raise ValueError('flush affects all pending users')
            return self.service.call('admin/flush',{})
        raise KeyError('unknown write route')
