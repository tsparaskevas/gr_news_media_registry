from pathlib import Path
import pandas as pd

def clean_col(c: str) -> str:
    return " ".join(str(c).replace("\n", " ").split()).strip()

def inspect(file_path: Path, sheet_name: str, n_rows: int = 3) -> None:
    print("\n" + "=" * 80)
    print(f"FILE: {file_path}")
    print(f"SHEET: {sheet_name}")

    df = pd.read_excel(file_path, sheet_name=sheet_name, header=0)
    df.columns = [clean_col(c) for c in df.columns]

    print("\nCOLUMNS (as pandas sees them):")
    for i, c in enumerate(df.columns, start=1):
        print(f"{i:02d}. {c}")

    # pick the first "real" row: name column if present, else first row
    name_candidates = [
        "ΤΡΕΧΟΥΣΑ ΕΠΩΝΥΜΙΑ ΑΠΟΘΕΤΗΡΙΟΥ",
        "ΤΡΕΧΟΥΣΑ ΟΝΟΜΑΣΙΑ ΣΤΑΘΜΟΥ",
        "ΤΡΕΧΟΥΣΑ ΟΝΟΜΑΣΙΑ",
    ]
    name_col = next((c for c in name_candidates if c in df.columns), None)

    if name_col:
        df2 = df[df[name_col].notna()]
    else:
        df2 = df

    if df2.empty:
        print("\n(No data rows found.)")
        return

    row = df2.iloc[0]

    print("\nONE SAMPLE DATA ROW (first non-empty):")
    # print all columns with their values, so you can spot status/owner/etc
    for c in df.columns:
        v = row.get(c)
        if pd.isna(v):
            continue
        s = str(v).strip()
        if s == "":
            continue
        print(f"- {c}: {s}")

    print("\nTOP 3 ROWS (selected columns if present):")
    cols_show = []
    for c in name_candidates + ["ΝΟΜΟΣ", "ΤΥΠΟΣ ΕΜΒΕΛΕΙΑΣ", "ΕΠΩΝΥΜΙΑ ΦΟΡΕΑ", "ΚΑΤΑΣΤΑΣΗ", "ΦΥΣΙΟΓΝΩΜΙΑ ΠΡΟΓΡΑΜΜΑΤΟΣ"]:
        if c in df.columns and c not in cols_show:
            cols_show.append(c)
    if cols_show:
        print(df2[cols_show].head(n_rows).to_string(index=False))
    else:
        print(df2.head(n_rows).to_string(index=False))

def main():
    base = Path("data/sources/esr")
    latest = sorted([p for p in base.iterdir() if p.is_dir()])[-1]

    tve = latest / "tve.xls"
    tvtp = latest / "tvtp.xls"

    if tve.exists():
        inspect(tve, "tve")
    else:
        print("Missing tve.xls in latest snapshot")

    if tvtp.exists():
        inspect(tvtp, "tvp")
    else:
        print("Missing tvtp.xls in latest snapshot")

if __name__ == "__main__":
    main()

