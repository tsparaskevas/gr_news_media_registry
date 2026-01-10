from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

@dataclass(frozen=True)
class SnapshotManifest:
    source_name: str
    url: str
    snapshot_date: str  # YYYY-MM-DD
    filename: str
    bytes: int
    sha256: str
    downloaded_at_utc: str  # ISO timestamp
    http_etag: Optional[str] = None
    http_last_modified: Optional[str] = None

def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()

def write_manifest(folder: Path, manifest: SnapshotManifest) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    out = folder / "manifest.json"
    out.write_text(json.dumps(asdict(manifest), ensure_ascii=False, indent=2), encoding="utf-8")
    return out

def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

