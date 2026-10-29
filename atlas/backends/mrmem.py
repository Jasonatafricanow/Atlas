"""Read-only contract skeleton. No MR-Mem imports, connections or configuration."""


class MrMemBackend:
    def digests(self):
        """Unavailable until docs/for_mrmem_requirements.md sections 9–10 land."""
        return None

    def toc(self, params):
        """Read visible Line identities and entity names for navigation."""
        raise NotImplementedError

    def home(self, params):
        """Read correction-aware Lines and propositions for four home questions."""
        raise NotImplementedError

    def lines(self, params):
        """Read native Lines with source-backed points and annotation provenance."""
        raise NotImplementedError

    def line(self, params):
        """Read one Line, its topic view, stance dimension and result references."""
        raise NotImplementedError

    def entities(self, params):
        """Read visible entity identities without source message content."""
        raise NotImplementedError

    def entity(self, params):
        """Read an entity's aliases, relations and pointer-only mention backlinks."""
        raise NotImplementedError

    def search(self, params):
        """Search visible entity/Line/proposition metadata without corpus excerpts."""
        raise NotImplementedError

    def evidence(self, params):
        """Read and verify authorized message_paragraphs refs on drawer request."""
        raise NotImplementedError
