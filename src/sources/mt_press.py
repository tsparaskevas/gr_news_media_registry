from __future__ import annotations

from pathlib import Path
import hashlib
import pandas as pd

from src.config import Paths


def _clean_col(c: object) -> str:
    return " ".join(str(c).replace("\n", " ").split()).strip()


def _latest_snapshot_folder(mt_sources_dir: Path) -> Path:
    dates = [p.name for p in mt_sources_dir.iterdir() if p.is_dir() and p.name[:4].isdigit()]
    if not dates:
        raise RuntimeError("No MT snapshots found under data/sources/mt_media/")
    return mt_sources_dir / sorted(dates)[-1]


def _row_id(source_name: str, snapshot_date: str, name_raw: str, owner_raw: str) -> str:
    s = f"{source_name}|{snapshot_date}|{name_raw}|{owner_raw}"
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def build_mt_press_bronze(paths: Paths) -> Path:
    mt_dir = paths.sources / "mt_media"
    snap = _latest_snapshot_folder(mt_dir)
    snapshot_date = snap.name

    f = snap / "press_export.xls"
    if not f.exists():
        raise RuntimeError(f"Missing {f}. Run scripts/download_mt_press.py first.")

    df = pd.read_excel(f, header=0)
    df.columns = [_clean_col(c) for c in df.columns]

    required = ["Έντυπο", "ΔΟΥ", "Είδος εντύπου"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise RuntimeError(f"press_export.xls missing columns: {missing}\nAvailable: {list(df.columns)}")

    out = pd.DataFrame()
    out["name_raw"] = df["Έντυπο"]
    owner_col = "Επωνυμία επιχείρησης" if "Επωνυμία επιχείρησης" in df.columns else ("Επωνυμία" if "Επωνυμία" in df.columns else None)
    if owner_col is None:
        raise RuntimeError(f"press_export.xls missing owner column. Available: {list(df.columns)}")
    out["owner_raw"] = df[owner_col]
    out["tax_office_raw"] = df["ΔΟΥ"]
    out["area_raw"] = df["Περιοχή"] if "Περιοχή" in df.columns else pd.NA
    out["press_type_raw"] = df["Είδος εντύπου"]

    out = out[out["name_raw"].notna()]
    out = out[out["name_raw"].astype(str).str.strip() != ""]

    out["source_name"] = "mt_press"
    out["snapshot_date"] = snapshot_date
    out["source_file"] = f.name
    out["source_sheet"] = "0"

    out["row_id"] = out.apply(
        lambda r: _row_id(
            "mt_press",
            snapshot_date,
            str(r["name_raw"]).strip(),
            str(r["owner_raw"]).strip(),
        ),
        axis=1,
    )

    ordered = [
        "row_id", "source_name", "snapshot_date", "source_file", "source_sheet",
        "name_raw", "owner_raw", "tax_office_raw", "area_raw", "press_type_raw",
    ]
    out = out[ordered]

    paths.bronze.mkdir(parents=True, exist_ok=True)
    out_path = paths.bronze / "mt_press_bronze.parquet"
    out.to_parquet(out_path, index=False)
    return out_path

