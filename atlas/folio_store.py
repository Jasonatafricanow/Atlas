"""Local annotation sidecar. Sealed originals are immutable; saves use CAS."""
import hashlib
import json
import os
import threading
from pathlib import Path


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class FolioStore:
    def __init__(self, seed, state_dir):
        self.seed = Path(seed)
        self.state = Path(state_dir) / ('folio-' + hashlib.sha256(str(self.seed.resolve()).encode()).hexdigest()[:20] + '.json')
        self.lock = threading.Lock()

    def read(self):
        return json.loads((self.state if self.state.exists() else self.seed).read_text(encoding='utf-8'))

    @staticmethod
    def validate(doc, previous):
        if not isinstance(doc,dict): raise ValueError('folio object required')
        entries = doc.get('entries')
        if not isinstance(entries, list) or len(entries) < len(previous['entries']):
            raise ValueError('sealed entries cannot be removed')
        trust=doc.get('trust', {})
        if not isinstance(trust,dict) or not isinstance(trust.get('aiMayWrite',{}),dict):
            raise ValueError('invalid trust settings')
        if trust.get('aiMayWrite', {}).get('original'):
            raise ValueError('original write authority cannot be granted')
        seen = set(); prev = 'GENESIS'
        for index, entry in enumerate(entries):
            if not isinstance(entry,dict): raise ValueError('entry object required')
            identifier = entry.get('id')
            if not isinstance(identifier, str) or identifier in seen:
                raise ValueError('duplicate entry identity')
            seen.add(identifier)
            if not isinstance(entry.get('versions'),list) or not entry['versions']:
                raise ValueError('sealed versions required')
            original = entry['versions'][0]
            if not isinstance(original,dict) or not isinstance(original.get('text'),str): raise ValueError('original text required')
            sha = hashlib.sha256(original['text'].encode()).hexdigest()
            chain = hashlib.sha256((prev+'\n'+sha+'\n'+identifier).encode()).hexdigest()
            if original['sha256'] != sha or entry['chain_prev'] != prev or entry['chain'] != chain:
                raise ValueError('sealed original chain invalid')
            if index < len(previous['entries']):
                old = previous['entries'][index]
                if identifier != old['id'] or entry['versions'][:len(old['versions'])] != old['versions']:
                    raise ValueError('sealed versions cannot be replaced or reordered')
            prev = chain

    def save(self, doc, revision):
        with self.lock:
            previous = self.read()
            if digest(previous) != revision:
                raise ValueError('folio revision conflict')
            self.validate(doc, previous)
            self.state.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.state.with_suffix('.tmp')
            temporary.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding='utf-8')
            os.replace(temporary, self.state)
            return digest(doc)
