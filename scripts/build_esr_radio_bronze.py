from pathlib import Path
from src.config import get_paths
from src.sources.esr_radio import build_esr_radio_bronze

root = Path(__file__).resolve().parents[1]
paths = get_paths(root)

out = build_esr_radio_bronze(paths)
print("Wrote:", out)

