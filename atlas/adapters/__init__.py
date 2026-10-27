class Adapter:
    """Turn some raw export into atlas.schema.Document objects.
    Source-specific adapters (e.g. a chat-app export) belong in PRIVATE packages."""
    name = "base"
    def __init__(self, **options):
        self.options = options
    def read(self):
        raise NotImplementedError
