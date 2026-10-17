"""Fixed internal parser process; input bytes on stdin, JSON on stdout."""
import json
import sys
try:
    import resource
    resource.setrlimit(resource.RLIMIT_CPU, (8, 9))
    if sys.platform != 'darwin':
        resource.setrlimit(resource.RLIMIT_AS, (1024 ** 3, 1024 ** 3))
except (ImportError, ValueError, OSError):
    pass
from .extract import extract, MAX_UPLOAD

try:
    text, warnings = extract(sys.argv[1], sys.stdin.buffer.read(MAX_UPLOAD + 1))
    print(json.dumps({'text': text, 'warnings': warnings}))
except Exception as exc:
    print(json.dumps({'error': str(exc) if isinstance(exc, ValueError) else 'Document parsing failed.'}))
    sys.exit(1)
