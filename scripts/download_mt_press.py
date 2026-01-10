from pathlib import Path
from src.config import get_paths
from src.io_snapshots import download_snapshot

root = Path(__file__).resolve().parents[1]
paths = get_paths(root)

download_snapshot(
    base_sources_dir=paths.sources,
    source_group="mt_media",
    source_name="mt_press",
    url="http://mt.media.gov.gr/submissions/MET/public/export",
    filename="press_export.xls",
)
print("Downloaded press_export.xls")

