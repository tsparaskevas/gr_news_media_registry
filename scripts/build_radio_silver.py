from pathlib import Path
from src.config import get_paths
from src.silver.radio import build_radio_silver

root = Path(__file__).resolve().parents[1]
paths = get_paths(root)

out = build_radio_silver(paths)
print("Wrote:", out)

