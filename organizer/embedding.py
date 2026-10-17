"""Offline-only inference. Initial model download is a separate explicit command."""
import os
from pathlib import Path
import threading
import numpy as np

MODEL_ID = 'sentence-transformers/all-MiniLM-L6-v2'


class Embedder:
    def __init__(self, path: Path, enabled: bool = True):
        self.model = None
        self.dimension = 384
        self.reason = 'Keyword-only mode requested.'
        self.lock = threading.Lock()
        if not enabled:
            return
        if not (path / 'config.json').exists():
            self.reason = 'Embedding model is not installed. Run python setup_model.py, then restart.'
            return
        try:
            os.environ['HF_HUB_OFFLINE'] = '1'
            os.environ['TOKENIZERS_PARALLELISM'] = 'false'
            from sentence_transformers import SentenceTransformer
            import torch
            torch.set_num_threads(1)
            self.model = SentenceTransformer(str(path), device='cpu', local_files_only=True, trust_remote_code=False)
            self.dimension = self.model.get_embedding_dimension()
            self.reason = ''
        except Exception:
            self.reason = 'Local model could not load. Check dependencies or reinstall it with setup_model.py.'

    @property
    def available(self):
        return self.model is not None

    def encode(self, texts: list[str]) -> np.ndarray:
        if not self.available:
            raise RuntimeError(self.reason)
        with self.lock:
            vectors = self.model.encode(texts, batch_size=32, normalize_embeddings=True, show_progress_bar=False, convert_to_numpy=True)
        result = np.asarray(vectors, dtype=np.float32)
        if result.shape != (len(texts), self.dimension) or not np.isfinite(result).all():
            raise ValueError('Embedding model returned invalid vectors.')
        return result
