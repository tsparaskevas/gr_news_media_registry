from __future__ import annotations

import pandas as pd
from src.config import Paths
from src.prefectures import load_prefecture_aliases, apply_prefecture_aliasing


def _map_press_type(press_type_raw: object) -> tuple[str, str, str]:
    """
    Returns (media_type, range_type, frequency)
    Based on your mapping spec.
    """
    s = str(press_type_raw).strip()
    s_norm = s.casefold()

    mapping = {
        "Λοιπές πανελλαδικής κυκλοφορίας": ("newspaper", "national", "unknown"),
        "Ημερήσιες πανελλαδικής κυκλοφορίας": ("newspaper", "national", "daily"),
        "Ημερήσιες Πανελλαδικής Κυκλοφορίας": ("newspaper", "national", "daily"),
        "Εβδομαδιαίες περιφερειακές εφημερίδες": ("newspaper", "regional", "weekly"),
        "Ημερήσιες περιφερειακές εφημερίδες": ("newspaper", "regional", "daily"),
        "Περιοδικά": ("magazine", "unknown", "periodical"),
        "Περιφερειακές εκδόσεις με περιοδικότητα άνω της δεκαπενθήμερης κυκλοφορίας": ("unknown", "regional", "unknown"),
    }
    mapping_norm = {k.casefold(): v for k, v in mapping.items()}
    return mapping_norm.get(s_norm, ("unknown","unknown","unknown"))


def _norm(s: object) -> str:
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return ""
    return " ".join(str(s).replace("\n", " ").split()).strip()

def _make_tax_office_key(tax_office: object, area: object) -> str:
    t = _norm(tax_office)
    a = _norm(area)
    # If tax office is missing or suspiciously short, use composite
    if t == "" or len(t) < 3:
        return f"{t} | {a}".strip(" |")
    return t


def build_press_silver(paths: Paths) -> str:
    bronze_path = paths.bronze / "mt_press_bronze.parquet"
    if not bronze_path.exists():
        raise RuntimeError(f"Missing {bronze_path}. Build MT press bronze first.")

    df = pd.read_parquet(bronze_path)

    out = pd.DataFrame()
    out["row_id"] = df["row_id"]
    out["source_name"] = df["source_name"]
    out["snapshot_date"] = df["snapshot_date"]

    out["name"] = df["name_raw"].astype(str).str.strip()
    out["owner"] = df["owner_raw"].astype("string").str.strip()

    out["tax_office_raw"] = df["tax_office_raw"].astype("string")
    out["area_raw"] = df["area_raw"].astype("string")

    out["tax_office_key"] = [
        _make_tax_office_key(t, a)
        for t, a in zip(out["tax_office_raw"], out["area_raw"])
    ]

    out["press_type_raw"] = df["press_type_raw"].astype("string")
    mapped = out["press_type_raw"].apply(_map_press_type)
    out["media_type"] = mapped.apply(lambda t: t[0])
    out["range_type"] = mapped.apply(lambda t: t[1])
    out["frequency"] = mapped.apply(lambda t: t[2])

    out["status"] = "operating"
    out["content_type"] = "unknown"

    # Prefecture aliasing from tax office
    aliases = load_prefecture_aliases(paths.overrides / "prefecture_aliases.csv")
    out = apply_prefecture_aliasing(out, raw_col="tax_office_key", aliases_df=aliases)

    # NOTE: apply_prefecture_aliasing writes to columns: prefecture, prefecture_en, prefecture_match_type
    # That’s fine for your outputs (you prefer prefecture_en).

    out = out[out["name"].notna() & (out["name"].str.strip() != "")].copy()

    paths.silver.mkdir(parents=True, exist_ok=True)
    out_path = paths.silver / "press_silver.parquet"
    out.to_parquet(out_path, index=False)
    return str(out_path)

