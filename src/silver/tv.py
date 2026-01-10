from __future__ import annotations

from pathlib import Path
import pandas as pd

from src.config import Paths
from src.prefectures import load_prefecture_aliases, apply_prefecture_aliasing


def _map_status(x: object) -> str:
    s = str(x).strip()
    if s == "Λ":
        return "operating"
    if s == "ΜΛ":
        return "not_operating"
    return "unknown"


def _map_content_type(x: object) -> str:
    s = str(x).strip()
    if s == "Ε":
        return "news"
    if s == "ΜΕ":
        return "other"
    return "unknown"


def _map_range_type(x: object) -> str:
    s = str(x).strip()
    if s == "Εθνική":
        return "national"
    if s == "Περιφερειακή":
        return "regional"
    return "unknown"


def build_tv_silver(paths: Paths) -> Path:
    bronze_path = paths.bronze / "esr_tv_bronze.parquet"
    if not bronze_path.exists():
        raise RuntimeError(f"Missing {bronze_path}. Build TV bronze first.")

    df = pd.read_parquet(bronze_path)

    out = pd.DataFrame()
    out["row_id"] = df["row_id"]
    out["source_name"] = df["source_name"]
    out["snapshot_date"] = df["snapshot_date"]

    out["name"] = df["name_raw"].astype(str).str.strip()
    out["media_type"] = "tv"
    out["frequency"] = "unknown"

    out["range_type"] = df["range_raw"].apply(_map_range_type)

    # Keep raw + a placeholder canonical (we’ll alias later)
    out["prefecture_raw"] = df["prefecture_raw"].astype("string")
    aliases = load_prefecture_aliases(paths.overrides / "prefecture_aliases.csv")
    out = apply_prefecture_aliasing(out, raw_col="prefecture_raw", aliases_df=aliases)

    out["content_type"] = df["content_type_raw"].apply(_map_content_type)
    out["status"] = df["status_raw"].apply(_map_status)

    out["owner"] = df["owner_raw"].astype("string").str.strip()

    # Basic cleanup: keep rows with a name
    out = out[out["name"].notna() & (out["name"].str.strip() != "")].copy()

    paths.silver.mkdir(parents=True, exist_ok=True)
    out_path = paths.silver / "tv_silver.parquet"
    out.to_parquet(out_path, index=False)
    return out_path

