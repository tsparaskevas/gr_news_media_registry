import json
from pathlib import Path

import pandas as pd
import streamlit as st
import plotly.graph_objects as go

from src.config import get_paths


st.set_page_config(page_title="Prefecture map", layout="wide")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
paths = get_paths(PROJECT_ROOT)

st.title("Prefecture map (outlets with website)")
st.caption(
    "Counts of outlets in the published final registry, aggregated by prefecture. "
    "Filter by media bucket, content type, and geographic range. "
    "Web-native is derived from final_urls."
)

# ---- Load published artifacts ----
outlets_path = paths.published / "final_outlets.parquet"
urls_path = paths.published / "final_urls.parquet"
if not outlets_path.exists():
    st.error("Missing published final outlets. Run Publish first (Pipeline page).")
    st.stop()

outlets = pd.read_parquet(outlets_path)

# Load URL registry if available (for web_native)
url_registry = None
if urls_path.exists():
    url_registry = pd.read_parquet(urls_path)

# ---- Load geojson ----
geo_path = Path("data/geo/greece-prefectures.geojson")
if not geo_path.exists():
    st.error("Missing GeoJSON. Add: data/geo/greece-prefectures.geojson")
    st.stop()

with geo_path.open("r", encoding="utf-8") as f:
    geo = json.load(f)


import re
import unicodedata

def _norm_name(s: str) -> str:
    s = (s or "").strip().lower()
    # remove accents (works for greek too)
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    # remove common noise
    s = re.sub(r"^(ν\.|νομος|nomos)\s+", "", s).strip()
    s = re.sub(r"\s+", " ", s)
    return s


def _centroid_of_feature(feat):
    """Rough centroid from polygon bounds (works fine for labeling)."""
    geom = feat.get("geometry") or {}
    coords = geom.get("coordinates") or []
    gtype = geom.get("type")

    lons, lats = [], []

    def _collect_points(ring):
        for pt in ring:
            if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                lons.append(float(pt[0]))
                lats.append(float(pt[1]))

    if gtype == "Polygon":
        # coords = [ring1, ring2, ...]
        for ring in coords:
            _collect_points(ring)
    elif gtype == "MultiPolygon":
        # coords = [[ring1,...], [ring1,...], ...]
        for poly in coords:
            for ring in poly:
                _collect_points(ring)

    if not lons or not lats:
        return None

    # centroid as midpoint of bounds (good enough for labels)
    return (min(lats) + max(lats)) / 2.0, (min(lons) + max(lons)) / 2.0

# ---- Load canonical prefectures mapping (your dropdown list) ----
canon_path = Path("data/overrides/canonical_prefectures.csv")
canon = None
if canon_path.exists():
    canon = pd.read_csv(canon_path, dtype=str).fillna("")
    # expect columns like: prefecture, prefecture_en (based on your setup)
    canon["prefecture"] = canon.get("prefecture", "").astype(str).str.strip()
    canon["prefecture_en"] = canon.get("prefecture_en", "").astype(str).str.strip()

alias_path = Path("data/overrides/geo_prefecture_aliases.csv")

#if alias_path.exists():
#    alias_df = pd.read_csv(alias_path, dtype=str).fillna("")
#    st.dataframe(alias_df, width="stretch")
#
#    st.download_button(
#        "Download mapping CSV",
#        data=alias_df.to_csv(index=False).encode("utf-8"),
#        file_name="geo_prefecture_aliases.csv",
#        mime="text/csv",
#        key="dl_geo_pref_aliases",
#    )


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


# ---- Build "bucket" media_type: tv/radio/newspaper/web-native ----
df = outlets.copy()
df["prefecture_en"] = df.get("prefecture_en", "").astype(str).str.strip()

# If url_registry exists: join web_native flag by canonical_url
df["canonical_url"] = df["url"].apply(_canonical_url) if "url" in df.columns else ""
if url_registry is not None and "canonical_url" in url_registry.columns:
    join_cols = url_registry[["canonical_url", "web_native"]].copy()
    # ensure bool-ish
    join_cols["web_native"] = pd.to_numeric(join_cols["web_native"], errors="coerce").fillna(0).astype(int)
    df = df.merge(join_cols, on="canonical_url", how="left")
else:
    df["web_native"] = 0

with st.expander("Canonical prefecture mapping (GeoJSON → registry prefecture_en)", expanded=False):
    st.subheader("GeoJSON → canonical prefecture mapping (edit in UI)")

    # Canonical dropdown values
    canon_en_options = []
    if canon is not None and "prefecture_en" in canon.columns:
        canon_en_options = sorted(
            [x for x in canon["prefecture_en"].astype(str).str.strip().unique().tolist() if x]
        )

    # Collect GeoJSON names
    geo_names = []
    for feat in geo.get("features", []):
        props = feat.get("properties", {})
        raw = (props.get("name") or props.get("NAME") or props.get("Nomos") or props.get("nomos") or "").strip()
        if raw:
            geo_names.append(raw)
    geo_names = sorted(set(geo_names))

    def _make_default_alias_df():
        # Try auto-match by normalization (best-effort)
        canon_norm_to_en = {_norm_name(x): x for x in canon_en_options}
        rows = []
        for raw in geo_names:
            k = _norm_name(raw)
            suggested = canon_norm_to_en.get(k, "")
            rows.append(
                {
                    "geo_name_raw": raw,
                    "geo_key_norm": k,
                    "canonical_prefecture_en": suggested,
                    "label_primary": "1",   # Option B: you will set 0 for Attica sub-areas except one
                }
            )
        return pd.DataFrame(rows)

    # Initialize / load mapping file
    if alias_path.exists():
        alias_df = pd.read_csv(alias_path, dtype=str).fillna("")
    else:
        alias_df = _make_default_alias_df()
        alias_path.parent.mkdir(parents=True, exist_ok=True)
        alias_df.to_csv(alias_path, index=False, encoding="utf-8")

    # Ensure required columns exist (in case old file was generated)
    for col, default in [
        ("geo_name_raw", ""),
        ("geo_key_norm", ""),
        ("canonical_prefecture_en", ""),
        ("label_primary", "1"),
    ]:
        if col not in alias_df.columns:
            alias_df[col] = default

    # Keep only current GeoJSON names (in case geojson changes)
    alias_df = alias_df[alias_df["geo_name_raw"].isin(geo_names)].copy()

    edited = st.data_editor(
        alias_df[["geo_name_raw", "geo_key_norm", "canonical_prefecture_en", "label_primary"]],
        width="stretch",
        hide_index=True,
        disabled=["geo_name_raw", "geo_key_norm"],
        column_config={
            "canonical_prefecture_en": st.column_config.SelectboxColumn(
                "canonical_prefecture_en",
                options=[""] + canon_en_options,
                help="Pick the canonical prefecture_en used in the registry",
            ),
            "label_primary": st.column_config.SelectboxColumn(
                "label_primary",
                options=["0", "1"],
                help="1 = show numeric label for this polygon, 0 = do not show label (Option B for Attica)",
            ),
        },
        key="geo_alias_editor",
    )

    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        if st.button("Save mapping"):
            edited.to_csv(alias_path, index=False, encoding="utf-8")
            st.success(f"Saved: {alias_path}")

    with c2:
        if st.button("Reset mapping (regenerate)"):
            alias_df2 = _make_default_alias_df()
            alias_df2.to_csv(alias_path, index=False, encoding="utf-8")
            st.success("Reset mapping file. Edit & Save again.")
            st.rerun()

    with c3:
        st.download_button(
            "Download mapping CSV",
            data=edited.to_csv(index=False).encode("utf-8"),
            file_name="geo_prefecture_aliases.csv",
            mime="text/csv",
            key="dl_geo_pref_counts",
        )


# ---- Filters (media bucket, content_type, range_type) ----

# bucket:
# - web-native means: outlet is a website entity AND its URL is marked web_native in final_urls
# - otherwise bucket by media_type
df["media_bucket"] = df.get("media_type", "unknown").astype(str).str.strip().str.lower()
df.loc[(df["media_bucket"] == "website") & (df["web_native"] == 1), "media_bucket"] = "web-native"

# normalize filterable fields (defensive)
df["content_type"] = df.get("content_type", "").astype(str).str.strip().str.lower()
df["range_type"] = df.get("range_type", "").astype(str).str.strip().str.lower()

f1, f2, f3 = st.columns(3)

with f1:
    bucket_options = ["all", "tv", "radio", "newspaper", "web-native"]
    choice = st.selectbox("Media type", bucket_options, index=0)

with f2:
    ct_options = ["all", "news", "sports"]
    ct_choice = st.selectbox("Content type", ct_options, index=0)

with f3:
    range_options = ["all", "national", "regional"]
    range_choice = st.selectbox("Range", range_options, index=0)

# Apply filters
df_view = df.copy()

if choice != "all":
    df_view = df_view[df_view["media_bucket"] == choice].copy()

if ct_choice != "all":
    df_view = df_view[df_view["content_type"] == ct_choice].copy()

if range_choice != "all":
    df_view = df_view[df_view["range_type"] == range_choice].copy()


# ---- Aggregate counts by prefecture ----
counts = (
    df_view.groupby("prefecture_en", as_index=False)
      .size()
      .rename(columns={"size": "outlet_count"})
)

st.write(f"Total outlets in this view: **{int(counts['outlet_count'].sum())}**")

with st.expander("Outlets in this view"):
    st.dataframe(counts.sort_values("outlet_count", ascending=False), width="stretch")

# ---- Inspect outlets for a prefecture (from the filtered view) ----
st.markdown("### Inspect outlets by prefecture")

pref_options = counts.sort_values("prefecture_en")["prefecture_en"].astype(str).tolist()
pref_options = [p for p in pref_options if p and p.lower() not in {"nan", "<na>"}]

sel_pref = st.selectbox(
    "Select a prefecture",
    [""] + pref_options,
    index=0,
    help="Shows outlets from the current filtered view (Media/Content/Range).",
)

if sel_pref:
    cols_show = [
        "name",
        "media_type",
        "media_bucket",
        "content_type",
        "range_type",
        "url",
        "owner",
        "fb",
        "x",
        "youtube",
    ]
    cols_show = [c for c in cols_show if c in df_view.columns]

    subset = df_view[df_view["prefecture_en"].astype(str).str.strip() == sel_pref].copy()
    subset = subset.sort_values(["media_bucket", "name"], na_position="last")

    st.write(f"Outlets in **{sel_pref}**: **{len(subset):,}**")
    st.dataframe(subset[cols_show], width="stretch")

show_labels = st.checkbox("Show numeric labels on map", value=True)

# ---- Attach counts to GeoJSON features using alias table ----
# Map canonical prefecture_en -> count
pref_counts = dict(zip(counts["prefecture_en"].astype(str).str.strip(), counts["outlet_count"].astype(int)))

# Build mapping: geo_key_norm -> (canonical_prefecture_en, label_primary)
alias_live = edited.copy()
alias_live["geo_key_norm"] = alias_live["geo_key_norm"].astype(str).str.strip()
alias_live["canonical_prefecture_en"] = alias_live["canonical_prefecture_en"].astype(str).str.strip()
alias_live["label_primary"] = alias_live["label_primary"].astype(str).str.strip()
geo_to_canon = dict(zip(alias_live["geo_key_norm"], alias_live["canonical_prefecture_en"]))
geo_to_primary = dict(zip(alias_live["geo_key_norm"], alias_live["label_primary"]))

max_val = int(max(pref_counts.values())) if len(pref_counts) else 1

for feat in geo.get("features", []):
    props = feat.setdefault("properties", {})
    raw_name = (props.get("name") or props.get("NAME") or props.get("Nomos") or props.get("nomos") or "").strip()
    geo_key = _norm_name(raw_name)

    canon_en = geo_to_canon.get(geo_key, "")
    val = int(pref_counts.get(canon_en, 0)) if canon_en else 0

    props["key"] = geo_key  # stable key for plotly
    props["canonical_prefecture_en"] = canon_en
    props["label_primary"] = geo_to_primary.get(geo_key, "1")
    props["outlet_count"] = val
    props["fill_alpha"] = int(40 + (180 * (val / max_val))) if max_val else 40


labels = []
for feat in geo.get("features", []):
    props = feat.get("properties", {})
    # Option B: only label_primary polygons get numbers
    if str(props.get("label_primary", "1")).strip() != "1":
        continue

    name = (props.get("name") or props.get("NAME") or props.get("Nomos") or "").strip()
    val = int(props.get("outlet_count", 0))
    if val == 0:
        continue

    c = _centroid_of_feature(feat)
    if c is None:
        continue
    lat, lon = c
    labels.append({"name": name, "outlet_count": str(val), "lat": lat, "lon": lon})


labels_df = pd.DataFrame(labels, columns=["name", "outlet_count", "lat", "lon"])
if not labels_df.empty:
    labels_df["lat"] = pd.to_numeric(labels_df["lat"], errors="coerce")
    labels_df["lon"] = pd.to_numeric(labels_df["lon"], errors="coerce")
    labels_df = labels_df.dropna(subset=["lat", "lon"])

#st.caption(f"Labels to render: {len(labels_df):,}")
#st.dataframe(labels_df.head(30), width="stretch")

#################

# ---- Dynamic title ----
def _pretty(v: str) -> str:
    v = (v or "").strip().lower()
    if v == "all":
        return "All"
    return v.replace("-", " ").title()

title = f"Outlets per prefecture — Media: {_pretty(choice)} — Content: {_pretty(ct_choice)} — Range: {_pretty(range_choice)}"
st.subheader(title)

# Build a dataframe for choropleth keyed by feature property "key"
## Ensure each feature has a stable key
#for feat in geo.get("features", []):
#    props = feat.setdefault("properties", {})
#    raw_name = (props.get("name") or props.get("NAME") or props.get("Nomos") or props.get("nomos") or "").strip()
#    props["key"] = _norm_name(raw_name)

# Build map df from features (so it always aligns with geojson keys)
feat_keys = []
feat_vals = []
for feat in geo.get("features", []):
    props = feat.get("properties", {})
    feat_keys.append(props.get("key", ""))
    feat_vals.append(int(props.get("outlet_count", 0)))

map_df = pd.DataFrame({"key": feat_keys, "outlet_count": feat_vals})

# Choropleth
fig = go.Figure()

fig.add_trace(
    go.Choropleth(
        geojson=geo,
        locations=map_df["key"],
        z=map_df["outlet_count"],
        featureidkey="properties.key",
        marker_line_width=0.6,
        colorbar_title="Outlets",
        hovertemplate="<b>%{location}</b><br>Outlets: %{z}<extra></extra>",
        # Custom palette: low counts are light but NOT near-white
        colorscale=[
            [0.0, "#f6e8d9"],  # <- less light than #fff7ec
            [0.2, "#fee0c2"],
            [0.4, "#fdbf95"],
            [0.6, "#fc8d59"],
            [0.8, "#ef6548"],
            [1.0, "#b30000"],
        ],
        zmin=0,
        zmax=int(map_df["outlet_count"].max()) if len(map_df) else 1,
    )
)

# Overlay numeric labels
if show_labels and (not labels_df.empty):
    fig.add_trace(
        go.Scattergeo(
            lon=labels_df["lon"],
            lat=labels_df["lat"],
            text=labels_df["outlet_count"],
            mode="text",
            textfont=dict(color="black", size=18),
            hoverinfo="skip",
            showlegend=False,
        )
    )

fig.update_geos(
    fitbounds="locations",
    visible=False,
    showcountries=False,
    showcoastlines=False,
    showland=False,
)

fig.update_layout(
    margin=dict(l=0, r=0, t=0, b=0),
    height=700,
)

st.plotly_chart(fig, width="stretch")

