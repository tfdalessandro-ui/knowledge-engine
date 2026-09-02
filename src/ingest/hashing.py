"""Content-hash change detection: a file only gets re-parsed/re-chunked/
re-indexed if its content actually changed, not just its mtime."""
from __future__ import annotations

import hashlib
from pathlib import Path


def content_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
