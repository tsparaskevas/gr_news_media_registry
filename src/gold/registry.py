from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Tuple

import pandas as pd

from src.config import Paths


def _norm_text(x: object) -> str:
    # Treat pandas missing values and their string representations as empty
    if x is None:
        return ""
    try:
        if pd.isna(x):
            return ""
    except Exception:
        pass

    s = str(x).strip().lower()
    if s in {"<na>", "na", "nan", "none", ""}:
        return ""
    s = re.sub(r"\s+", " ", s)
    return s


def _norm_owner(x: object) -> str:
    s = _norm_text(x)
    # very light normalization; keep it conservative
    s = s.replace("ανωνυμη", "α.ε.").replace("ανώνυμη", "α.ε.")
    return s


def _norm_name(x: object) -> str:
    return _norm_text(x)


def _make_id(media_type: str, name: str, prefecture_en: str, owner: str) -> str:
    key = f"{media_type}|{_norm_name(name)}|{_norm_text(prefecture_en)}|{_norm_owner(owner)}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()


def _norm_url(x: object) -> str:
    """Light URL normalization for comparisons (duplicate detection)."""
    s = _norm_text(x)
    if not s:
        return ""
    s = s.strip()
    s = s.replace(" ", "")
    s_low = s.lower()

    # strip scheme
    if s_low.startswith("https://"):
        s_low = s_low[len("https://") :]
    elif s_low.startswith("http://"):
        s_low = s_low[len("http://") :]

    # strip www.
    if s_low.startswith("www."):
        s_low = s_low[len("www.") :]

    # drop path/query/fragment
    s_low = s_low.split("?", 1)[0].split("#", 1)[0]
    s_low = s_low.split("/", 1)[0]

    return s_low


def _extract_domain_from_url(url: object) -> str:
    # Keep consistent with your current websites domain extraction
    u = _norm_text(url)
    if not u:
        return ""
    u_low = u.lower().strip()
    u_low = u_low.replace("https://", "").replace("http://", "")
    u_low = u_low.replace("www.", "")
    return u_low.split("/", 1)[0].strip()


def _load_manual_independent() -> pd.DataFrame:
    """
    Load manually curated outlets (not in ESR/MT) from data/overrides/manual_independent_outlets.csv
    Returns a dataframe aligned to gold columns (name/url/media_type/etc + audit fields).
    """
    project_root = Path(__file__).resolve().parents[2]
    manual_path = project_root / "data" / "overrides" / "manual_independent_outlets.csv"

    if not manual_path.exists():
        return pd.DataFrame()

    try:
        m = pd.read_csv(manual_path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()

    # Ensure expected cols exist
    expected = [
        "id",
        "name",
        "url",
        "media_type",
        "content_type",
        "status",
        "range_type",
        "prefecture_en",
        "owner",
        "notes",
        "added_by",
        "added_at",
    ]
    for c in expected:
        if c not in m.columns:
            m[c] = ""

    # Normalize core fields
    m["name"] = m["name"].astype(str).str.strip()
    m["url"] = m["url"].astype(str).str.strip()
    m["media_type"] = m["media_type"].astype(str).str.strip().str.lower()
    m["content_type"] = m["content_type"].astype(str).str.strip().str.lower()
    m["status"] = m["status"].astype(str).str.strip().str.lower()
    m["range_type"] = m["range_type"].astype(str).str.strip().str.lower()
    m["prefecture_en"] = m["prefecture_en"].astype(str).str.strip()
    m["owner"] = m["owner"].astype(str).str.strip()
    m["notes"] = m["notes"].astype(str).str.strip()

    # Keep only rows with name + url
    m = m[(m["name"] != "") & (m["url"] != "")].copy()
    if m.empty:
        return pd.DataFrame()

    # URL key for duplicate detection
    m["_url_key"] = m["url"].map(_norm_url)

    m = m.sort_values("added_at", ascending=True)  # oldest first

    # Report duplicates inside manual file (same URL)
    dup_in_manual = m[m.duplicated(subset=["_url_key"], keep=False)].copy()
    if len(dup_in_manual) > 0:
        project_root = Path(__file__).resolve().parents[2]
        rep = project_root / "data" / "gold" / "reports"
        rep.mkdir(parents=True, exist_ok=True)
        dup_in_manual.to_csv(rep / "manual_internal_duplicates.csv", index=False, encoding="utf-8")

    # Deduplicate within manual by URL (keep latest)
    m = m.drop_duplicates(subset=["_url_key"], keep="last").copy()

    # Build gold-aligned dataframe
    out = pd.DataFrame()
    out["id"] = m["id"].astype(str).str.strip()

    # fallback: if id missing, generate deterministic ids ONLY for missing rows
    missing_mask = out["id"] == ""
    if missing_mask.any():
        out.loc[missing_mask, "id"] = [
            hashlib.sha1(f"manual|{_norm_text(n)}|{_norm_text(u)}".encode("utf-8")).hexdigest()
            for n, u in zip(
                m.loc[missing_mask, "name"].astype(str),
                m.loc[missing_mask, "url"].astype(str),
            )
        ]

    out["name"] = m["name"]
    out["url"] = m["url"]
    out["url_status"] = "ok"  # manual entries start as ok; can be overridden later
    out["fb"] = m.get("fb", "").replace("", pd.NA)
    out["x"] = m.get("x", "").replace("", pd.NA)
    out["youtube"] = m.get("youtube", "").replace("", pd.NA)
    out["notes"] = m["notes"]

    out["domain"] = m["url"].map(_extract_domain_from_url)

    out["media_type"] = m["media_type"]
    # manual intake does not collect frequency yet
    out["frequency"] = "unknown"
    out["range_type"] = m["range_type"].replace("", "unknown")
    out["prefecture_en"] = m["prefecture_en"]
    out["content_type"] = m["content_type"].replace("", "unknown")
    out["status"] = m["status"].replace("", "unknown")
    out["owner"] = m["owner"]

    # audit fields
    out["source_name"] = "manual_independent"
    out["row_id"] = out["id"]
    out["snapshot_date"] = m["added_at"].astype(str).str.slice(0, 10)
    out["url_match_type"] = "manual"
    out["url_match_detail"] = "manual_independent_outlets_csv"

    return out


def _pick_best_url(cands: pd.DataFrame) -> Tuple[str, str, str]:
    """
    Deterministic selection of 1 URL from a set of candidate websites.
    Returns (url, domain, match_detail).
    """
    # Prefer https, then shortest URL, then alphabetical
    tmp = cands.copy()
    tmp["url_norm"] = tmp["url"].astype(str).str.strip()
    tmp["is_https"] = tmp["url_norm"].str.lower().str.startswith("https://")
    tmp["url_len"] = tmp["url_norm"].str.len()

    tmp = tmp.sort_values(["is_https", "url_len", "url_norm"], ascending=[False, True, True])
    best = tmp.iloc[0]
    detail = "best_of_candidates"
    return str(best["url"]), str(best.get("domain") or ""), detail


def build_registry_gold(paths: Paths) -> Path:
    tv_path = paths.silver / "tv_silver.parquet"
    radio_path = paths.silver / "radio_silver.parquet"
    press_path = paths.silver / "press_silver.parquet"
    web_path = paths.silver / "websites_silver.parquet"

    missing = [p for p in [tv_path, radio_path, press_path, web_path] if not p.exists()]
    if missing:
        raise RuntimeError(f"Missing silver inputs: {missing}")

    tv = pd.read_parquet(tv_path)
    radio = pd.read_parquet(radio_path)
    press = pd.read_parquet(press_path)
    web = pd.read_parquet(web_path)

    # --- Standardize base tables (TV/Radio/Press) ---
    def base_select(df: pd.DataFrame) -> pd.DataFrame:
        out = pd.DataFrame()
        out["source_name"] = df.get("source_name")
        out["row_id"] = df.get("row_id")
        out["snapshot_date"] = df.get("snapshot_date")

        out["name"] = df.get("name")
        out["owner"] = df.get("owner")
        out["media_type"] = df.get("media_type")
        out["frequency"] = df.get("frequency")
        out["range_type"] = df.get("range_type")
        out["prefecture_en"] = df.get("prefecture_en")

        out["content_type"] = df.get("content_type")
        out["status"] = df.get("status")

        # URL empty for base (will be attached)
        out["url"] = pd.NA
        out["domain"] = pd.NA
        return out

    base = pd.concat([base_select(tv), base_select(radio), base_select(press)], ignore_index=True)
    # Exclude magazines from MT press (per project decision)
    base = base[~((base["source_name"] == "mt_press") & (base["media_type"] == "magazine"))].copy()


    # Stable IDs for base rows
    base["id"] = [
        _make_id(mt, n, pe, ow)
        for mt, n, pe, ow in zip(
            base["media_type"].astype(str),
            base["name"].astype(str),
            base["prefecture_en"].astype(str),
            base["owner"].astype(str),
        )
    ]

    # --- Prep websites for matching ---
    web2 = web.copy()

    # Ensure url/domain exist
    if "url" not in web2.columns:
        # older schema fallback
        if "url_raw" in web2.columns:
            web2["url"] = web2["url_raw"]
        else:
            raise RuntimeError("websites_silver needs a 'url' column.")

    web2["url"] = web2["url"].astype(str).str.strip()
    web2["domain"] = web2.get("domain")
    if "domain" not in web2.columns or web2["domain"].isna().all():
        web2["url_norm"] = web2["url"].str.lower().str.strip()
        web2["domain"] = (
            web2["url_norm"]
            .str.replace("https://", "", regex=False)
            .str.replace("http://", "", regex=False)
            .str.replace("www.", "", regex=False)
            .str.split("/", n=1).str[0]
        )

    web2["owner_norm"] = web2["owner"].apply(_norm_owner) if "owner" in web2.columns else web2.get("owner_raw", "").apply(_norm_owner)
    web2["pref_en_norm"] = web2.get("prefecture_en").apply(_norm_text) if "prefecture_en" in web2.columns else ""
    web2["name_norm"] = web2.get("name", web2.get("name_raw", "")).apply(_norm_name)

    # Base norms
    base["owner_norm"] = base["owner"].apply(_norm_owner)
    base["pref_en_norm"] = base["prefecture_en"].apply(_norm_text)
    base["name_norm"] = base["name"].apply(_norm_name)

    # --- Match URLs to base outlets ---
    matches = []

    # Pass 1: owner_norm + prefecture_en (when prefecture known on both)
    # (This is deterministic + high-precision)
    web_by_owner_pref = web2.groupby(["owner_norm", "pref_en_norm"], dropna=False)

    for idx, row in base.iterrows():
        owner_k = row["owner_norm"]
        pref_k = row["pref_en_norm"]
        best_url = None
        best_domain = None
        match_type = "no_match"
        match_detail = ""

        # only use owner+pref if pref is known (not empty/unknown)
        if owner_k and pref_k and pref_k != "unknown":
            key = (owner_k, pref_k)
            if key in web_by_owner_pref.groups:
                cands = web2.loc[web_by_owner_pref.groups[key]]
                url, domain, detail = _pick_best_url(cands)
                best_url, best_domain = url, domain
                match_type = "owner_prefecture"
                match_detail = detail

        # Pass 2: owner_norm only (if still unmatched)
        if best_url is None and owner_k:
            cands = web2[web2["owner_norm"] == owner_k]
            if len(cands) > 0:
                url, domain, detail = _pick_best_url(cands)
                best_url, best_domain = url, domain
                match_type = "owner_only"
                match_detail = detail if len(cands) == 1 else "owner_only_multi"

        # (Optional future pass: name similarity; skip in v1 for auditability)

        matches.append(
            {
                "id": row["id"],
                "base_row_id": row.get("row_id"),
                "base_source_name": row.get("source_name"),
                "matched_url": best_url,
                "matched_domain": best_domain,
                "url_match_type": match_type,
                "url_match_detail": match_detail,
            }
        )

    matches_df = pd.DataFrame(matches)

    # Attach to base
    base = base.merge(matches_df[["id", "matched_url", "matched_domain", "url_match_type", "url_match_detail"]], on="id", how="left")
    base["url"] = base["matched_url"]
    base["domain"] = base["matched_domain"]
    base = base.drop(columns=["matched_url", "matched_domain"])

    # --- Add leftover websites as web-native outlets ---
    # Mark which website domains were used by base rows
    used_domains = set(base["domain"].dropna().astype(str).str.strip().tolist())

    web_native = web2.copy()
    web_native["domain"] = web_native["domain"].astype(str).str.strip()
    web_native = web_native[~web_native["domain"].isin(used_domains)].copy()

    # Standardize web-native schema
    web_out = pd.DataFrame()
    web_out["source_name"] = web_native.get("source_name")
    web_out["row_id"] = web_native.get("row_id")
    web_out["snapshot_date"] = web_native.get("snapshot_date")

    # Name: prefer explicit name column if present, else derive from domain
    if "name" in web_native.columns:
        web_out["name"] = web_native["name"].astype(str).str.strip()
    elif "name_raw" in web_native.columns:
        web_out["name"] = web_native["name_raw"].astype(str).str.strip()
    else:
        web_out["name"] = web_native["domain"].str.split(".", n=1).str[0]

    web_out["owner"] = web_native.get("owner")
    web_out["media_type"] = "website"
    web_out["frequency"] = "unknown"
    # You asked websites default national
    web_out["range_type"] = "national"
    web_out["prefecture_en"] = web_native.get("prefecture_en")
    web_out["content_type"] = "unknown"
    web_out["status"] = "operating"
    web_out["url"] = web_native["url"]
    web_out["domain"] = web_native["domain"]

    web_out["id"] = [
        _make_id(mt, n, pe, ow)
        for mt, n, pe, ow in zip(
            web_out["media_type"].astype(str),
            web_out["name"].astype(str),
            web_out["prefecture_en"].astype(str),
            web_out["owner"].astype(str),
        )
    ]

    web_out["url_match_type"] = "self"
    web_out["url_match_detail"] = "websites_silver_unmatched_domain"

    # --- Final registry ---
    registry = pd.concat([base, web_out], ignore_index=True)

    # --- Add manual / independent outlets (if any) ---
    manual = _load_manual_independent()
    if manual is not None and not manual.empty:
        # Duplicate detection vs existing registry (by normalized URL key):
        existing_url_keys = set(registry["url"].map(_norm_url).astype(str).tolist())
        manual["_url_key"] = manual["url"].map(_norm_url)

        dup_manual = manual[manual["_url_key"].isin(existing_url_keys)].copy()
        manual = manual[~manual["_url_key"].isin(existing_url_keys)].copy()

        # Save a report so skips are auditable
        if len(dup_manual) > 0:
            report_dir = paths.gold / "reports"
            report_dir.mkdir(parents=True, exist_ok=True)
            dup_manual.to_csv(report_dir / "manual_skipped_duplicates.csv", index=False, encoding="utf-8")

        manual = manual.drop(columns=["_url_key"], errors="ignore")
        registry = pd.concat([registry, manual], ignore_index=True)

    # keep your existing stable dedupe for accidental repeats inside sources
    registry = registry.drop_duplicates(subset=["source_name", "snapshot_date", "row_id"], keep="first").copy()


    # Ensure override-ready columns exist in Gold
    if "url_status" not in registry.columns:
        registry["url_status"] = "ok"

    for c in ["fb", "x", "youtube", "notes"]:
        if c not in registry.columns:
            registry[c] = pd.NA

    # Drop any duplicate column names (pyarrow cannot write them)
    registry = registry.loc[:, ~registry.columns.duplicated()]

    # Keep only prefecture_en for outputs (you can keep raw cols in silver/audit)
    # Ensure stable column order
    final_cols = [
        "id",
        "name",
        "url",
        "url_status",
        "fb",
        "x",
        "youtube",
        "notes",
        "domain",
        "media_type",
        "frequency",
        "range_type",
        "prefecture_en",
        "content_type",
        "status",
        "owner",
        # audit
        "source_name",
        "row_id",
        "snapshot_date",
        "url_match_type",
        "url_match_detail",
    ]
    for c in final_cols:
        if c not in registry.columns:
            registry[c] = pd.NA
    registry = registry[final_cols]

    paths.gold.mkdir(parents=True, exist_ok=True)

    out_path = paths.gold / "registry_gold.parquet"
    registry.to_parquet(out_path, index=False)

    # Save match audit table
    matches_path = paths.gold / "registry_gold_url_matches.parquet"
    matches_df.to_parquet(matches_path, index=False)

    return out_path

