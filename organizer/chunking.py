import re

MAX_CHUNKS = 200


def chunk_text(text: str, size: int = 160, overlap: int = 32) -> list[str]:
    """Short overlapping word windows reduce MiniLM's token truncation risk."""
    if size < 1 or not 0 <= overlap < size:
        raise ValueError('invalid chunk size/overlap')
    words = re.findall(r'\S+', text)
    chunks = []
    for start in range(0, len(words), size - overlap):
        chunks.append(' '.join(words[start:start + size]))
        if start + size >= len(words):
            break
        if len(chunks) >= MAX_CHUNKS:
            raise ValueError('Document exceeds the 200-chunk limit.')
    return chunks
