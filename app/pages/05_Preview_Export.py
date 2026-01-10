import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st
import pandas as pd

from src.config import get_paths


st.set_page_config(page_title="Preview & Export", layout="wide")

root = Path(__file__).resolve().parents[2]
paths = get_paths(root)


def make_unique_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Streamlit/pyarrow cannot display DataFrames with duplicate column names.
    This function renames duplicates by appending .1, .2, etc.
    """
    cols = list(df.columns)
    seen = {}
    new_cols = []
    for c in cols:
        c = str(c)
        if c not in seen:
            seen[c] = 0
            new_cols.append(c)
        else:
            seen[c] += 1
            new_cols.append(f"{c}.{seen[c]}")
    out = df.copy()
    out.columns = new_cols
    return out


st.title("Preview & Export")

# Discover available parquet/csv artifacts
silver_files = sorted(paths.silver.glob("*.parquet"))
gold_files = sorted(paths.gold.glob("*.parquet"))
published_files = sorted(paths.published.glob("*.csv"))

options = []
for p in silver_files:
    options.append(("Silver", p.name, p))
for p in gold_files:
    options.append(("Gold", p.name, p))
for p in published_files:
    options.append(("Published", p.name, p))

if not options:
    st.info("No Silver/Gold/Published files found yet.")
    st.stop()

labels = [f"{layer}: {name}" for layer, name, _ in options]
choice = st.selectbox("Choose dataset", labels, index=0)
layer, name, path = options[labels.index(choice)]

st.caption(f"File: {path}")

# Load
if path.suffix == ".parquet":
    df = pd.read_parquet(path)
else:
    df = pd.read_csv(path)

dups = df.columns[df.columns.duplicated()].tolist()
if dups:
    st.error(f"Duplicate columns in dataset: {dups}")

# Summary
st.subheader("Summary")
c1, c2, c3 = st.columns(3)
c1.metric("Rows", len(df))
c2.metric("Columns", df.shape[1])
c3.metric("Missing cells", int(df.isna().sum().sum()))

# Missing values
st.subheader("Missing values")

missing = df.isna().sum().sort_values(ascending=False)
missing = missing[missing > 0].rename("missing").reset_index().rename(columns={"index": "column"})

if missing.empty:
    st.success("No missing values")
else:
    st.dataframe(missing, width="stretch")

st.subheader("Rows with missing values (filter)")

cols_with_missing = missing["column"].tolist() if not missing.empty else []
if cols_with_missing:
    col_to_check = st.selectbox("Show rows where this column is missing", cols_with_missing)

    include_unknown = st.checkbox("Also treat 'unknown' as missing", value=True)

    only_missing = df[df[col_to_check].isna()].copy()
    if include_unknown and col_to_check in df.columns:
        only_missing = df[(df[col_to_check].isna()) | (df[col_to_check].astype(str).str.strip().str.lower() == "unknown")].copy()

    only_missing = df[df[col_to_check].isna()].copy()
    st.write(f"Rows missing {col_to_check}: {len(only_missing)}")
    st.dataframe(only_missing.head(500), width="stretch")
else:
    st.info("No missing values to filter.")

# Useful breakdowns if columns exist
with st.expander("Breakdowns", expanded=True):
    for col in ["media_type", "range_type", "status", "content_type", "prefecture_en"]:
        if col in df.columns:
            st.write(f"**{col}**")
            vc = (
                df[col]
                .value_counts(dropna=False)
                .head(50)
                .rename_axis("value")
                .reset_index(name="n")
            )
            vc = make_unique_columns(vc)
            st.dataframe(vc, width="stretch")

st.subheader("Preview")
df_display = make_unique_columns(df)
st.dataframe(df_display.head(500), width="stretch")

# Export
st.subheader("Export")
if path.suffix == ".parquet":
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Download as CSV (utf-8)",
        data=csv_bytes,
        file_name=path.with_suffix(".csv").name,
        mime="text/csv",
    )
else:
    st.download_button(
        label="Download CSV",
        data=path.read_bytes(),
        file_name=path.name,
        mime="text/csv",
    )

