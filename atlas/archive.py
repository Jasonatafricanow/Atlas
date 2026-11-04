"""Explicit legacy archive reader. Historical projections keep their own identity."""
import base64
import copy
import hashlib
import json
from pathlib import Path


class Archive:
    def __init__(self, path):
        self.path = Path(path)

    def read(self):
        data = json.loads(self.path.read_text(encoding='utf-8'))
        if not isinstance(data.get('quotes'), list) or not isinstance(data.get('meta'), dict):
            raise ValueError('invalid archive contract')
        return data

    @staticmethod
    def text(row):
        return base64.b64decode(row['q']).decode('utf-8') if row.get('e') else row['q']

    def verify(self):
        previous = '0' * 64
        data = self.read()
        for index, row in enumerate(data['quotes']):
            current = hashlib.sha256((previous+'|'+row['date']+'|'+row['chat']+'|'+self.text(row)).encode()).hexdigest()
            if current != row['h']:
                return dict(valid=False, first_invalid=index, count=len(data['quotes']))
            previous = current
        return dict(valid=True, count=len(data['quotes']), head=previous)

    def projection(self, sensitive=False):
        data = copy.deepcopy(self.read())
        for index, row in enumerate(data['quotes']):
            if row['id'] != index:
                raise ValueError('archive quote identity drift')
            if row.get('s') and not sensitive:
                data['quotes'][index] = dict(id=index,q='',s=True,e=0,date='',chat='',dim='',c=[],hs=[],kw={},iv=0,h=row['h'])
            else:
                row['q'] = self.text(row)
                row['e'] = 0
        if not sensitive:
            data.pop('porS', None)
        return data

    def evidence(self, identifier, sensitive=False):
        data = self.read()
        index = int(identifier)
        if not 0 <= index < len(data['quotes']):
            raise KeyError('archive record missing')
        row = data['quotes'][index]
        if row.get('s') and not sensitive:
            raise KeyError('archive record hidden')
        if not self.verify()['valid']:
            raise ValueError('archive chain invalid')
        return dict(id=index,quote=self.text(row),date=row['date'],chat=row['chat'],fingerprint=row['h'],provenance='legacy_archive')
