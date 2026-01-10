from pathlib import Path
from src.config import get_paths
from src.silver.websites import build_websites_silver

root = Path(__file__).resolve().parents[1]
paths = get_paths(root)

out = build_websites_silver(paths)
print("Wrote:", out)

