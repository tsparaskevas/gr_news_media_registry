from __future__ import annotations
from pathlib import Path
import pandas as pd
from pandas.errors import EmptyDataError

OVERRIDE_COLUMNS = ["id", "url", "url_status", "fb", "x", "youtube", "status", "content_type", "media_type", "notes"]


def load_outlet_overrides(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=OVERRIDE_COLUMNS)

    # Handle empty 0-byte file
    try:
        df = pd.read_csv(path, dtype=str).fillna("")
    except EmptyDataError:
        return pd.DataFrame(columns=OVERRIDE_COLUMNS)

    for c in OVERRIDE_COLUMNS:
        if c not in df.columns:
            df[c] = ""
    return df[OVERRIDE_COLUMNS]


def upsert_outlet_override(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df = load_outlet_overrides(path)

    rid = str(row.get("id", "")).strip()
    if not rid:
        raise ValueError("Override row must include non-empty 'id'.")

    # normalize incoming row to schema
    clean = {c: str(row.get(c, "") or "").strip() for c in OVERRIDE_COLUMNS}
    clean["id"] = rid

    # upsert by id (keep last)
    df = df[df["id"].astype(str).str.strip() != rid].copy()
    df = pd.concat([df, pd.DataFrame([clean])], ignore_index=True)

    df.to_csv(path, index=False)


def apply_outlet_overrides(gold: pd.DataFrame, overrides: pd.DataFrame) -> pd.DataFrame:
    """
    Applies non-empty override fields onto the gold dataframe by id.
    """
    if overrides.empty or "id" not in overrides.columns:
        return gold

    out = gold.copy()
    o = overrides.copy()

    o["id"] = o["id"].astype(str).str.strip()
    out["id"] = out["id"].astype(str).str.strip()

    o = o.drop_duplicates(subset=["id"], keep="last")
    o = o.set_index("id")

    # only apply fields that exist on gold
    for col in ["url", "url_status", "fb", "x", "youtube", "status", "content_type", "media_type", "notes"]:
        if col in out.columns and col in o.columns:
            s = o[col]
            mask = out["id"].isin(s.index) & (s.reindex(out["id"]).fillna("").values != "")
            # align values by id
            vals = s.reindex(out.loc[mask, "id"]).values
            out.loc[mask, col] = vals

    return out

