class Lens:
    """A lens reads the corpus and emits one JSON-serialisable view.
    Vocabularies, rules and prompts come from `config` (a lens config file), never hardcoded."""
    name = "base"
    title = ""
    def __init__(self, config, ctx):
        self.config, self.ctx = config, ctx
    def build(self, docs):
        raise NotImplementedError
