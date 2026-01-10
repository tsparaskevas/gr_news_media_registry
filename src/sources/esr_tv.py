from __future__ import annotations

from pathlib import Path
from typing import List
import hashlib

import pandas as pd

from src.config import Paths


# Canonical input -> bronze output columns
INPUT_TO_OUT = {
    "ΤΡΕΧΟΥΣΑ ΕΠΩΝΥΜΙΑ ΑΠΟΘΕΤΗΡΙΟΥ": "name_raw",
    "ΚΑΤΑΣΤΑΣΗ: Λειτουργούντες (Λ) Ή Μη λειτουργούντες (ΜΛ)": "status_raw",
    "ΦΥΣΙΟΓΝΩΜΙΑ ΠΡΟΓΡΑΜΜΑΤΟΣ Ενημερωτικός (Ε) Μη ενημερωτικός (ΜΕ)": "content_type_raw",
    "ΤΥΠΟΣ ΕΜΒΕΛΕΙΑΣ": "range_raw",
    "ΝΟΜΟΣ": "prefecture_raw",
    "ΕΠΩΝΥΜΙΑ ΦΟΡΕΑ": "owner_raw",
}

REQUIRED_INPUT_COLS = set(INPUT_TO_OUT.keys())


def _clean_col(c: str) -> str:
    return " ".join(str(c).replace("\n", " ").split()).strip()


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [_clean_col(c) for c in df.columns]
    return df


def _latest_snapshot_folder(esr_sources_dir: Path) -> Path:
    dates = [p.name for p in esr_sources_dir.iterdir() if p.is_dir() and p.name[:4].isdigit()]
    if not dates:
        raise RuntimeError("No ESR snapshots found under data/sources/esr/")
    return esr_sources_dir / sorted(dates)[-1]


def _row_id(source_name: str, snapshot_date: str, name_raw: str) -> str:
    s = f"{source_name}|{snapshot_date}|{name_raw}"
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def _read_tv_excel(
    *,
    path: Path,
    sheet_name: str,
    source_name: str,
    snapshot_date: str,
) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name=sheet_name, header=0)
    df = _normalize_columns(df)

    missing_required = [c for c in REQUIRED_INPUT_COLS if c not in df.columns]
    if missing_required:
        raise RuntimeError(
            f"{path.name} (sheet={sheet_name}) missing required columns: {missing_required}\n"
            f"Available columns: {list(df.columns)}"
        )

    # take only available columns from INPUT_TO_OUT
    available_in = [c for c in INPUT_TO_OUT.keys() if c in df.columns]
    out = df[available_in].rename(columns={c: INPUT_TO_OUT[c] for c in available_in})

    # basic row cleanup
    out = out[out["name_raw"].notna()]
    out = out[out["name_raw"].astype(str).str.strip() != ""]

    out["source_name"] = source_name
    out["snapshot_date"] = snapshot_date
    out["source_file"] = path.name
    out["source_sheet"] = sheet_name

    out["row_id"] = out["name_raw"].astype(str).str.strip().apply(
        lambda name: _row_id(source_name, snapshot_date, name)
    )

    ordered = ["row_id", "source_name", "snapshot_date", "source_file", "source_sheet"] + list(INPUT_TO_OUT.values())
    return out[ordered]


def build_esr_tv_bronze(paths: Paths) -> Path:
    """
    Builds data/bronze/esr_tv_bronze.parquet from the latest ESR snapshot.
    """
    esr_dir = paths.sources / "esr"
    snap = _latest_snapshot_folder(esr_dir)
    snapshot_date = snap.name

    frames: List[pd.DataFrame] = []

    national_path = snap / "tve.xls"
    if national_path.exists():
        frames.append(
            _read_tv_excel(
                path=national_path,
                sheet_name="tve",
                source_name="esr_tv_national",
                snapshot_date=snapshot_date,
            )
        )

    regional_path = snap / "tvtp.xls"
    if regional_path.exists():
        frames.append(
            _read_tv_excel(
                path=regional_path,
                sheet_name="tvp",
                source_name="esr_tv_regional",
                snapshot_date=snapshot_date,
            )
        )

    if not frames:
        raise RuntimeError(f"No ESR TV files found in latest snapshot folder: {snap}")

    out = pd.concat(frames, ignore_index=True)

    paths.bronze.mkdir(parents=True, exist_ok=True)
    out_path = paths.bronze / "esr_tv_bronze.parquet"
    out.to_parquet(out_path, index=False)
    return out_path

