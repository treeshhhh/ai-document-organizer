#!/usr/bin/env python3
"""Download public model weights only; no documents are read or transmitted."""
import os
os.environ['HF_HUB_DISABLE_XET'] = '1'
import argparse
import json
from pathlib import Path
from huggingface_hub import HfApi, snapshot_download
from organizer.embedding import MODEL_ID

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir', default='data')
    parser.add_argument('--revision', default='1110a243fdf4706b3f48f1d95db1a4f5529b4d41')
    args = parser.parse_args()
    path = Path(args.data_dir) / 'model'
    info = HfApi().model_info(MODEL_ID, revision=args.revision)
    snapshot_download(MODEL_ID, revision=info.sha, local_dir=str(path),
                      allow_patterns=['*.json', '*.txt', '*.safetensors'],
                      ignore_patterns=['onnx/*', 'openvino/*'], max_workers=4)
    (path / 'download-info.json').write_text(json.dumps({'model': MODEL_ID, 'revision': info.sha}, indent=2))
    print('Model installed locally at', path)
