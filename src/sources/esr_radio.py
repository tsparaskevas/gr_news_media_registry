from __future__ import annotations

from pathlib import Path
from typing import List, Optional
import hashlib

import pandas as pd

from src.config import Paths


def _clean_col(c: object) -> str:
    return " ".join(str(c).replace("\n", " ").split()).strip()


def _latest_snapshot_folder(esr_sources_dir: Path) -> Path:
    dates = [p.name for p in esr_sources_dir.iterdir() if p.is_dir() and p.name[:4].isdigit()]
    if not dates:
        raise RuntimeError("No ESR snapshots found under data/sources/esr/")
    return esr_sources_dir / sorted(dates)[-1]


def _row_id(source_name: str, snapshot_date: str, sheet_name: str, name_raw: str) -> str:
    s = f"{source_name}|{snapshot_date}|{sheet_name}|{name_raw}"
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def _find_col(df: pd.DataFrame, contains: List[str]) -> Optional[str]:
    """
    Find first column whose cleaned name contains ALL tokens in `contains`.
    """
    cols = [(_clean_col(c), c) for c in df.columns]
    for cleaned, original in cols:
        ok = True
        for token in contains:
            if token not in cleaned:
                ok = False
                break
        if ok:
            return original
    return None


def _read_radio_sheet(path: Path, sheet_name: str, snapshot_date: str) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name=sheet_name, header=0)
    df.columns = [_clean_col(c) for c in df.columns]

    # Detect required columns (robust to slight header text changes)
    col_name = _find_col(df, ["ΤΡΕΧΟΥΣΑ", "ΕΠΩΝΥΜΙΑ"])
    col_status = _find_col(df, ["ΚΑΤΑΣΤΑΣΗ", "(Λ)"])
    col_content = _find_col(df, ["ΦΥΣΙΟΓΝΩΜΙΑ", "(Ε="])  # often contains the (Ε=...) note
    col_owner = _find_col(df, ["ΙΔΙΟΚΤΗΣΙΑΚΟΣ", "ΦΟΡΕΑΣ"])

    # If this sheet doesn't look like a prefecture listing, skip it
    if not col_name:
        return pd.DataFrame()

    out = pd.DataFrame()
    out["name_raw"] = df[col_name]
    out["status_raw"] = df[col_status] if col_status else pd.NA
    out["content_type_raw"] = df[col_content] if col_content else pd.NA
    out["owner_raw"] = df[col_owner] if col_owner else pd.NA

    out["prefecture_raw"] = sheet_name
    out = out[out["name_raw"].notna()]
    out = out[out["name_raw"].astype(str).str.strip() != ""]

    out["source_name"] = "esr_radio"
    out["snapshot_date"] = snapshot_date
    out["source_file"] = path.name
    out["source_sheet"] = sheet_name

    out["row_id"] = out["name_raw"].astype(str).str.strip().apply(
        lambda name: _row_id("esr_radio", snapshot_date, sheet_name, name)
    )

    ordered = [
        "row_id", "source_name", "snapshot_date", "source_file", "source_sheet",
        "name_raw", "status_raw", "content_type_raw", "prefecture_raw", "owner_raw",
    ]
    return out[ordered]


def build_esr_radio_bronze(paths: Paths) -> Path:
    esr_dir = paths.sources / "esr"
    snap = _latest_snapshot_folder(esr_dir)
    snapshot_date = snap.name

    radio_path = snap / "bnl.xlsx"
    if not radio_path.exists():
        raise RuntimeError(
            f"Missing {radio_path}. Download it first (scripts/download_esr_bnl.py)."
        )

    xf = pd.ExcelFile(radio_path)
    frames: List[pd.DataFrame] = []

    for sheet in xf.sheet_names:
        df_sheet = _read_radio_sheet(radio_path, sheet, snapshot_date)
        if not df_sheet.empty:
            frames.append(df_sheet)

    if not frames:
        raise RuntimeError("No radio rows found. ESR format may have changed.")

    out = pd.concat(frames, ignore_index=True)

    paths.bronze.mkdir(parents=True, exist_ok=True)
    out_path = paths.bronze / "esr_radio_bronze.parquet"
    out.to_parquet(out_path, index=False)
    return out_path

