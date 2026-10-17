#!/usr/bin/env python3
"""Small explicit paraphrase retrieval evaluation; no private documents."""
import argparse
import json
from pathlib import Path
import platform
import tempfile
import time
import numpy as np
from organizer.embedding import Embedder, MODEL_ID
from organizer.service import Organizer

QUERIES = [
    ('How can we keep sensitive information confidential?', 'security.md'),
    ('What helps a car motor avoid breaking down?', 'automobile.md'),
    ('How do I settle an outstanding bill?', 'billing.txt'),
    ('What makes a loaf expand before it goes in the oven?', 'bread.md'),
    ('How do I get ready to apply for a summer job?', 'career.md'),
    ('What habits improve the health of the heart?', 'cardiac.txt'),
    ('How can I raise healthy vegetables in my backyard?', 'garden.txt'),
    ('How do scientists investigate objects in outer space?', 'astronomy.txt'),
]

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--model-dir', type=Path, default=Path('data/model'))
    args = parser.parse_args()
    embedder = Embedder(args.model_dir)
    if not embedder.available:
        raise SystemExit(embedder.reason)
    started = time.perf_counter()
    with tempfile.TemporaryDirectory() as tmp:
        app = Organizer(Path(tmp), embedder)
        for path in sorted(Path('samples').glob('*')):
            app.ingest(path.name, path.read_bytes())
        rows = []
        for query, relevant in QUERIES:
            row = {'query': query, 'relevant_filename': relevant}
            for mode in ('keyword', 'semantic', 'hybrid'):
                results = app.search(query, mode)['results']
                rank = next((i + 1 for i, d in enumerate(results) if d['filename'] == relevant), None)
                row[mode] = {'rank': rank, 'top_filename': results[0]['filename'] if results else None}
            rows.append(row)
    metrics = {}
    for mode in ('keyword', 'semantic', 'hybrid'):
        ranks = [r[mode]['rank'] for r in rows]
        metrics[mode] = {'recall_at_1': sum(r == 1 for r in ranks) / len(rows),
                         'recall_at_3': sum(r is not None and r <= 3 for r in ranks) / len(rows),
                         'mrr': sum(1 / r if r else 0 for r in ranks) / len(rows)}
    info = args.model_dir / 'download-info.json'
    report = {'documents': 8, 'queries': len(rows), 'model': MODEL_ID,
              'model_revision': json.loads(info.read_text())['revision'] if info.exists() else 'local',
              'embedding_dimension': embedder.dimension, 'metrics': metrics, 'queries_details': rows,
              'elapsed_seconds_excluding_model_load': time.perf_counter() - started,
              'environment': {'python': platform.python_version(), 'numpy': np.__version__},
              'limitations': 'Small author-written synthetic corpus and queries, one relevant document per query; not a general benchmark. No training or tuning against a hidden test set.'}
    Path('results').mkdir(exist_ok=True)
    Path('results/evaluation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'metrics': metrics, 'seconds': report['elapsed_seconds_excluding_model_load']}, indent=2))
