from pathlib import Path
from src.config import get_paths
from src.silver.press import build_press_silver

root = Path(__file__).resolve().parents[1]
paths = get_paths(root)

out = build_press_silver(paths)
print("Wrote:", out)

