from __future__ import annotations

from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Optional

import requests

from .manifests import SnapshotManifest, now_utc_iso, sha256_file, write_manifest

def snapshot_folder(base_sources_dir: Path, source_group: str, snapshot_date: str) -> Path:
    # e.g. data/sources/esr/2025-12-22/
    return base_sources_dir / source_group / snapshot_date

def download_snapshot(
    *,
    base_sources_dir: Path,
    source_group: str,     # "esr" or "mt_media"
    source_name: str,      # "esr_tv_national", etc.
    url: str,
    filename: str,
    snapshot_date: Optional[str] = None,
    timeout_sec: int = 60,
) -> Path:
    """
    Downloads `url` into:
      data/sources/<source_group>/<snapshot_date>/<filename>
    Writes/updates manifest.json in the same folder.
    Returns the file path.
    """
    snap_date = snapshot_date or date.today().isoformat()
    folder = snapshot_folder(base_sources_dir, source_group, snap_date)
    folder.mkdir(parents=True, exist_ok=True)
    out_path = folder / filename

    headers = {"User-Agent": "gr-media-registry/0.1 (+audit reproducible snapshots)"}
    with requests.get(url, stream=True, headers=headers, timeout=timeout_sec) as r:
        r.raise_for_status()
        etag = r.headers.get("ETag")
        last_modified = r.headers.get("Last-Modified")
        with out_path.open("wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)

    b = out_path.stat().st_size
    digest = sha256_file(out_path)

    manifest = SnapshotManifest(
        source_name=source_name,
        url=url,
        snapshot_date=snap_date,
        filename=filename,
        bytes=b,
        sha256=digest,
        downloaded_at_utc=now_utc_iso(),
        http_etag=etag,
        http_last_modified=last_modified,
    )
    write_manifest(folder, manifest)
    return out_path

