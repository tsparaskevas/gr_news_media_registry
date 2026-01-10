import sys
from pathlib import Path

import io
from contextlib import redirect_stdout, redirect_stderr

import pandas as pd
import streamlit as st

from src.overrides.outlet_overrides import load_outlet_overrides, apply_outlet_overrides

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import get_paths

st.set_page_config(page_title="Final Registry", layout="wide")

root = PROJECT_ROOT
paths = get_paths(root)

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


def publish_final_registry(paths) -> Path:
    gold_path = paths.gold / "registry_gold.parquet"
    if not gold_path.exists():
        raise RuntimeError("Missing data/gold/registry_gold.parquet. Build Gold first.")

    g = pd.read_parquet(gold_path)

    overrides_path = paths.overrides / "outlet_overrides.csv"
    ov = load_outlet_overrides(overrides_path)
    g = apply_outlet_overrides(g, ov)

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

    # ---- DEBUG: manual rows visibility ----
    manual_mask = g.get("source_name", pd.Series([""] * len(g))).astype(str).str.strip() == "manual_independent"
    manual_all = g[manual_mask].copy()

    if len(manual_all) > 0:
        # How many manual rows pass the strict final filter?
        manual_in_final = final_editorial[final_editorial.get("source_name", "") == "manual_independent"].copy()

        print("MANUAL rows (gold after overrides):", len(manual_all))
        print("MANUAL rows in FINAL:", len(manual_in_final))

        if len(manual_in_final) == 0:
            # Show why they failed
            dbg = manual_all.copy()
            dbg["status_norm"] = status[manual_mask].values
            dbg["ct_norm"] = ct[manual_mask].values
            dbg["url_status_norm"] = url_status[manual_mask].values
            dbg["has_url"] = has_url[manual_mask].values
            print("MANUAL failure breakdown:")
            print("status_norm:", dbg["status_norm"].value_counts(dropna=False).to_dict())
            print("ct_norm:", dbg["ct_norm"].value_counts(dropna=False).to_dict())
            print("url_status_norm:", dbg["url_status_norm"].value_counts(dropna=False).to_dict())
            print("has_url:", dbg["has_url"].value_counts(dropna=False).to_dict())

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
        # For .gr: keep 2 labels normally (ert.gr), but keep 3 when it is a second-level domain like com.gr, net.gr, org.gr, edu.gr, gov.gr
        if parts[-1] == "gr":
            if len(parts) >= 3 and parts[-2] in {"com", "net", "org", "edu", "gov"}:
                return ".".join(parts[-3:])
            return ".".join(parts[-2:])
        if parts[-2] in {"co", "com", "net", "org"} and len(parts) >= 3:
            return ".".join(parts[-3:])
        return ".".join(parts[-2:])


#    def _canonical_url(u: object) -> str:
#        d = _base_domain(u)
#        return f"https://{d}" if d else ""

    def _canonical_url(u: object) -> str:
        u = str(u or "").strip().lower()
        if not u:
            return ""
        u = u.replace("http://", "").replace("https://", "")
        host = u.split("/", 1)[0].strip()
        if not host:
            return ""
        for pref in ("www.", "www2.", "m."):
            if host.startswith(pref):
                host = host[len(pref):]
        return f"https://{host}"


    paths.published.mkdir(parents=True, exist_ok=True)
    
    def _write_outlets(df: pd.DataFrame, stem: str) -> Path:
        out_csv = paths.published / f"{stem}.csv"
        out_parquet = paths.published / f"{stem}.parquet"

        df = df.drop_duplicates().copy()
        df = df.drop_duplicates(subset=["id"], keep="first").copy()

        df.to_csv(out_csv, index=False, encoding="utf-8")
        df.to_parquet(out_parquet, index=False)
        return out_csv

    # 1) OUTLETS artifacts (Option B)
    out_outlets_csv = _write_outlets(final_editorial, "final_outlets")
    _write_outlets(final_news, "final_news_outlets")
    _write_outlets(final_sports, "final_sports_outlets")

    # Back-compat: final_registry.* points to editorial (news + sports)
    (paths.published / "final_registry.csv").write_bytes(out_outlets_csv.read_bytes())
    (paths.published / "final_registry.parquet").write_bytes((paths.published / "final_outlets.parquet").read_bytes())

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
                outlet_names=("name", lambda s: _uniq_sorted(s)[:20]),
                media_types=("media_type", lambda s: _uniq_sorted(s)),
                owners=("owner", lambda s: _uniq_sorted(s)[:20]),
                prefectures=("prefecture_en", lambda s: _uniq_sorted(s)[:50]),
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
        out_csv = paths.published / f"{stem}.csv"
        out_parquet = paths.published / f"{stem}.parquet"
        url_registry.to_csv(out_csv, index=False, encoding="utf-8")
        url_registry.to_parquet(out_parquet, index=False)

    # 2) URL registry artifacts (Option B)
    _write_urls(_build_url_registry(final_editorial), "final_urls")
    _write_urls(_build_url_registry(final_news), "final_news_urls")
    _write_urls(_build_url_registry(final_sports), "final_sports_urls")

    return out_outlets_csv


@st.cache_data(show_spinner=False)
def compute_progress(paths):
    gold_path = paths.gold / "registry_gold.parquet"
    if not gold_path.exists():
        return None

    g = pd.read_parquet(gold_path)

    overrides_path = paths.overrides / "outlet_overrides.csv"
    ov = load_outlet_overrides(overrides_path)
    g = apply_outlet_overrides(g, ov)

    def _norm(s):
        return s.astype(str).str.strip().str.lower()

    status = _norm(g.get("status", pd.Series([""] * len(g))))
    ct = _norm(g.get("content_type", pd.Series([""] * len(g))))
    url_status = _norm(g.get("url_status", pd.Series(["ok"] * len(g))))
    url_raw = g.get("url", pd.Series([pd.NA] * len(g)))
    url = url_raw.fillna("").astype(str).str.strip().str.lower()
    has_url = (~url_raw.isna()) & (~url.isin(["", "nan", "<na>", "none"]))

    is_operating = status == "operating"
    is_editorial = ct.isin(["news", "sports"])
    is_url_ok = url_status == "ok"

    in_final = is_operating & is_editorial & is_url_ok & has_url

    # Scope (what you said you want to work on now)
    scope_ct = ct.isin(["", "unknown", "news", "sports"])
    scope_status = status.isin(["", "unknown", "operating"])
    in_scope = scope_ct & scope_status

    # What blocks "final" (editorial = news OR sports)
    missing_url = in_scope & is_operating & is_editorial & is_url_ok & (~has_url)
    needs_ct = in_scope & is_operating & (~ct.isin(["news", "sports", "other"]))  # blank/unknown/anything else
    needs_status = in_scope & (~status.isin(["operating", "not_operating", "not_found"]))  # blank/unknown/other

    # Explicit exclusions (quick-mark outcomes)
    paywalled = in_scope & (url_status == "paywalled")
    no_website = in_scope & (url_status == "no_website")
    broken_url = in_scope & (url_status == "broken")
    not_operating = in_scope & (status == "not_operating")
    not_found = in_scope & (status == "not_found")

    # Not editorial means content_type is explicitly "other"
    not_editorial = in_scope & (ct == "other")

    return {
        "gold_rows": len(g),
        "scope_rows": int(in_scope.sum()),
        "final_rows": int(in_final.sum()),
        "missing_url": int(missing_url.sum()),
        "needs_content_type": int(needs_ct.sum()),
        "needs_status": int(needs_status.sum()),
        "paywalled": int(paywalled.sum()),
        "no_website": int(no_website.sum()),
        "broken_url": int(broken_url.sum()),
        "not_operating": int(not_operating.sum()),
        "not_found": int(not_found.sum()),
        "not_editorial": int(not_editorial.sum()),
    }


st.title("Final Registry")
st.caption("Preview and quality checks for published final registries: Editorial (operating + news/sports + website), plus News-only and Sports-only views.")

colA, colB = st.columns([1, 3])
with colA:
    do_publish = st.button("Re-publish now", type="primary")
publish_logs = st.expander("Show logs (publish)", expanded=False)

if do_publish:
    ok, out, logs, err = _capture_logs(lambda: publish_final_registry(paths))
    if ok:
        st.success("Published final_registry.csv (and parquet).")
        st.cache_data.clear()  # ensure page reloads the new file
    else:
        st.error(f"Publish failed: {err}")
    with publish_logs:
        st.code(logs or "(no logs)")

st.divider()

st.subheader("Progress tracker")

with st.expander("Progress stats"):
    prog = compute_progress(paths)
    if prog is None:
        st.warning("Gold registry not found yet. Build Gold first.")
    else:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Gold rows", f"{prog['gold_rows']:,}")
        c2.metric("In scope now", f"{prog['scope_rows']:,}")
        c3.metric("In final now", f"{prog['final_rows']:,}")
        c4.metric("Missing URL (operating+editorial)", f"{prog['missing_url']:,}")

        st.write("What’s blocking final (in scope)")
        b1, b2, b3, b4 = st.columns(4)
        b1.metric("Needs content_type", f"{prog['needs_content_type']:,}")
        b2.metric("Needs status", f"{prog['needs_status']:,}")
        b3.metric("No website", f"{prog['no_website']:,}")
        b4.metric("Paywalled", f"{prog['paywalled']:,}")

        b5, b6, b7, b8 = st.columns(4)
        b5.metric("Broken URL", f"{prog['broken_url']:,}")
        b6.metric("Not operating", f"{prog['not_operating']:,}")
        b7.metric("Not found", f"{prog['not_found']:,}")
        b8.metric("Not editorial (other)", f"{prog['not_editorial']:,}")


view_mode = st.radio(
    "View",
    ["Editorial (news + sports)", "News only", "Sports only"],
    horizontal=True,
)


if view_mode == "News only":
    published_csv = paths.published / "final_news_outlets.csv"
    published_parquet = paths.published / "final_news_outlets.parquet"
elif view_mode == "Sports only":
    published_csv = paths.published / "final_sports_outlets.csv"
    published_parquet = paths.published / "final_sports_outlets.parquet"
else:
    published_csv = paths.published / "final_outlets.csv"
    published_parquet = paths.published / "final_outlets.parquet"

# back-compat fallback for Editorial
if view_mode == "Editorial (news + sports)":
    if not published_csv.exists():
        published_csv = paths.published / "final_registry.csv"
    if not published_parquet.exists():
        published_parquet = paths.published / "final_registry.parquet"


if not published_csv.exists() and not published_parquet.exists():
    st.warning("No published registry found yet. Go to Pipeline → Publish final_registry.csv")
    st.stop()

@st.cache_data(show_spinner=False)
def _load_final(published_csv_str: str, published_parquet_str: str):
    published_csv = Path(published_csv_str)
    published_parquet = Path(published_parquet_str)

    # Prefer CSV as the definitive published artifact
    if published_csv.exists():
        return pd.read_csv(published_csv, dtype=str).fillna("")
    return pd.read_parquet(published_parquet)

df = _load_final(str(published_csv), str(published_parquet))

c_reload, _ = st.columns([1, 5])
with c_reload:
    if st.button("Force reload published data"):
        st.cache_data.clear()
        st.rerun()

# ---- High-level stats
tab_final, tab_excluded = st.tabs(["Final Registry", "Excluded / Why"])

with tab_final:
    st.subheader("Stats")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Rows", f"{len(df):,}")
    c2.metric("Unique outlets (id)", f"{df['id'].nunique():,}" if "id" in df.columns else "—")
    c3.metric("Unique domains", f"{df['url'].astype(str).str.lower().str.replace('https://','',regex=False).str.replace('http://','',regex=False).str.replace('www.','',regex=False).str.split('/',n=1).str[0].nunique():,}" if "url" in df.columns else "—")
    c4.metric("Prefectures", f"{df['prefecture_en'].nunique():,}" if "prefecture_en" in df.columns else "—")

    st.subheader("Domain analysis scope")

    scope = st.radio(
        "Compute domain tables on:",
        ["Final registry (published)", "Gold (after overrides)"],
        horizontal=True,
    )

    df_domains = df.copy()

    if scope == "Gold (after overrides)":
        gold_path = paths.gold / "registry_gold.parquet"
        g = pd.read_parquet(gold_path)

        overrides_path = paths.overrides / "outlet_overrides.csv"
        ov = load_outlet_overrides(overrides_path)
        g = apply_outlet_overrides(g, ov)

        # mimic review scope so irrelevant rows are not analyzed
        def _norm(s): return s.astype(str).str.strip().str.lower()
        ct = _norm(g.get("content_type", pd.Series([""] * len(g))))
        stt = _norm(g.get("status", pd.Series([""] * len(g))))

        ct_ok = ct.isin(["", "unknown", "news"])
        st_ok = stt.isin(["", "unknown", "operating"])

        df_domains = g[ct_ok & st_ok].copy()


    # ---- Top domains by number of outlets
    if "url" in df.columns:
#        st.subheader("Top domains by number of outlets")

        def _base_domain(u: object) -> str:
            u = str(u or "").strip().lower()
            u = u.replace("https://", "").replace("http://", "")
            host = u.split("/")[0].strip()
            if not host:
                return ""
            # drop common prefixes
            for pref in ("www.", "www2.", "m."):
                if host.startswith(pref):
                    host = host[len(pref):]

            parts = host.split(".")
            if len(parts) <= 2:
                return host

            # For .gr: keep 2 labels normally (ert.gr), but keep 3 when it is a second-level domain like com.gr, net.gr, org.gr, edu.gr, gov.gr
            if parts[-1] == "gr":
                if len(parts) >= 3 and parts[-2] in {"com", "net", "org", "edu", "gov"}:
                    return ".".join(parts[-3:])
                return ".".join(parts[-2:])

            # Common second-level patterns like co.uk
            if parts[-2] in {"co", "com", "net", "org"} and len(parts) >= 3:
                return ".".join(parts[-3:])

            # Default: last 2 labels
            return ".".join(parts[-2:])

        domains = (
            df_domains.assign(domain=df_domains["url"].apply(_base_domain))
            .query("domain != ''")
            .groupby("domain")
            .size()
            .reset_index(name="outlet_count")
            .sort_values("outlet_count", ascending=False)
            .head(30)
        )

#        st.dataframe(domains, width="stretch")

    # ---- Domains shared across multiple media types
    if {"url", "media_type"}.issubset(df.columns):
        st.subheader("Domains shared across multiple media types")

        cross_media = (
            df_domains.assign(
                domain=df_domains["url"].apply(_base_domain),
                media_type=df_domains["media_type"].fillna("(blank)").astype(str).str.strip(),
            )
            .query("domain != ''")
            .groupby("domain")
            .agg(
                outlet_count=("id", "count"),
                media_types=("media_type", lambda x: sorted(set(x))),
            )
            .reset_index()
        )

        cross_media["media_type_count"] = cross_media["media_types"].apply(len)

        cross_media = (
            cross_media[cross_media["media_type_count"] > 1]
            .sort_values(["media_type_count", "outlet_count"], ascending=False)
        )

        st.dataframe(
            cross_media[
                ["domain", "outlet_count", "media_type_count", "media_types"]
            ],
            width="stretch",
        )


    # ---- Breakdowns
    st.subheader("Breakdowns")

    colA, colB = st.columns(2)

    with colA:
        if "media_type" in df.columns:
            st.write("By media_type")
            st.dataframe(
                df["media_type"]
                .value_counts(dropna=False)
                .rename("count")
                .reset_index()
                .rename(columns={"index": "media_type"}),
                width="stretch",
            )

            # NEW: breakdown by range_type within media_type
            if "range_type" in df.columns:
                st.write("By media_type × range_type")
                mt_rt = (
                    df.assign(
                        media_type=df["media_type"].fillna("(blank)").astype(str).str.strip().replace({"": "(blank)"}),
                        range_type=df["range_type"].fillna("(blank)").astype(str).str.strip().replace({"": "(blank)"}),
                    )
                    .groupby(["media_type", "range_type"])
                    .size()
                    .reset_index(name="count")
                    .sort_values(["media_type", "count"], ascending=[True, False])
                )
                st.dataframe(mt_rt, width="stretch")
        else:
            st.info("No media_type column found.")

    with colB:
        if "prefecture_en" in df.columns:
            st.write("Top prefectures (by count)")
            top_pref = (
                df["prefecture_en"].fillna("")
                .astype(str).str.strip()
                .replace({"": "(blank)"})
                .value_counts()
                .head(30)
                .rename("count")
                .reset_index()
                .rename(columns={"index": "prefecture_en"})
            )
            st.dataframe(top_pref, width="stretch")
        else:
            st.info("No prefecture_en column found.")

    # ---- Simple filters + preview
    st.subheader("Preview")

    st.markdown("**Quick find**")
    q_url = st.text_input("Find by exact URL (paste)", value="")
    if q_url.strip():
        qn = q_url.strip().lower()
        hit = df[df["url"].astype(str).str.strip().str.lower() == qn].copy()
        st.write(f"Matches: {len(hit)}")
        st.dataframe(hit, width="stretch")


    only_with_url = st.checkbox("Show only rows with a URL", value=True)

    name_q = st.text_input("Filter by name contains", value="")

    mt_opts = ["(all)"]
    if "media_type" in df.columns:
        mt_opts += sorted([m for m in df["media_type"].dropna().astype(str).str.strip().unique().tolist() if m != ""])
    mt_choice = st.selectbox("Filter by media_type", mt_opts, index=0)

    pref_opts = ["(all)"]
    if "prefecture_en" in df.columns:
        pref_opts += sorted([p for p in df["prefecture_en"].dropna().astype(str).str.strip().unique().tolist() if p != ""])
    pref_choice = st.selectbox("Filter by prefecture_en", pref_opts, index=0)

    view = df.copy()
    if only_with_url and "url" in view.columns:
        u = view["url"].astype(str).str.strip()
        view = view[(u != "") & (u.str.lower() != "nan")].copy()

    if name_q.strip():
        view = view[view["name"].astype(str).str.contains(name_q.strip(), case=False, na=False)].copy()
    if mt_choice != "(all)" and "media_type" in view.columns:
        view = view[view["media_type"].astype(str).str.strip() == mt_choice].copy()
    if pref_choice != "(all)" and "prefecture_en" in view.columns:
        view = view[view["prefecture_en"].astype(str).str.strip() == pref_choice].copy()

    st.caption(f"Showing {len(view):,} rows")
    st.dataframe(view.head(500), width="stretch")

    # ---- Downloads
#    st.subheader("Download")
    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            "Download final_registry.csv",
            data=published_csv.read_bytes(),
            file_name="final_registry.csv",
            mime="text/csv",
            disabled=not published_csv.exists(),
        )
    with col2:
        if published_parquet.exists():
            st.download_button(
                "Download final_registry.parquet",
                data=published_parquet.read_bytes(),
                file_name="final_registry.parquet",
                mime="application/octet-stream",
            )



    st.subheader("URL registry (deduped)")

    if view_mode == "News only":
        urls_csv = paths.published / "final_news_urls.csv"
        urls_parquet = paths.published / "final_news_urls.parquet"
    elif view_mode == "Sports only":
        urls_csv = paths.published / "final_sports_urls.csv"
        urls_parquet = paths.published / "final_sports_urls.parquet"
    else:
        urls_csv = paths.published / "final_urls.csv"
        urls_parquet = paths.published / "final_urls.parquet"

    if not urls_csv.exists() and not urls_parquet.exists():
        st.info("No URL registry found yet. Re-publish to generate final_urls.csv.")
    else:
        if urls_parquet.exists():
            url_df = pd.read_parquet(urls_parquet)
        else:
            url_df = pd.read_csv(urls_csv, dtype=str).fillna("")

        c1, c2, c3 = st.columns(3)
        c1.metric("Unique URLs", f"{len(url_df):,}")

        # Web-native count
        if "web_native" in url_df.columns:
            web_native_count = int(pd.to_numeric(url_df["web_native"], errors="coerce").fillna(0).sum())
            c2.metric("Web-native URLs", f"{web_native_count:,}")
        else:
            c2.metric("Web-native URLs", "—")

        # Cross-media count (>= 2 of tv/radio/newspaper)
        if {"has_tv", "has_radio", "has_newspaper"}.issubset(url_df.columns):
            has_tv = pd.to_numeric(url_df["has_tv"], errors="coerce").fillna(0).astype(int)
            has_radio = pd.to_numeric(url_df["has_radio"], errors="coerce").fillna(0).astype(int)
            has_news = pd.to_numeric(url_df["has_newspaper"], errors="coerce").fillna(0).astype(int)
            cross_media_count = int(((has_tv + has_radio + has_news) >= 2).sum())
            c3.metric("Cross-media URLs", f"{cross_media_count:,}")
        else:
            c3.metric("Cross-media URLs", "—")

        st.dataframe(url_df.head(200), width="stretch")

        col1, col2 = st.columns(2)
        with col1:
            if urls_csv.exists():
                st.download_button(
                    "Download final_urls.csv",
                    data=urls_csv.read_bytes(),
                    file_name="final_urls.csv",
                    mime="text/csv",
                )
        with col2:
            if urls_parquet.exists():
                st.download_button(
                    "Download final_urls.parquet",
                    data=urls_parquet.read_bytes(),
                    file_name="final_urls.parquet",
                    mime="application/octet-stream",
                )



with tab_excluded:
    st.subheader("Excluded / Why")
    st.caption("Explains why items from Gold are not in the published final registry (after applying overrides).")

    gold_path = paths.gold / "registry_gold.parquet"
    if not gold_path.exists():
        st.warning("Gold registry not found. Build Gold first.")
        st.stop()

    @st.cache_data(show_spinner=False)
    def _load_gold_with_overrides():
        g = pd.read_parquet(gold_path)
        overrides_path = paths.overrides / "outlet_overrides.csv"
        if overrides_path.exists():
            from src.overrides.outlet_overrides import load_outlet_overrides, apply_outlet_overrides
            ov = load_outlet_overrides(overrides_path)
            g = apply_outlet_overrides(g, ov)
        return g

    g = _load_gold_with_overrides()

    st.write("Gold media_type counts")
    st.dataframe(g["media_type"].value_counts(dropna=False).rename("count").reset_index())


    def _norm(s):
        return s.astype(str).str.strip().str.lower()

    status = _norm(g.get("status", pd.Series([""] * len(g))))
    ct = _norm(g.get("content_type", pd.Series([""] * len(g))))
    url_status = _norm(g.get("url_status", pd.Series(["ok"] * len(g))))
    url = g.get("url", pd.Series([""] * len(g))).astype(str).str.strip()

    is_operating = status == "operating"
    is_editorial = ct.isin(["news", "sports"])
    has_url = (url != "") & (url != "nan")
    is_url_ok = url_status == "ok"

    in_final = is_operating & is_editorial & is_url_ok & has_url

    # Reason assignment (first match wins)
    reason = pd.Series("in_final", index=g.index)
    reason[~has_url & (url_status == "ok")] = "missing_url"
    reason[url_status == "paywalled"] = "paywalled"
    reason[url_status == "no_website"] = "no_website"
    reason[url_status == "broken"] = "broken_url"
    reason[~is_editorial] = "not_editorial"
    reason[~is_operating] = "not_operating"

    # Keep only excluded
    excluded = g[~in_final].copy()
    excluded["excluded_reason"] = reason[~in_final].values

    # Optional: show excluded counts by media_type (helps sanity-check)
    st.write("Excluded by media_type")
    st.dataframe(
        excluded["media_type"].value_counts(dropna=False).rename("count").reset_index(),
        width="stretch",
    )

    mt_filter = st.selectbox(
        "Filter by media_type",
        ["(all)"] + sorted(excluded["media_type"].dropna().astype(str).unique().tolist()),
        index=0,
    )

    st.write("Reasons (counts)")
    reasons = excluded["excluded_reason"].value_counts(dropna=False).rename("count").reset_index().rename(columns={"index": "excluded_reason"})
    st.dataframe(reasons, width="stretch")

    st.write("Inspect excluded rows")
    reason_filter = st.selectbox("Filter by reason", ["(all)"] + reasons["excluded_reason"].tolist(), index=0)
    ex_view = excluded.copy()
    if reason_filter != "(all)":
        ex_view = ex_view[ex_view["excluded_reason"] == reason_filter].copy()
    if mt_filter != "(all)":
        ex_view = ex_view[ex_view["media_type"].astype(str) == mt_filter].copy()

    cols = [
        "id", "name", "media_type", "prefecture_en", "status", "content_type", "url_status", "url", "owner", "excluded_reason"
    ]
    for c in cols:
        if c not in ex_view.columns:
            ex_view[c] = pd.NA

    limit = st.selectbox("Rows to show", [200, 500, 1000, 5000], index=1)
    st.dataframe(ex_view[cols].head(limit), width="stretch")
