"""ATLAS adapter preserving the existing read-model projections and errors."""
from ..web_data import ReadModel


class AtlasSqliteBackend:
    def __init__(self, data_dir, sensitive=False):
        self.model = ReadModel(data_dir, sensitive)

    def toc(self, params):
        return self.model.get("toc", params)

    def home(self, params):
        return self.model.get("home", params)

    def lines(self, params):
        return self.model.get("lines", params)

    def line(self, params):
        return self.model.get("line", params)

    def entities(self, params):
        return self.model.get("entities", params)

    def entity(self, params):
        return self.model.get("entity", params)

    def search(self, params):
        return self.model.get("search", params)

    def evidence(self, params):
        return self.model.get("evidence", params)
