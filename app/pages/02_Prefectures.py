import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]  # gr_news_media_registry/
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st
import pandas as pd

from src.config import get_paths
from src.prefectures import load_prefecture_aliases, unmatched_values
from src.silver.tv import build_tv_silver
from src.silver.radio import build_radio_silver
from src.silver.press import build_press_silver
from src.silver.websites import build_websites_silver

st.set_page_config(page_title="Prefecture Aliases", layout="wide")

from app.demo import is_demo_mode

if is_demo_mode():
    st.warning("Demo mode: read-only. Overrides editing is disabled.")
    st.stop()

root = Path(__file__).resolve().parents[2]
paths = get_paths(root)

canon_path = paths.overrides / "canonical_prefectures.csv"
canon = pd.read_csv(canon_path, dtype=str).fillna("")
canon["prefecture"] = canon["prefecture"].astype(str).str.strip()
canon["prefecture_en"] = canon["prefecture_en"].astype(str).str.strip()
canon = canon[(canon["prefecture"] != "") & (canon["prefecture_en"] != "")].copy()

pref_gr_options = canon["prefecture"].tolist()
pref_en_options = canon["prefecture_en"].tolist()

gr_to_en = dict(zip(canon["prefecture"], canon["prefecture_en"]))
en_to_gr = dict(zip(canon["prefecture_en"], canon["prefecture"]))


st.title("Prefecture Aliases")

st.info(
    """
This page manages **prefecture (νομός) aliasing**.

Why this exists:
- Source files often use different strings for the same place (e.g., spelling variants, tax-office names, sheet names).
- We store those raw values in the pipeline (**prefecture_raw / tax_office_raw**) for auditability.
- Here you map raw values → a **canonical prefecture** (Greek + English), so Silver/Gold outputs are consistent.

Workflow:
1) Add or edit alias mappings below
2) Save aliases
3) Rebuild Silver to apply mappings
4) Check “Unmatched” lists and repeat
"""
)

with st.expander("Canonical prefectures list"):
    st.dataframe(canon, width="stretch")

alias_path = paths.overrides / "prefecture_aliases.csv"
paths.overrides.mkdir(parents=True, exist_ok=True)

# --- Unmatched report ---
st.subheader("Unmatched prefectures in Silver")

aliases2 = load_prefecture_aliases(alias_path)
silver_files = sorted(paths.silver.glob("*.parquet"))

if not silver_files:
    st.info("No silver parquet files found yet. Build TV or Radio silver first.")
    # Ensure the Add-mapping dropdown exists even if nothing is available
    st.session_state["unmatched_alias_options"] = []
else:
    options = [p.name for p in silver_files]
    picked = st.selectbox("Choose a silver file", options, key="unmatched_picked_file")

    df = pd.read_parquet(paths.silver / picked)
    raw_candidates = [c for c in ["prefecture_raw", "tax_office_key", "tax_office_raw"] if c in df.columns]

    if not raw_candidates:
        st.warning(f"{picked} has no prefecture-like raw columns.")
        st.session_state["unmatched_alias_options"] = []
    else:
        raw_col = st.selectbox("Raw column to check", raw_candidates, key="unmatched_raw_col")
        unknown = unmatched_values(df, raw_col=raw_col, aliases_df=aliases2)

        if unknown.empty:
            st.success(f"No unmatched values in {picked}.{raw_col}")
            st.session_state["unmatched_alias_options"] = []
        else:
            st.write("Add these as aliases above:")
            st.dataframe(unknown, width="stretch")
            # Store unmatched values for the Add-mapping dropdown
            st.session_state["unmatched_alias_options"] = sorted(set(unknown["alias"].astype(str).tolist()))


st.divider()

# --- Edit table ---
st.subheader("Edit alias table")

aliases_disk = load_prefecture_aliases(alias_path)
if aliases_disk.empty:
    aliases_disk = pd.DataFrame(columns=["alias", "alias_type", "prefecture", "prefecture_en", "notes"])
else:
    aliases_disk = aliases_disk.drop(columns=["alias_norm"], errors="ignore")

tab_add, tab_view = st.tabs(["Add mapping (recommended)", "View / Download"])

with tab_add:
    st.caption("Add one mapping at a time. Each click writes immediately to CSV (no lost edits).")

    with st.form("add_alias_form", clear_on_submit=True):
        unmatched_opts = st.session_state.get("unmatched_alias_options", [])
        if unmatched_opts:
            chosen = st.selectbox(
                "Alias (raw value) — pick from unmatched",
                options=["(type manually)"] + unmatched_opts,
                index=0,
            )
            alias = st.text_input(
                "Or type/paste alias",
                value="" if chosen == "(type manually)" else chosen,
            )
        else:
            alias = st.text_input("Alias (raw value)", value="")

        alias_type = st.selectbox("Alias type", ["nomos", "tax_office", "sheet", "other"], index=0)

        pref_gr = st.selectbox("Canonical prefecture (Greek)", pref_gr_options, index=0)

        # English dropdown, auto-selected to match Greek (still a dropdown as requested)
        pref_en_default = gr_to_en.get(pref_gr, "")
        pref_en_index = pref_en_options.index(pref_en_default) if pref_en_default in pref_en_options else 0
        pref_en = st.selectbox("Canonical prefecture (English)", pref_en_options, index=pref_en_index)

        notes = st.text_input("Notes (optional)", value="")

        submitted = st.form_submit_button("Add mapping", type="primary")

        if submitted:
            a = str(alias).strip()
            if a == "":
                st.error("Alias cannot be empty.")
            else:
                new_row = pd.DataFrame([{
                    "alias": a,
                    "alias_type": alias_type,
                    "prefecture": pref_gr,
                    "prefecture_en": pref_en,
                    "notes": notes,
                }])

                out = pd.concat([aliases_disk, new_row], ignore_index=True).fillna("")

                # Normalize alias key (strip + collapse whitespace)
                out["alias"] = out["alias"].astype(str).str.strip()
                out["alias_norm"] = out["alias"].str.replace(r"\s+", " ", regex=True)

                out = out[out["alias_norm"] != ""].copy()

                # Detect if we're overwriting an existing alias
                is_overwrite = (out["alias_norm"].duplicated(keep=False)).any()

                # Keep last occurrence (new row wins)
                out = out.drop_duplicates(subset=["alias_norm"], keep="last")

                # Drop helper column before saving
                out = out.drop(columns=["alias_norm"])

                out.to_csv(alias_path, index=False)

                if is_overwrite:
                    st.warning(f"Alias already existed — updated mapping for: {a}")
                else:
                    st.success(f"Added mapping for: {a}")

                st.rerun()


with tab_view:
    st.caption("Read-only view. Download CSV to bulk edit in a spreadsheet if needed.")
    view = aliases_disk.copy()
    view["alias"] = view["alias"].astype(str).str.strip()
    view["alias_norm"] = view["alias"].str.replace(r"\s+", " ", regex=True)
    view = view.drop_duplicates(subset=["alias_norm"], keep="last").drop(columns=["alias_norm"])
    st.dataframe(view, width="stretch")

    st.download_button(
        "Download prefecture_aliases.csv",
        data=alias_path.read_bytes() if alias_path.exists() else b"",
        file_name="prefecture_aliases.csv",
        mime="text/csv",
    )

    if st.button("Reload from disk"):
        st.rerun()

st.divider()

# --- Build controls at the end ---
st.subheader("Apply aliases (rebuild Silver)")

st.caption(
    "This will rebuild Silver outputs using the current alias table. "
    "As we add more sources (radio/press/websites), they will appear here too."
)

build_target = st.selectbox(
    "What do you want to rebuild?",
    options=["TV (ESR)", "Radio (ESR)", "Press (MT)", "Websites (MT)"],
    index=0,
)

if st.button("Build selected Silver", type="primary"):
    if build_target == "TV (ESR)":
        out_path = build_tv_silver(paths)
    elif build_target == "Radio (ESR)":
        out_path = build_radio_silver(paths)
    elif build_target == "Press (MT)":
        out_path = build_press_silver(paths)
    elif build_target == "Websites (MT)":
        out_path = build_websites_silver(paths)
    st.success(f"Built: {out_path}")
    st.rerun()

