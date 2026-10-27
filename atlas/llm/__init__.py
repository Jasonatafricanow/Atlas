"""Pluggable LLM provider abstraction + optional pre-send processors.
The core ships only NullProvider; real providers (agy, grok, volc DS ...) and
the redaction/sensitivity pre-processor are configured per deployment."""
class Provider:
    name = "base"
    def complete(self, prompt: str, **kw) -> str:
        raise NotImplementedError

class NullProvider(Provider):
    """Offline default: never sends anything anywhere."""
    name = "null"
    def complete(self, prompt, **kw):
        return ""

class PreSend:
    """Hook run on every prompt before it leaves the machine (e.g. redaction,
    sensitivity veto). Return None to block sending."""
    def __call__(self, prompt: str):
        return prompt

class Pipeline:
    def __init__(self, provider: Provider, presend=()):
        self.provider, self.presend = provider, list(presend)
    def complete(self, prompt, **kw):
        for h in self.presend:
            prompt = h(prompt)
            if prompt is None:
                return None
        return self.provider.complete(prompt, **kw)
