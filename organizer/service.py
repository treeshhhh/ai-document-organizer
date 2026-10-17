import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import threading
import uuid
import numpy as np
from .chunking import chunk_text
from .extract import extract_isolated, safe_name, DocumentError
from .metadata import suggest, words, STOP
from .store import Store
from .embedding import MODEL_ID


class Organizer:
    def __init__(self, root: Path, embedder):
        self.store = Store(root)
        self.embedder = embedder
        self.lock = threading.RLock()
        info = root / 'model' / 'download-info.json'
        revision = json.loads(info.read_text()).get('revision', 'local') if info.exists() else 'local'
        self.model_key = MODEL_ID + ':' + revision + ':normalized-v1'

    def _key(self, chunk: str) -> str:
        return hashlib.sha256((self.model_key + '\0' + chunk).encode()).hexdigest()

    def cache(self, chunks: list[str]):
        keys = [self._key(c) for c in chunks]
        if not self.embedder.available:
            return keys
        with self.store.connect() as db:
            missing = {key: text for key, text in zip(keys, chunks) if db.execute('SELECT 1 FROM embeddings WHERE cache_key=?', (key,)).fetchone() is None}
            if missing:
                vectors = self.embedder.encode(list(missing.values()))
                db.executemany('INSERT OR IGNORE INTO embeddings(cache_key,dimension,vector) VALUES(?,?,?)',
                               [(key, len(v), v.astype('<f4').tobytes()) for key, v in zip(missing, vectors)])
        return keys

    def ingest(self, name: str, data: bytes):
        safe_name(name)
        digest = hashlib.sha256(data).hexdigest()
        with self.lock:
            with self.store.connect() as db:
                duplicate = db.execute('SELECT id FROM documents WHERE sha256=?', (digest,)).fetchone()
                count = db.execute('SELECT count(*) FROM documents').fetchone()[0]
            if duplicate:
                return {'document': self.store.get(duplicate[0], False), 'duplicate': True}
            if count >= 500:
                raise DocumentError('This local edition supports 500 documents including Trash.')
            text, warnings = extract_isolated(name, data)
            chunks = chunk_text(text)
            suggestions = suggest(text, name)
            keys = self.cache(chunks)
            if not self.embedder.available:
                warnings.append('Keyword-only indexing; run Rebuild missing embeddings after installing the model.')
            identity = uuid.uuid4().hex
            stored = identity + Path(name).suffix.lower()
            path = self.store.root / 'files' / stored
            path.write_bytes(data)
            try:
                with self.store.connect() as db:
                    db.execute('INSERT INTO documents(id,filename,stored_name,sha256,text,title,category,tags,summary,suggestions,warnings,created) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                               (identity, name, stored, digest, text, suggestions['title'], suggestions['category'], json.dumps(suggestions['keywords']), suggestions['summary'], json.dumps(suggestions), json.dumps(warnings), datetime.now(timezone.utc).isoformat()))
                    db.executemany('INSERT INTO chunks(document_id,ordinal,text,cache_key) VALUES(?,?,?,?)',
                                   [(identity, i, chunk, key) for i, (chunk, key) in enumerate(zip(chunks, keys))])
            except Exception:
                path.unlink(missing_ok=True)
                raise
            return {'document': self.store.get(identity, False), 'duplicate': False}

    def reindex(self):
        if not self.embedder.available:
            raise ValueError(self.embedder.reason)
        with self.lock:
            with self.store.connect() as db:
                chunks = [dict(r) for r in db.execute('SELECT c.* FROM chunks c JOIN documents d ON c.document_id=d.id WHERE d.deleted=0')]
            texts = [c['text'] for c in chunks]
            keys = self.cache(texts)
            with self.store.connect() as db:
                db.executemany('UPDATE chunks SET cache_key=? WHERE document_id=? AND ordinal=?',
                               [(key, c['document_id'], c['ordinal']) for c, key in zip(chunks, keys)])
                for row in db.execute('SELECT id,warnings FROM documents WHERE deleted=0').fetchall():
                    warnings = [w for w in json.loads(row['warnings']) if not w.startswith('Keyword-only indexing;')]
                    db.execute('UPDATE documents SET warnings=? WHERE id=?', (json.dumps(warnings), row['id']))
            return {'chunks_checked': len(chunks), 'message': 'Missing vectors indexed; existing embeddings were reused.'}

    def search(self, query: str, mode='hybrid', category='', collection='', deleted=False):
        if mode not in ('keyword', 'semantic', 'hybrid') or len(query) > 500:
            raise ValueError('Choose keyword, semantic, or hybrid mode; query limit is 500 characters.')
        docs = self.store.list(deleted, category, collection)
        if not query.strip():
            return {'results': docs, 'mode_used': 'library', 'notice': ''}
        used = mode
        notice = ''
        if mode != 'keyword' and not self.embedder.available:
            used = 'keyword'; notice = self.embedder.reason + ' Keyword fallback used.'
        tokens = list(dict.fromkeys(w for w in words(query) if w not in STOP))
        vector = self.embedder.encode([query])[0] if used != 'keyword' else None
        with self.store.connect() as db:
            rows = db.execute('SELECT c.document_id,c.text,c.cache_key,e.vector,e.dimension FROM chunks c LEFT JOIN embeddings e ON c.cache_key=e.cache_key').fetchall()
        groups = {}
        for row in rows:
            groups.setdefault(row['document_id'], []).append(row)
        results = []
        unindexed = 0
        for doc in docs:
            chunks = groups.get(doc['id'], [])
            metadata = ' '.join([doc['filename'], doc['title'], doc['category'], *doc['tags']]).lower()
            content = ' '.join(c['text'] for c in chunks).lower()
            lexical = sum(1 for t in tokens if t in metadata or t in content) / max(1, len(tokens))
            # Literal filename/title/content substring handles filenames and short tokens too.
            literal = query.lower().strip() in metadata or query.lower().strip() in content
            lexical = max(lexical, float(literal))
            best, cosine, indexed = None, -1., False
            if vector is not None:
                for c in chunks:
                    if c['cache_key'] == self._key(c['text']) and c['vector'] is not None and c['dimension'] == len(vector):
                        similarity = float(np.dot(vector, np.frombuffer(c['vector'], dtype='<f4')))
                        if similarity > cosine:
                            best, cosine = c, similarity
                        indexed = True
            if vector is not None and not indexed:
                unindexed += 1
            if best is None and chunks:
                best = max(chunks, key=lambda c: sum(c['text'].lower().count(t) for t in tokens))
            if used == 'keyword':
                if not lexical:
                    continue
                score = lexical
            elif used == 'semantic':
                if not indexed:
                    continue
                score = cosine
            else:
                if not indexed and not lexical:
                    continue
                score = .7 * max(0., cosine) + .3 * lexical
            results.append({**doc, 'score': round(score, 5), 'cosine_similarity': round(cosine, 5) if indexed else None,
                            'keyword_score': round(lexical, 5), 'excerpt': best['text'][:500] if best else '', 'indexed': indexed})
        results.sort(key=lambda r: (-r['score'], r['filename']))
        if vector is not None and unindexed:
            notice = 'Some documents lack embeddings. Use Rebuild missing embeddings.'
        return {'results': results[:100], 'mode_used': used, 'notice': notice}
