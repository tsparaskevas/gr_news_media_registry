from __future__ import annotations

import pandas as pd
from src.config import Paths
from src.prefectures import load_prefecture_aliases, apply_prefecture_aliasing

def _norm(s: object) -> str:
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return ""
    return " ".join(str(s).replace("\n", " ").split()).strip()

def _make_tax_office_key(tax_office: object, area: object) -> str:
    t = _norm(tax_office)
    a = _norm(area)

    # If ΔΟΥ is missing -> use area
    if t == "":
        return a

    # If ΔΟΥ is numeric-only (e.g. "5621") it's ambiguous; use composite when area exists
    if t.isdigit() and a != "":
        return f"{t} | {a}"

    # If ΔΟΥ is suspiciously short -> use composite
    if len(t) < 3 and a != "":
        return f"{t} | {a}"

    return t

def build_websites_silver(paths: Paths) -> str:
    bronze_path = paths.bronze / "mt_websites_bronze.parquet"
    if not bronze_path.exists():
        raise RuntimeError(f"Missing {bronze_path}. Build MT websites bronze first.")

    df = pd.read_parquet(bronze_path)

    out = pd.DataFrame()
    out["row_id"] = df["row_id"]
    out["source_name"] = df["source_name"]
    out["snapshot_date"] = df["snapshot_date"]

    out["name"] = df["name_raw"].astype(str).str.strip()
    out["url"] = df["url_raw"].astype(str).str.strip()
    out["url_norm"] = out["url"].str.lower().str.strip()
    out["domain"] = (
        out["url_norm"]
        .str.replace("https://", "", regex=False)
        .str.replace("http://", "", regex=False)
        .str.replace("www.", "", regex=False)
        .str.split("/", n=1).str[0]
    )

    out["owner"] = df["owner_raw"].astype("string").str.strip()

    out["tax_office_raw"] = df["tax_office_raw"].astype("string")
    out["area_raw"] = df["area_raw"].astype("string") if "area_raw" in df.columns else pd.NA
    out["tax_office_key"] = [
        _make_tax_office_key(t, a)
        for t, a in zip(out["tax_office_raw"], out["area_raw"])
    ]

    out["media_type"] = "website"
    out["range_type"] = "national"
    out["frequency"] = "unknown"

    out["status"] = "operating"
    out["content_type"] = "unknown"

    aliases = load_prefecture_aliases(paths.overrides / "prefecture_aliases.csv")
    out = apply_prefecture_aliasing(out, raw_col="tax_office_key", aliases_df=aliases)

    out = out[out["url"].notna() & (out["url"].str.strip() != "")].copy()

    paths.silver.mkdir(parents=True, exist_ok=True)
    out_path = paths.silver / "websites_silver.parquet"
    out.to_parquet(out_path, index=False)
    return str(out_path)

