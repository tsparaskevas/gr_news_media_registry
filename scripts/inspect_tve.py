from pathlib import Path
import pandas as pd

path = Path("data/sources/esr")  # base
latest = sorted([p for p in path.iterdir() if p.is_dir()])[-1]
file = latest / "tve.xls"

xf = pd.ExcelFile(file)
print("Sheets:", xf.sheet_names)

sheet = "tve" if "tve" in xf.sheet_names else 0
print("Using sheet:", sheet)

preview = pd.read_excel(file, sheet_name=sheet, header=None, nrows=10)
print(preview)

