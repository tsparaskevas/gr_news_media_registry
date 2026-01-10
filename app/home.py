from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional, Tuple

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]  # gr_news_media_registry/
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.demo import is_demo_mode

# Must be called before any st.* output
st.set_page_config(page_title="Greek News Media Registry", layout="wide")

# Hide pages in Streamlit Cloud demo (read-only exploration)
if is_demo_mode():
    from app.demo_pages import apply_demo_page_visibility
    apply_demo_page_visibility(PROJECT_ROOT)
    st.info("🔒 Demo mode: only Final Registry and Map pages are shown. Other pages are hidden in the demo.")

from src.config import get_paths
paths = get_paths(PROJECT_ROOT)

@st.cache_data(show_spinner=False)
def _read_csv_or_parquet(csv_path: Path, parquet_path: Path) -> pd.DataFrame:
    if csv_path.exists():
        return pd.read_csv(csv_path, dtype=str).fillna("")
    if parquet_path.exists():
        return pd.read_parquet(parquet_path).fillna("")
    return pd.DataFrame()


def _file_mtime(p: Path) -> Optional[str]:
    if not p.exists():
        return None
    ts = p.stat().st_mtime
    # Show local time; Streamlit server time is fine for relative diagnostics.
    return pd.to_datetime(ts, unit="s").strftime("%Y-%m-%d %H:%M:%S")


def _count_if(df: pd.DataFrame, col: str, value: str) -> int:
    if df.empty or col not in df.columns:
        return 0
    s = df[col].astype(str).str.strip().str.lower()
    return int((s == value).sum())


def _norm(s: pd.Series) -> pd.Series:
    return s.astype(str).fillna("").str.strip().str.lower()


@st.cache_data(show_spinner=False)
def _compute_gold_metrics(gold_path: Path) -> dict:
    if not gold_path.exists():
        return {
            "gold_rows": 0,
            "in_scope_rows": 0,
            "needs_content_type": 0,
            "needs_status": 0,
            "manual_rows": 0,
        }

    g = pd.read_parquet(gold_path).fillna("")

    gold_rows = len(g)

    status = _norm(g.get("status", pd.Series([""] * len(g))))
    ct = _norm(g.get("content_type", pd.Series([""] * len(g))))
    url_status = _norm(g.get("url_status", pd.Series([""] * len(g))))
    url = _norm(g.get("url", pd.Series([""] * len(g))))
    has_url = (url != "") & (url != "nan") & (url != "<na>")

    # Review queue (in scope):
    # Rows that are *eligible* to become part of the published editorial registries (news/sports), once reviewed. What's included:
    # - operating
    # - has a URL
    # - url_status is ok/blank (i.e., not explicitly rejected: broken/paywalled/no_website)
    # - content_type is editorial or unknown (news/sports/blank/unknown)
    is_operating = status == "operating"
    scope_ct = ct.isin(["", "unknown"])
    scope_url_ok = url_status.isin(["", "ok"])  # allow blank/ok; review page can set others
    in_scope = is_operating & scope_ct & scope_url_ok & has_url

    needs_content_type = in_scope & (~ct.isin(["news", "sports", "other"]))
    needs_status = in_scope & (~status.isin(["operating", "not_operating", "not_found"]))
    # Reasons rows are NOT eligible for the review queue / final publishing
    not_operating = status == "not_operating"
    not_found = status == "not_found"
    missing_url = ~has_url

    rejected_url = url_status.isin(["no_website", "broken", "paywalled"])
    non_editorial = ct == "other"

    manual_rows = 0
    if "source_name" in g.columns:
        manual_rows = int((_norm(g["source_name"]) == "manual_independent").sum())

    return {
        "gold_rows": int(gold_rows),
        "review_queue_rows": int(in_scope.sum()),
        "needs_content_type": int(needs_content_type.sum()),
        "needs_status": int(needs_status.sum()),
        "manual_rows": int(manual_rows),

        # blockers / exclusions
        "blocked_not_operating": int(not_operating.sum()),
        "blocked_not_found": int(not_found.sum()),
        "blocked_missing_url": int(missing_url.sum()),
        "blocked_rejected_url": int(rejected_url.sum()),
        "blocked_non_editorial": int(non_editorial.sum()),
    }


def _published_paths(paths) -> dict:
    pub = paths.published
    return {
        "editorial_outlets_csv": pub / "final_outlets.csv",
        "editorial_outlets_parquet": pub / "final_outlets.parquet",
        "news_outlets_csv": pub / "final_news_outlets.csv",
        "news_outlets_parquet": pub / "final_news_outlets.parquet",
        "sports_outlets_csv": pub / "final_sports_outlets.csv",
        "sports_outlets_parquet": pub / "final_sports_outlets.parquet",
        "editorial_urls_csv": pub / "final_urls.csv",
        "editorial_urls_parquet": pub / "final_urls.parquet",
        "news_urls_csv": pub / "final_news_urls.csv",
        "news_urls_parquet": pub / "final_news_urls.parquet",
        "sports_urls_csv": pub / "final_sports_urls.csv",
        "sports_urls_parquet": pub / "final_sports_urls.parquet",
        # Back-compat (optional)
        "legacy_registry_csv": pub / "final_registry.csv",
        "legacy_registry_parquet": pub / "final_registry.parquet",
    }


# ---- UI ----
project_root = PROJECT_ROOT
pub = _published_paths(paths)

st.title("Greek News Media Registry")

st.markdown(
    """
**Greek News Media Registry** is a transparent, reproducible system for building a registry of Greek media outlets.

It ingests authoritative sources (ESR for TV/radio, MT for press/websites), normalizes geography and metadata,
supports human-in-the-loop corrections via overrides, and publishes auditable outputs.

**Published outputs (Option B)**  
- **Editorial registry**: operating outlets with **news OR sports** content and an active website  
- Separate **News-only** and **Sports-only** registries  
- A deduped **URL registry** that shows when one site is used across multiple media types
"""
)

c0, c1 = st.columns([1, 5])
with c0:
    if st.button("Force reload", help="Clear Streamlit caches and reload the page"):
        st.cache_data.clear()
        st.rerun()
with c1:
    st.caption(f"Project root: {project_root}")

st.divider()

# ---- Status metrics ----
gold_metrics = _compute_gold_metrics(paths.gold / "registry_gold.parquet")

editorial_df = _read_csv_or_parquet(pub["editorial_outlets_csv"], pub["editorial_outlets_parquet"])
news_df = _read_csv_or_parquet(pub["news_outlets_csv"], pub["news_outlets_parquet"])
sports_df = _read_csv_or_parquet(pub["sports_outlets_csv"], pub["sports_outlets_parquet"])

urls_editorial_df = _read_csv_or_parquet(pub["editorial_urls_csv"], pub["editorial_urls_parquet"])
urls_news_df = _read_csv_or_parquet(pub["news_urls_csv"], pub["news_urls_parquet"])
urls_sports_df = _read_csv_or_parquet(pub["sports_urls_csv"], pub["sports_urls_parquet"])

st.subheader("Current status")

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Gold rows (all)", f"{gold_metrics['gold_rows']:,}")
m2.metric("Review queue (needs content_type)", f"{gold_metrics['review_queue_rows']:,}")
m3.metric("Manual entries (gold)", f"{gold_metrics['manual_rows']:,}")
m4.metric("Final editorial (published)", f"{len(editorial_df):,}")
m5.metric("Final news (published)", f"{len(news_df):,}")

m6, m7, m8, m9, m10 = st.columns(5)
m6.metric("Final sports (published)", f"{len(sports_df):,}")
m7.metric("Unique URLs (editorial)", f"{len(urls_editorial_df):,}")
m8.metric("Unique URLs (news)", f"{len(urls_news_df):,}")
m9.metric("Unique URLs (sports)", f"{len(urls_sports_df):,}")
m10.metric("URL registry rows with manual", f"{_count_if(urls_editorial_df, 'has_manual', 'true'):,}" if not urls_editorial_df.empty else "—")

st.markdown("### What’s blocking publishing (gold)")

b1, b2, b3, b4, b5 = st.columns(5)
b1.metric("Not operating", f"{gold_metrics['blocked_not_operating']:,}")
b2.metric("Not found", f"{gold_metrics['blocked_not_found']:,}")
b3.metric("Missing URL", f"{gold_metrics['blocked_missing_url']:,}")
b4.metric("URL rejected (no/broken/paywalled)", f"{gold_metrics['blocked_rejected_url']:,}")
b5.metric("Non-editorial (content_type=other)", f"{gold_metrics['blocked_non_editorial']:,}")

st.caption(
    "Definitions: Editorial = news or sports. Published outputs require: operating + editorial + url_status=ok + url present."
)

st.divider()

# ---- “Last published” info ----
st.subheader("Last publish timestamps")

ts_rows = []
for label, key in [
    ("Editorial outlets", "editorial_outlets_parquet"),
    ("News outlets", "news_outlets_parquet"),
    ("Sports outlets", "sports_outlets_parquet"),
    ("Editorial URLs", "editorial_urls_parquet"),
    ("News URLs", "news_urls_parquet"),
    ("Sports URLs", "sports_urls_parquet"),
]:
    p = pub[key]
    ts_rows.append({"Artifact": label, "File": p.name, "Last modified": _file_mtime(p) or "—"})

st.dataframe(pd.DataFrame(ts_rows), width="stretch", hide_index=True)

st.divider()

# ---- How to use ----
st.subheader("How to use")

st.markdown(
    """
1) **Pipeline**: refresh snapshots (optional) and rebuild Bronze → Silver → Gold, then **Publish**  
2) **Prefectures**: resolve new / unknown prefecture aliases  
3) **Review overrides**: verify ambiguous outlets (URLs, status, content type, socials)  
4) **Final registry**: inspect outputs, exclusions, URL registry, and domain patterns  
5) **Map**: view geographic distribution by media type / editorial bucket  
6) **Manual intake**: add independent outlets missing from official registries
"""
)

st.info(
    "Tip: Start with the Review Overrides queue: operating outlets with a URL and url_status ok, "
    "but missing/unknown content_type. Label as news, sports, or other."
)

# ---- Quick links / downloads (optional convenience) ----
st.subheader("Quick downloads")

d1, d2, d3 = st.columns(3)

with d1:
    if pub["editorial_outlets_csv"].exists():
        st.download_button(
            "Download Editorial outlets (CSV)",
            data=pub["editorial_outlets_csv"].read_bytes(),
            file_name="final_outlets.csv",
            mime="text/csv",
            key="dl_editorial_outlets",
        )
with d2:
    if pub["news_outlets_csv"].exists():
        st.download_button(
            "Download News outlets (CSV)",
            data=pub["news_outlets_csv"].read_bytes(),
            file_name="final_news_outlets.csv",
            mime="text/csv",
            key="dl_news_outlets",
        )
with d3:
    if pub["sports_outlets_csv"].exists():
        st.download_button(
            "Download Sports outlets (CSV)",
            data=pub["sports_outlets_csv"].read_bytes(),
            file_name="final_sports_outlets.csv",
            mime="text/csv",
            key="dl_sports_outlets",
        )

d4, d5, d6 = st.columns(3)
with d4:
    if pub["editorial_urls_csv"].exists():
        st.download_button(
            "Download Editorial URLs (CSV)",
            data=pub["editorial_urls_csv"].read_bytes(),
            file_name="final_urls.csv",
            mime="text/csv",
            key="dl_editorial_urls",
        )
with d5:
    if pub["news_urls_csv"].exists():
        st.download_button(
            "Download News URLs (CSV)",
            data=pub["news_urls_csv"].read_bytes(),
            file_name="final_news_urls.csv",
            mime="text/csv",
            key="dl_news_urls",
        )
with d6:
    if pub["sports_urls_csv"].exists():
        st.download_button(
            "Download Sports URLs (CSV)",
            data=pub["sports_urls_csv"].read_bytes(),
            file_name="final_sports_urls.csv",
            mime="text/csv",
            key="dl_sports_urls",
        )

st.divider()

st.subheader("Methodology & provenance (recommended)")

st.markdown(
    """
- Raw source snapshots are stored under `data/sources/` (date-stamped)  
- Silver tables under `data/silver/`  
- Gold registry under `data/gold/registry_gold.parquet`  
- Overrides under `data/overrides/`  
- Published artifacts under `data/published/`  
"""
)

