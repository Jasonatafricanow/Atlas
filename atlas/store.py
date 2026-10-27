"""External corpus store: a SQLite file inside the user's data_dir (never in the repo)."""
import sqlite3, json, os
from .schema import Document

SCHEMA = """CREATE TABLE IF NOT EXISTS documents(
 id TEXT PRIMARY KEY, source TEXT, ts TEXT, text TEXT, author TEXT,
 channel TEXT, tags TEXT, meta TEXT);
CREATE INDEX IF NOT EXISTS idx_ts ON documents(ts);"""

class Store:
    def __init__(self, data_dir):
        os.makedirs(data_dir, exist_ok=True)
        self.db = sqlite3.connect(os.path.join(data_dir, "corpus.sqlite"))
        self.db.executescript(SCHEMA)

    def upsert(self, docs):
        n = 0
        for d in docs:
            self.db.execute("INSERT OR REPLACE INTO documents VALUES(?,?,?,?,?,?,?,?)",
                (d.id, d.source, d.ts, d.text, d.author, d.channel,
                 json.dumps(d.tags, ensure_ascii=False), json.dumps(d.meta, ensure_ascii=False)))
            n += 1
        self.db.commit()
        return n

    def all(self):
        for r in self.db.execute("SELECT id,source,ts,text,author,channel,tags,meta FROM documents ORDER BY ts"):
            yield Document(r[0], r[1], r[2], r[3], r[4], r[5], json.loads(r[6]), json.loads(r[7]))
