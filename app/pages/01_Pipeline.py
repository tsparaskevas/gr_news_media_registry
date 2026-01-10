import io
import sys
from pathlib import Path
from contextlib import redirect_stdout, redirect_stderr

import pandas as pd
import streamlit as st

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import get_paths
from src.io_snapshots import download_snapshot

# Bronze builders
from src.sources.esr_tv import build_esr_tv_bronze
from src.sources.esr_radio import build_esr_radio_bronze
from src.sources.mt_press import build_mt_press_bronze
from src.sources.mt_websites import build_mt_websites_bronze

# Silver builders
from src.silver.tv import build_tv_silver
from src.silver.radio import build_radio_silver
from src.silver.press import build_press_silver
from src.silver.websites import build_websites_silver

# Gold builder
from src.gold.registry import build_registry_gold

# Overrides
from src.overrides.outlet_overrides import load_outlet_overrides, apply_outlet_overrides

# Demo mode
from app.demo import is_demo_mode

st.set_page_config(page_title="Pipeline", layout="wide")

if is_demo_mode():
    st.warning("Demo mode: read-only. Pipeline rebuild and snapshot refresh are disabled.")
    st.stop()

def _capture_logs(fn):
    buf = io.StringIO()
    ok = True
    err = None
    with redirect_stdout(buf), redirect_stderr(buf):
        try:
            result = fn()
        except Exception as e:
            ok = False
            err = e
            result = None
    return ok, result, buf.getvalue(), err


def _latest_snapshot_date(group_dir: Path) -> str:
    if not group_dir.exists():
        return "(none)"
    dates = sorted([p.name for p in group_dir.iterdir() if p.is_dir() and p.name[:4].isdigit()])
    return dates[-1] if dates else "(none)"


def _count_rows(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        if path.suffix.lower() == ".parquet":
            return len(pd.read_parquet(path))
        if path.suffix.lower() == ".csv":
            return sum(1 for _ in open(path, "r", encoding="utf-8")) - 1
    except Exception:
        return -1
    return -1


def publish_final_registry(paths) -> Path:
    """
    Publish final registries based on Gold + Overrides (Option B):
      - status == operating
      - content_type in {news, sports}   (editorial)
      - url_status == ok
      - url is not blank

    Outputs (CSV + parquet):
      - final_outlets.*            (editorial: news + sports)
      - final_news_outlets.*       (news only)
      - final_sports_outlets.*     (sports only)
      - final_urls.*               (editorial URL registry; deduped)
      - final_news_urls.*          (news URL registry; deduped)
      - final_sports_urls.*        (sports URL registry; deduped)
    """
    gold_path = paths.gold / "registry_gold.parquet"
    if not gold_path.exists():
        raise RuntimeError("Missing data/gold/registry_gold.parquet. Build Gold first.")

    g = pd.read_parquet(gold_path)

    # Apply overrides (so your manual edits are reflected)
    overrides_path = paths.overrides / "outlet_overrides.csv"
    ov = load_outlet_overrides(overrides_path)
    g = apply_outlet_overrides(g, ov)

    # Normalize filters
    def _norm(s):
        return s.astype(str).str.strip().str.lower()

    status = _norm(g["status"])
    ct = _norm(g["content_type"])
    url_status = _norm(g.get("url_status", pd.Series(["ok"] * len(g))))
    url_raw = g.get("url")
    url = url_raw.fillna("").astype(str).str.strip().str.lower()

    has_url = (~url_raw.isna()) & (~url.isin(["", "nan", "<na>", "none"]))

    final_editorial = g[
        (status == "operating")
        & (ct.isin(["news", "sports"]))
        & (url_status == "ok")
        & (has_url)
    ].copy()

    final_news = g[
        (status == "operating")
        & (ct == "news")
        & (url_status == "ok")
        & (has_url)
    ].copy()

    final_sports = g[
        (status == "operating")
        & (ct == "sports")
        & (url_status == "ok")
        & (has_url)
    ].copy()

    # Keep preferred published columns
    cols = [
        "id",
        "name",
        "url",
        "media_type",
        "frequency",
        "range_type",
        "prefecture_en",
        "content_type",
        "status",
        "url_status",
        "fb",
        "x",
        "youtube",
        "owner",
        "source_name",
        "row_id",
        "snapshot_date",
        "url_match_type",
        "url_match_detail",
        "notes",
    ]

    def _select_cols(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        for c in cols:
            if c not in df.columns:
                df[c] = pd.NA
        return df[cols]

    final_editorial = _select_cols(final_editorial)
    final_news = _select_cols(final_news)
    final_sports = _select_cols(final_sports)

    def _base_domain(u: object) -> str:
        u = str(u or "").strip().lower()
        u = u.replace("https://", "").replace("http://", "")
        host = u.split("/")[0].strip()
        if not host:
            return ""
        for pref in ("www.", "www2.", "m."):
            if host.startswith(pref):
                host = host[len(pref):]
        parts = host.split(".")
        if len(parts) <= 2:
            return host
        if parts[-1] == "gr":
            return ".".join(parts[-2:])
        if parts[-2] in {"co", "com", "net", "org"} and len(parts) >= 3:
            return ".".join(parts[-3:])
        return ".".join(parts[-2:])


    def _canonical_url(u: object) -> str:
        d = _base_domain(u)
        return f"https://{d}" if d else ""

    paths.published.mkdir(parents=True, exist_ok=True)

    def _write_outlets(df: pd.DataFrame, stem: str) -> Tuple[Path, Path]:
        out_csv = paths.published / f"{stem}.csv"
        out_parquet = paths.published / f"{stem}.parquet"

        df = df.drop_duplicates().copy()
        df = df.drop_duplicates(subset=["id"], keep="first").copy()

        df.to_csv(out_csv, index=False, encoding="utf-8")
        df.to_parquet(out_parquet, index=False)
        return out_csv, out_parquet

    # 1) OUTLETS artifacts
    out_outlets_csv, out_outlets_parquet = _write_outlets(final_editorial, "final_outlets")
    _write_outlets(final_news, "final_news_outlets")
    _write_outlets(final_sports, "final_sports_outlets")

    # Back-compat: keep old filenames pointing to editorial (news + sports)
    (paths.published / "final_registry.csv").write_bytes(out_outlets_csv.read_bytes())
    (paths.published / "final_registry.parquet").write_bytes(out_outlets_parquet.read_bytes())

    def _uniq_sorted(series):
        vals = [v for v in series.dropna().astype(str).str.strip().tolist() if v and v.lower() not in {"nan", "<na>", "none"}]
        return sorted(set(vals))

    def _build_url_registry(df: pd.DataFrame) -> pd.DataFrame:
        df2 = df.copy()
        df2["domain"] = df2["url"].apply(_base_domain)
        df2["canonical_url"] = df2["url"].apply(_canonical_url)

        url_registry = (
            df2[df2["canonical_url"] != ""]
            .groupby("canonical_url", as_index=False)
            .agg(
                domain=("domain", "first"),
                outlet_count=("id", "count"),
                outlet_ids=("id", lambda s: _uniq_sorted(s)),
                outlet_names=("name", lambda s: _uniq_sorted(s)[:50]),
                media_types=("media_type", lambda s: _uniq_sorted(s)),
                owners=("owner", lambda s: _uniq_sorted(s)[:50]),
                prefectures=("prefecture_en", lambda s: _uniq_sorted(s)[:100]),
                source_names=("source_name", lambda s: _uniq_sorted(s)),
                has_manual=("source_name", lambda s: "manual_independent" in _uniq_sorted(s)),
                fb_any=("fb", lambda s: next((x for x in _uniq_sorted(s) if x), "")),
                x_any=("x", lambda s: next((x for x in _uniq_sorted(s) if x), "")),
                youtube_any=("youtube", lambda s: next((x for x in _uniq_sorted(s) if x), "")),
            )
        )

        mt = url_registry["media_types"].apply(lambda xs: xs if isinstance(xs, list) else [])
        url_registry["has_tv"] = mt.apply(lambda xs: "tv" in xs)
        url_registry["has_radio"] = mt.apply(lambda xs: "radio" in xs)
        url_registry["has_newspaper"] = mt.apply(lambda xs: "newspaper" in xs)
        url_registry["has_website_entity"] = mt.apply(lambda xs: "website" in xs)

        url_registry["web_native"] = url_registry["has_website_entity"] & ~(
            url_registry["has_tv"] | url_registry["has_radio"] | url_registry["has_newspaper"]
        )
        return url_registry

    def _write_urls(url_registry: pd.DataFrame, stem: str) -> None:
        out_urls_csv = paths.published / f"{stem}.csv"
        out_urls_parquet = paths.published / f"{stem}.parquet"
        url_registry.to_csv(out_urls_csv, index=False, encoding="utf-8")
        url_registry.to_parquet(out_urls_parquet, index=False)

    # 2) URL registry artifacts (deduped by canonical_url)
    urls_editorial = _build_url_registry(final_editorial)
    urls_news = _build_url_registry(final_news)
    urls_sports = _build_url_registry(final_sports)

    _write_urls(urls_editorial, "final_urls")
    _write_urls(urls_news, "final_news_urls")
    _write_urls(urls_sports, "final_sports_urls")

    return out_outlets_csv


# ---------- UI ----------
root = PROJECT_ROOT
paths = get_paths(root)

st.title("Pipeline")
st.caption("Refresh authoritative sources → build Bronze/Silver/Gold → review overrides → publish final registry.")

# Status overview
with st.container():
    st.subheader("Current status")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("ESR snapshot date", _latest_snapshot_date(paths.sources / "esr"))
    c2.metric("MT snapshot date", _latest_snapshot_date(paths.sources / "mt_media"))
    c3.metric("Gold rows", _count_rows(paths.gold / "registry_gold.parquet"))
    c4.metric("Published rows", _count_rows(paths.published / "final_registry.csv"))

    st.write("")


# ---------- Step 1: Refresh snapshots ----------
st.subheader("1) Refresh snapshots")
st.write(
    "Downloads the latest source files and stores them under `data/sources/<source_group>/<YYYY-MM-DD>/...` "
    "to keep the pipeline auditable and reproducible."
)

colA, colB = st.columns([1, 2])
with colA:
    do_refresh = st.button("Refresh ESR + MT snapshots", type="primary")

refresh_logs = st.expander("Show logs (refresh)", expanded=False)

if do_refresh:
    def _refresh():
        # ESR
        download_snapshot(
            base_sources_dir=paths.sources,
            source_group="esr",
            source_name="esr_tv_national",
            url="https://www.esr.gr/wp-content/uploads/tve.xls",
            filename="tve.xls",
        )
        download_snapshot(
            base_sources_dir=paths.sources,
            source_group="esr",
            source_name="esr_tv_regional",
            url="https://www.esr.gr/wp-content/uploads/tvtp.xls",
            filename="tvtp.xls",
        )
        download_snapshot(
            base_sources_dir=paths.sources,
            source_group="esr",
            source_name="esr_radio",
            url="https://www.esr.gr/wp-content/uploads/bnl.xlsx",
            filename="bnl.xlsx",
        )

        # MT
        download_snapshot(
            base_sources_dir=paths.sources,
            source_group="mt_media",
            source_name="mt_press",
            url="http://mt.media.gov.gr/submissions/MET/public/export",
            filename="press_export.xls",
        )
        download_snapshot(
            base_sources_dir=paths.sources,
            source_group="mt_media",
            source_name="mt_websites",
            url="http://mt.media.gov.gr/submissions/MHT/public/export",
            filename="websites_export.xls",
        )

        print("OK: refreshed ESR + MT snapshots")

    ok, _, logs, err = _capture_logs(_refresh)
    if ok:
        st.success("Snapshots refreshed.")
    else:
        st.error(f"Refresh failed: {err}")
    with refresh_logs:
        st.code(logs or "(no logs)")


st.divider()

# ---------- Step 2: Build Bronze ----------
st.subheader("2) Build Bronze")
st.write("Parses the downloaded source files into raw, structured Bronze tables (one file per source).")

colA, colB = st.columns([1, 2])
with colA:
    do_bronze = st.button("Build all Bronze", type="primary")
bronze_logs = st.expander("Show logs (bronze)", expanded=False)

if do_bronze:
    def _bronze():
        out1 = build_esr_tv_bronze(paths)
        print("Wrote:", out1)
        out2 = build_esr_radio_bronze(paths)
        print("Wrote:", out2)
        out3 = build_mt_press_bronze(paths)
        print("Wrote:", out3)
        out4 = build_mt_websites_bronze(paths)
        print("Wrote:", out4)
        print("OK: built all Bronze")

    ok, _, logs, err = _capture_logs(_bronze)
    if ok:
        st.success("Bronze built.")
    else:
        st.error(f"Bronze build failed: {err}")
    with bronze_logs:
        st.code(logs or "(no logs)")


st.divider()

# ---------- Step 3: Build Silver ----------
st.subheader("3) Build Silver")
st.write(
    "Builds normalized Silver tables (clean columns + canonical prefectures where aliases exist). "
    "Unmatched prefecture aliases can be handled in the Prefectures page."
)

colA, colB = st.columns([1, 2])
with colA:
    do_silver = st.button("Build all Silver", type="primary")
silver_logs = st.expander("Show logs (silver)", expanded=False)

if do_silver:
    def _silver():
        out1 = build_tv_silver(paths)
        print("Wrote:", out1)
        out2 = build_radio_silver(paths)
        print("Wrote:", out2)
        out3 = build_press_silver(paths)
        print("Wrote:", out3)
        out4 = build_websites_silver(paths)
        print("Wrote:", out4)
        print("OK: built all Silver")

    ok, _, logs, err = _capture_logs(_silver)
    if ok:
        st.success("Silver built.")
    else:
        st.error(f"Silver build failed: {err}")
    with silver_logs:
        st.code(logs or "(no logs)")


st.divider()

# ---------- Step 4: Build Gold ----------
st.subheader("4) Build Gold registry")
st.write(
    "Combines Silver sources into a single auditable Gold registry, attaches websites where possible, "
    "and keeps provenance columns for reproducibility."
)

colA, colB = st.columns([1, 2])
with colA:
    do_gold = st.button("Build Gold", type="primary")
gold_logs = st.expander("Show logs (gold)", expanded=False)

if do_gold:
    def _gold():
        out = build_registry_gold(paths)
        print("Wrote:", out)
        print("OK: built Gold")

    ok, _, logs, err = _capture_logs(_gold)
    if ok:
        st.success("Gold built.")
    else:
        st.error(f"Gold build failed: {err}")
    with gold_logs:
        st.code(logs or "(no logs)")


st.divider()

# ---------- Step 5: Publish ----------
st.subheader("5) Publish final registry")
st.write(
    "Exports final registries for downstream use, applying Overrides and filtering to:\n"
    "- status = operating\n"
    "- content_type = news OR sports (editorial)\n"
    "- url_status = ok\n"
    "- url present\n"
    "\nAlso publishes separate News-only and Sports-only artifacts."
)

colA, colB = st.columns([1, 2])
with colA:
    do_publish = st.button("Publish final_registry.csv", type="primary")
publish_logs = st.expander("Show logs (publish)", expanded=False)

if do_publish:
    def _pub():
        out = publish_final_registry(paths)
        print("Wrote:", out)
        print("OK: published final registry")

    ok, _, logs, err = _capture_logs(_pub)
    if ok:
        st.success("Published final registry.")
    else:
        st.error(f"Publish failed: {err}")
    with publish_logs:
        st.code(logs or "(no logs)")

