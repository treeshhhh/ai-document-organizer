# Interview preparation

1. **What is actually AI here?** Real local MiniLM embeddings support semantic matching. Classification/title/summary suggestions are deterministic rules and extraction; no custom model was trained.
2. **Why cosine?** Normalization makes vector direction comparable despite magnitude. For unit vectors a dot product gives cosine. A high cosine is not a calibrated probability.
3. **Why overlap chunks?** It keeps boundary-spanning context visible. The cost is duplicate text/extra vectors. Word windows do not guarantee a strict token budget.
4. **How is a document ranked?** Its highest-scoring chunk supplies its semantic score and excerpt. This is simple, but long documents get more chances to match.
5. **How does hybrid search work?** 70% nonnegative cosine plus 30% lexical coverage. The weights are transparent and untuned. It can help exact identifiers but needs broader evaluation.
6. **What is cached?** Document chunks' normalized float32 vectors, keyed by chunk content and model revision. Query embeddings are computed per request. Exact file hashes prevent duplicate uploads.
7. **How do edits affect the index?** Metadata edits immediately affect keyword search; embeddings represent extracted text. New uploaded contents create new documents/chunk keys. Explicit rebuild fills missing vectors after fallback/model changes.
8. **What is the classifier confidence?** A heuristic strength from rule coverage and winner separation. It is not a probability and can be wrong; evidence terms and original suggestions remain visible.
9. **How did you test semantics?** A real-model synonym check and an eight-document/eight-query paraphrase demonstration. Unit/API tests also use a deterministic fixture for speed; that fixture is not presented as real semantic evidence.
10. **Why not a vector database?** This bounded library fits SQLite plus exact NumPy scoring. Exhaustive O(Cd) ranking does not scale to millions of chunks; an ANN index would be a later tradeoff.
11. **How are uploads handled safely?** Byte/type/signature/expanded-size limits, isolated parsing with time/resource bounds, UUID storage, fixed download routes, plain-text rendering, and bound SQL. They reduce risk but do not make this a hardened upload service.
12. **Does local mean fully private?** No external inference transmission; installation downloads packages/model. Data at rest is not encrypted, Trash retains originals, and exports can contain sensitive metadata. Operating-system access still matters.
13. **What would improve scientific rigor?** A larger independently labeled corpus, held-out queries, multiple domains/languages, exact-match baseline alternatives, latency/memory profiling, and error analysis. Do not call this small demo a general accuracy benchmark.

Demo: upload a synthetic note, inspect original suggestions/evidence and extracted text, correct its category, create a collection, issue a paraphrased query, show the matching chunk, then move the note to Trash and restore it. State limits and assistance honestly.
