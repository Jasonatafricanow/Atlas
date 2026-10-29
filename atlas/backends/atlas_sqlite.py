"""ATLAS adapter preserving the existing read-model projections and errors."""
from ..web_data import ReadModel
from .digests import DigestSource


class AtlasSqliteBackend:
    def __init__(self, data_dir, sensitive=False, digest_dir=None):
        self.model = ReadModel(data_dir, sensitive)
        self.digest_source = DigestSource(digest_dir, self.model) if digest_dir else None

    def digests(self):
        return self.digest_source

    def toc(self, params):
        return self.model.get("toc", params)

    def home(self, params):
        data = self.model.get("home", params)
        if self.digest_source:
            data["home_views"] = self.digest_source.home_views(100)
        return data

    def lines(self, params):
        return self.model.get("lines", params)

    def line(self, params):
        data = self.model.get("line", params)
        if self.digest_source:
            ids = [l["line_id"] for l in data["line"]["lines"]]
            if params.get("id") in ids:
                ids = [params["id"]]
            digests = []
            for lid in ids:
                digest = self.digest_source.for_line(lid)
                if digest and digest not in digests:
                    digests.append(digest)
            data.update(digest=digests[0] if digests else None, digests=digests)
        return data

    def entities(self, params):
        return self.model.get("entities", params)

    def entity(self, params):
        data = self.model.get("entity", params)
        if self.digest_source:
            data["digest"] = self.digest_source.for_entity(data["node"]["node_id"])
        return data

    def search(self, params):
        return self.model.get("search", params)

    def evidence(self, params):
        if params.get("kind") in ("digest_line", "digest_entity"):
            if not self.digest_source:
                raise KeyError
            return self.digest_source.evidence(params)
        return self.model.get("evidence", params)
