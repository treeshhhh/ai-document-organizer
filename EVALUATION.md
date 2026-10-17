# Measured retrieval evaluation

Executed October 17, 2026 on macOS arm64, Python 3.12.14, NumPy 2.3.5, Sentence Transformers 6.1.0, CPU. Model: `sentence-transformers/all-MiniLM-L6-v2`, revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`; 384-dimensional normalized vectors. No model training or tuning was performed.

## Method

Eight author-written synthetic documents are in `samples/`. Eight author-written paraphrased natural-language queries each have one declared relevant document. `evaluate.py` creates a temporary SQLite library, ingests the real files through the same extraction/indexing path as the app, and ranks the same query with keyword, semantic, and hybrid modes. Evaluation does not touch a user's library and uses the actual downloaded model, not the unit-test embedding fixture. Duplicate hashing/caching and category/summary suggestions are normal application behavior; no query-specific overrides exist.

Keyword baseline: query-term coverage/literal substring matching across metadata and content, no stemming/BM25. Semantic: maximum chunk cosine. Hybrid: fixed 0.7 nonnegative cosine + 0.3 lexical score. Relevance was labeled by the author; no independent annotators or hidden test set.

| Mode | Recall@1 | Recall@3 | Mean reciprocal rank |
|---|---:|---:|---:|
| Keyword | 4/8 (0.50) | 4/8 (0.50) | 0.50 |
| Semantic | 8/8 (1.00) | 8/8 (1.00) | 1.00 |
| Hybrid | 8/8 (1.00) | 8/8 (1.00) | 1.00 |

Recall@k is the fraction of queries whose relevant document appears in the first k results. Reciprocal rank is 1/rank, or zero when absent; MRR averages it. Missing lexical matches can yield no relevant result. Results demonstrate that semantic retrieval helped these tested paraphrases, not that it always beats keyword search.

Actual measured ingestion + 24 searches: **0.591 seconds**, excluding model load, on this execution environment. This is one small-corpus observation, not a latency guarantee or comparative benchmark. The JSON contains full precision and environment information.

## Reproduce

```sh
python setup_model.py
python evaluate.py
```

Inspect `results/evaluation.json` for every query, relevant filename, top result, rank and environment. The run uses a temporary directory and writes only the evaluation report. The normal application should be stopped if you are changing/deleting its model files; evaluating an existing model does not modify the library.

## Limits

Tiny, deliberately understandable English corpus; clear single-topic documents; author-written queries/labels; one model revision and one run; no confidence intervals, independent relevance judgments, adversarial documents, scanned PDFs, multilingual coverage, or scalability study. All examples are synthetic and the model is pretrained on broad external corpora. This is a correctness/behavior demonstration, not a novel or general retrieval benchmark. Category classification was not evaluated as a trained classifier and its strength is explicitly not calibrated.
