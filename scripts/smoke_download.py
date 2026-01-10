from pathlib import Path
from src.config import get_paths
from src.io_snapshots import download_snapshot

root = Path(__file__).resolve().parents[1] 
paths = get_paths(root)

download_snapshot(
    base_sources_dir=paths.sources,
    source_group="esr",
    source_name="esr_tv_national",
    url="https://www.esr.gr/wp-content/uploads/tve.xls",
    filename="tve.xls",
)
print("OK")

