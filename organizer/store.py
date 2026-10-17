"""SQLite metadata, chunk vectors and a persistent content-addressed cache."""
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3


class Store:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / 'files').mkdir(exist_ok=True)
        self.path = self.root / 'index.sqlite3'
        with self.connect() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS collections(id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL);
            CREATE TABLE IF NOT EXISTS documents(
              id TEXT PRIMARY KEY, filename TEXT NOT NULL, stored_name TEXT NOT NULL,
              sha256 TEXT UNIQUE NOT NULL, text TEXT NOT NULL, title TEXT NOT NULL,
              category TEXT NOT NULL, tags TEXT NOT NULL, summary TEXT NOT NULL,
              suggestions TEXT NOT NULL, warnings TEXT NOT NULL, created TEXT NOT NULL,
              collection_id INTEGER REFERENCES collections(id), deleted INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS chunks(
              document_id TEXT REFERENCES documents(id) ON DELETE CASCADE, ordinal INTEGER,
              text TEXT NOT NULL, cache_key TEXT NOT NULL, PRIMARY KEY(document_id,ordinal));
            CREATE TABLE IF NOT EXISTS embeddings(
              cache_key TEXT PRIMARY KEY, dimension INTEGER NOT NULL, vector BLOB NOT NULL);
            CREATE INDEX IF NOT EXISTS chunk_cache ON chunks(cache_key);
            ''')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def decode(row, full=False):
        data = dict(row)
        for key in ('tags', 'suggestions', 'warnings'):
            data[key] = json.loads(data[key])
        data['deleted'] = bool(data['deleted'])
        if not full:
            data.pop('text', None)
            data.pop('stored_name', None)
        return data

    def get(self, identity: str, full=True):
        with self.connect() as db:
            row = db.execute('SELECT d.*, c.name collection FROM documents d LEFT JOIN collections c ON c.id=d.collection_id WHERE d.id=?', (identity,)).fetchone()
        if row is None:
            raise KeyError('Document not found.')
        return self.decode(row, full)

    def list(self, deleted=False, category='', collection=''):
        sql = 'SELECT d.*, c.name collection FROM documents d LEFT JOIN collections c ON c.id=d.collection_id WHERE d.deleted=?'
        params = [int(deleted)]
        if category:
            sql += ' AND d.category=?'; params.append(category)
        if collection:
            sql += ' AND c.name=?'; params.append(collection)
        with self.connect() as db:
            rows = db.execute(sql + ' ORDER BY d.created DESC', params).fetchall()
        return [self.decode(row, False) for row in rows]

    def collections(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute('SELECT id,name FROM collections ORDER BY name')]

    def edit(self, identity: str, values: dict):
        allowed = {'title', 'category', 'summary', 'tags', 'collection'}
        if not isinstance(values, dict) or not values or not set(values) <= allowed:
            raise ValueError('Update only title, category, summary, tags, or collection.')
        limits = {'title': 150, 'category': 60, 'summary': 1500, 'collection': 80}
        for key, value in values.items():
            if key == 'tags':
                if not isinstance(value, list) or len(value) > 20 or any(not isinstance(t, str) or not 1 <= len(t.strip()) <= 40 for t in value):
                    raise ValueError('Use at most 20 nonempty tags, each up to 40 characters.')
            elif not isinstance(value, str) or len(value) > limits[key] or (key in ('title', 'category') and not value.strip()):
                raise ValueError('Invalid metadata value: ' + key)
        with self.connect() as db:
            if not db.execute('SELECT id FROM documents WHERE id=?', (identity,)).fetchone():
                raise KeyError('Document not found.')
            for key, value in values.items():
                if key == 'collection':
                    name = value.strip()
                    if name:
                        db.execute('INSERT OR IGNORE INTO collections(name) VALUES(?)', (name,))
                        collection_id = db.execute('SELECT id FROM collections WHERE name=?', (name,)).fetchone()[0]
                    else:
                        collection_id = None
                    db.execute('UPDATE documents SET collection_id=? WHERE id=?', (collection_id, identity))
                else:
                    # Column names are from the explicit allowlist above; values are bound.
                    db.execute(f'UPDATE documents SET {key}=? WHERE id=?', (json.dumps(value) if key == 'tags' else value.strip(), identity))
        return self.get(identity, False)

    def trash(self, identity: str, deleted: bool):
        with self.connect() as db:
            changed = db.execute('UPDATE documents SET deleted=? WHERE id=?', (int(deleted), identity)).rowcount
            if not changed:
                raise KeyError('Document not found.')
