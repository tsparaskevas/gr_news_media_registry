from pathlib import Path
from src.config import get_paths
from src.gold.registry import build_registry_gold

root = Path(__file__).resolve().parents[1]
paths = get_paths(root)

out = build_registry_gold(paths)
print("Wrote:", out)

