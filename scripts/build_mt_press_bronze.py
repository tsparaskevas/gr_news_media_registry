from pathlib import Path
from src.config import get_paths
from src.sources.mt_press import build_mt_press_bronze

root = Path(__file__).resolve().parents[1]
paths = get_paths(root)

out = build_mt_press_bronze(paths)
print("Wrote:", out)

