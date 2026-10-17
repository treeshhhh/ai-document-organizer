#!/usr/bin/env python3
import os
for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS'):
    os.environ.setdefault(key, '1')
import argparse
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, File, UploadFile, Request, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from starlette.concurrency import run_in_threadpool
from organizer.embedding import Embedder
from organizer.service import Organizer
from organizer.extract import DocumentError, MAX_UPLOAD

ROOT = Path(__file__).resolve().parent


def create_app(data_dir: Path = ROOT / 'data', keyword_only=False, organizer=None):
    @asynccontextmanager
    async def lifespan(app):
        app.state.organizer = organizer or Organizer(data_dir, Embedder(data_dir / 'model', not keyword_only))
        yield

    app = FastAPI(title='AI Document Organizer', lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware('http')
    async def guard(request: Request, call_next):
        host = request.headers.get('host', '')
        authority = host.split(':')[0]
        if authority not in ('localhost', '127.0.0.1') and not (organizer is not None and host == 'testserver'):
            return JSONResponse({'error': 'Only localhost access is supported.'}, 403)
        origin = request.headers.get('origin')
        if origin and origin != 'http://' + host:
            return JSONResponse({'error': 'Cross-origin requests are not allowed.'}, 403)
        # Content-Length is mandatory on writes; middleware below bounds actual bytes too.
        if request.method in ('POST', 'PATCH'):
            try:
                length = int(request.headers.get('content-length', '-1'))
            except ValueError:
                length = -1
            limit = MAX_UPLOAD + 65536 if request.url.path == '/api/upload' else 16384
            if length < 0 or length > limit:
                return JSONResponse({'error': 'Request is missing a valid size or exceeds its limit.'}, 413)
            # Streaming requests with dishonest lengths are bounded before form/JSON parsing.
            parts, size = [], 0
            async for part in request.stream():
                size += len(part)
                if size > limit:
                    return JSONResponse({'error': 'Request exceeds its size limit.'}, 413)
                parts.append(part)
            request._body = b''.join(parts)
        try:
            response = await call_next(request)
        except (ValueError, DocumentError) as exc:
            return JSONResponse({'error': str(exc)}, 400)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'"
        response.headers['Cache-Control'] = 'no-store'
        return response

    @app.exception_handler(ValueError)
    async def value_error(request, exc):
        return JSONResponse({'error': str(exc)}, 400)

    @app.exception_handler(KeyError)
    async def missing(request, exc):
        return JSONResponse({'error': 'Document not found.'}, 404)

    def service(request):
        return request.app.state.organizer

    @app.get('/')
    def index():
        return FileResponse(ROOT / 'web/index.html', media_type='text/html')

    @app.get('/assets/{name}')
    def assets(name: str):
        if name not in ('app.js', 'style.css'):
            raise HTTPException(404)
        return FileResponse(ROOT / 'web' / name)

    @app.get('/api/status')
    def status(request: Request):
        s = service(request)
        return {'semantic_available': s.embedder.available, 'message': s.embedder.reason,
                'collections': s.store.collections(), 'categories': sorted({d['category'] for d in s.store.list()}),
                'count': len(s.store.list())}

    @app.post('/api/upload')
    async def upload(request: Request, file: UploadFile = File(...)):
        content = await file.read(MAX_UPLOAD + 1)
        await file.close()
        if len(content) > MAX_UPLOAD:
            raise ValueError('File exceeds 8 MiB.')
        # Fixed internal parser process bounds extraction time; it never executes document code.
        # Service ingestion is serialized and runs off the event loop.
        return await run_in_threadpool(service(request).ingest, file.filename or '', content)

    @app.get('/api/documents')
    def documents(request: Request, q: str = '', mode: str = 'hybrid', category: str = '', collection: str = '', trash: bool = False):
        return service(request).search(q, mode, category, collection, trash)

    @app.get('/api/documents/{identity}')
    def document(identity: str, request: Request):
        doc = service(request).store.get(identity)
        doc.pop('stored_name', None)
        return doc

    @app.patch('/api/documents/{identity}')
    async def edit(identity: str, request: Request):
        try:
            data = await request.json()
        except Exception:
            raise ValueError('Malformed JSON metadata.')
        return service(request).store.edit(identity, data)

    @app.delete('/api/documents/{identity}')
    def delete(identity: str, request: Request):
        service(request).store.trash(identity, True)
        return {'message': 'Moved to Trash. You can restore it.'}

    @app.post('/api/documents/{identity}/restore')
    def restore(identity: str, request: Request):
        service(request).store.trash(identity, False)
        return {'message': 'Restored.'}

    @app.get('/api/documents/{identity}/original')
    def original(identity: str, request: Request):
        s = service(request); doc = s.store.get(identity)
        return FileResponse(s.store.root / 'files' / doc['stored_name'], filename=doc['filename'], media_type='application/octet-stream', content_disposition_type='attachment')

    @app.get('/api/export')
    def export(request: Request):
        return JSONResponse({'schema_version': 1, 'documents': service(request).store.list(), 'collections': service(request).store.collections(),
                             'note': 'Metadata only; original files, full text, Trash and embeddings are not included.'},
                            headers={'Content-Disposition': 'attachment; filename="document-index.json"'})

    @app.post('/api/reindex')
    def reindex(request: Request):
        return service(request).reindex()

    return app


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir', type=Path, default=ROOT / 'data')
    parser.add_argument('--keyword-only', action='store_true')
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args()
    import uvicorn
    uvicorn.run(create_app(args.data_dir, args.keyword_only), host='127.0.0.1', port=args.port, log_level='warning', limit_concurrency=16)
