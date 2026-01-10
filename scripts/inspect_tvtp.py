from pathlib import Path
import pandas as pd

base = Path("data/sources/esr")
latest = sorted([p for p in base.iterdir() if p.is_dir()])[-1]
file = latest / "tvtp.xls"

xf = pd.ExcelFile(file)
print("Sheets:", xf.sheet_names)

# pick a likely one: first non-info sheet
sheet = xf.sheet_names[-1]
print("Using sheet:", sheet)

preview = pd.read_excel(file, sheet_name=sheet, header=None, nrows=10)
print(preview)

