from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import pandas as pd


def _norm(s: object) -> str:
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return ""
    # normalize whitespace + strip
    return " ".join(str(s).replace("\n", " ").split()).strip()


@dataclass(frozen=True)
class PrefectureMatch:
    prefecture: str | None
    prefecture_en: str | None
    match_type: str  # exact | missing | unknown


def load_prefecture_aliases(path: Path) -> pd.DataFrame:
    if not path.exists():
        # return empty but with correct columns
        return pd.DataFrame(columns=["alias", "alias_type", "prefecture", "prefecture_en", "notes"])

    df = pd.read_csv(path, dtype=str).fillna("")
    # normalized key
    df["alias_norm"] = df["alias"].map(_norm)
    # drop empty aliases
    df = df[df["alias_norm"] != ""].copy()
    # keep last occurrence if duplicates
    df = df.drop_duplicates(subset=["alias_norm"], keep="last")
    return df


def normalize_prefecture(raw: object, aliases_df: pd.DataFrame) -> PrefectureMatch:
    r = _norm(raw)
    if r == "":
        return PrefectureMatch(prefecture=None, prefecture_en=None, match_type="missing")

    if aliases_df is None or aliases_df.empty:
        return PrefectureMatch(prefecture=None, prefecture_en=None, match_type="unknown")

    row = aliases_df.loc[aliases_df["alias_norm"] == r]
    if row.empty:
        return PrefectureMatch(prefecture=None, prefecture_en=None, match_type="unknown")

    rec = row.iloc[0]
    pref = _norm(rec.get("prefecture"))
    pref_en = _norm(rec.get("prefecture_en"))

    return PrefectureMatch(
        prefecture=pref or None,
        prefecture_en=pref_en or None,
        match_type="exact",
    )


def apply_prefecture_aliasing(df: pd.DataFrame, raw_col: str, aliases_df: pd.DataFrame) -> pd.DataFrame:
    """
    Adds/overwrites:
      - prefecture (canonical)
      - prefecture_en
      - prefecture_match_type
    Keeps raw_col unchanged for auditability.
    """
    out = df.copy()
    matches = out[raw_col].apply(lambda x: normalize_prefecture(x, aliases_df))

    out["prefecture"] = matches.apply(lambda m: m.prefecture)
    out["prefecture_en"] = matches.apply(lambda m: m.prefecture_en)
    out["prefecture_match_type"] = matches.apply(lambda m: m.match_type)
    return out


def unmatched_values(df: pd.DataFrame, raw_col: str, aliases_df: pd.DataFrame) -> pd.DataFrame:
    """
    Returns a table of raw values not found in alias table, with counts.
    """
    raw_series = df[raw_col].map(_norm)
    raw_series = raw_series[raw_series != ""]

    known = set(aliases_df["alias_norm"]) if aliases_df is not None and not aliases_df.empty else set()
    unknown = raw_series[~raw_series.isin(known)]

    return (
        unknown.value_counts()
        .rename_axis("alias")
        .reset_index(name="count")
        .sort_values(["count", "alias"], ascending=[False, True])
    )

