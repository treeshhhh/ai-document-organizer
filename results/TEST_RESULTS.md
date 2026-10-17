# Verification — October 17, 2026

**READY TO PUBLISH** as a bounded local educational application. No GitHub repository was created or modified.

## Automated tests

Final command: `ORGANIZER_TEST_MODEL=/path/to/local/model python -m unittest discover -s tests -v`.

**17 test methods passed, zero failures, zero skips** in 6.639 seconds in the recorded environment. Raw output: `test-output.txt`. The first full pass also passed; a final pass added regression coverage for rebuilding previously missing vectors and removing stale fallback warnings.

Coverage includes text/Markdown extraction, a minimal DOCX archive, a text-bearing synthetic PDF, malformed/empty/oversized files, signature and path checks, DOCX entities/archive traversal, fixed parser subprocess, explainable category/metadata generation, overlapping chunks, duplicate/cache reuse, SQLite reopening, semantic/keyword/hybrid ordering using a clearly labeled deterministic fixture, missing-model fallback, reindex, metadata/collection edits, Trash/restore, upload/API end-to-end paths, original download, metadata export, unknown routes, write-size validation, and Host/Origin checks. A separate real MiniLM test verified shape `(3,384)`, unit norms, and synonym ordering. The fixture is not used to substantiate the semantic evaluation.

Non-fatal diagnostics: the installed Starlette version deprecates its httpx TestClient integration, and PyTorch prints a macOS process-redirection note. Tests still completed successfully. Hosted GitHub Actions is configured but has not run; Linux execution was not verified locally.

## Actual model evaluation

`evaluate.py` used the real pretrained model with eight synthetic documents and eight labeled paraphrased queries. Keyword Recall@1: **4/8**; semantic and hybrid: **8/8**. Full query/rank evidence is in `evaluation.json`; methodology/limits in `EVALUATION.md`. No training, private documents, paid services, or general accuracy claims.

## Browser smoke check

Using a real local Uvicorn/FastAPI server and actual cached model embeddings, opened the eight-document synthetic library. A semantic query, “What helps a car motor avoid breaking down?”, ranked `automobile.md` first (cosine approximately 0.343). Opened the result and verified extracted plain text, original category evidence, and editable fields. Entered “Portfolio demo” as a collection, saved it, and verified the library card and collection filter updated. Cleared the query and visually reviewed the populated library. Screenshot: `interface.png`.

This smoke check did not exercise browser drag/drop, every file-picker interaction, mobile breakpoints, or all browser engines. Upload, export, Trash/restore and original downloads were exercised in API tests rather than through every browser control. No real personal documents were used; the shipped package contains no populated library.

## Security/packaging review and limits

Reviewed allowed suffix/signature/UTF-8 validation, upload byte limits, bounded DOCX expansion, PDF limits, parser timeout/resource handling, SQLite bound values, edit allowlist, UUID storage, fixed routes, attachment-only originals, plain-text DOM rendering, runtime offline inference, and localhost/Origin checks. No virtual environments, downloaded models, caches, populated databases, real private documents, or credentials are included.

Parser subprocesses/resource limits are not a complete OS sandbox. Data is unencrypted; Trash retains originals/indexes. No OCR, private-cloud sync, permanent purge, authentication, or large-scale ANN search is provided. Package pins direct dependencies tested on Python 3.12.14/macOS arm64; transitive/platform variation is possible. Classification strength and retrieval scores are not calibrated probabilities. The small synthetic retrieval demonstration does not establish general performance.
