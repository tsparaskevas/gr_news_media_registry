from pathlib import Path
from src.config import get_paths
from src.sources.mt_websites import build_mt_websites_bronze

root = Path(__file__).resolve().parents[1]
paths = get_paths(root)

out = build_mt_websites_bronze(paths)
print("Wrote:", out)

