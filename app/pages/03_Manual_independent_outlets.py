# app/pages/09_Manual_Independent.py
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import pandas as pd
import streamlit as st

from src.config import get_paths

from app.demo import is_demo_mode

if is_demo_mode():
    st.warning("Demo mode: read-only. Overrides editing is disabled.")
    st.stop()

# ---------- Page setup ----------
st.set_page_config(page_title="Manual / Independent Intake", layout="wide")
st.title("Manual / Independent Media Intake")
st.caption(
    "Add Greek news outlets that are not covered by official registries (ESR / MT / public media). "
    "Entries here are human-curated and auditable."
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
paths = get_paths(PROJECT_ROOT)

OVERRIDES_DIR = PROJECT_ROOT / "data" / "overrides"
OVERRIDES_DIR.mkdir(parents=True, exist_ok=True)

MANUAL_PATH = OVERRIDES_DIR / "manual_independent_outlets.csv"
CANON_PATH = OVERRIDES_DIR / "canonical_prefectures.csv"


# ---------- Helpers ----------
def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_url(u: str) -> str:
    """Normalize URL for storage and comparisons."""
    u = (u or "").strip()
    if not u:
        return ""
    # If user pasted without scheme, assume https
    if not re.match(r"^https?://", u, flags=re.IGNORECASE):
        u = "https://" + u

    p = urlparse(u)
    scheme = (p.scheme or "https").lower()
    netloc = (p.netloc or "").lower()
    path = p.path or "/"

    # drop default ports
    netloc = re.sub(r":(80|443)$", "", netloc)

    # remove trailing slash unless root
    if path != "/" and path.endswith("/"):
        path = path[:-1]

    # keep query only if you explicitly want it; we drop it for registry identity
    return urlunparse((scheme, netloc, path, "", "", ""))


def is_valid_url(u: str) -> bool:
    if not u:
        return False
    p = urlparse(u)
    return p.scheme in {"http", "https"} and bool(p.netloc)


def make_manual_id(name: str, url: str) -> str:
    base = f"{(name or '').strip().lower()}|{(url or '').strip().lower()}"
    return hashlib.sha1(base.encode("utf-8")).hexdigest()


def load_manual() -> pd.DataFrame:
    cols = [
        "id",
        "name",
        "url",
        "media_type",
        "content_type",
        "status",
        "range_type",
        "prefecture_en",
        "owner",
        "fb",
        "x",
        "youtube",
        "notes",
        "added_by",
        "added_at",
        "updated_by",
        "updated_at",
    ]
    if not MANUAL_PATH.exists():
        return pd.DataFrame(columns=cols)

    try:
        df = pd.read_csv(MANUAL_PATH, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame(columns=cols)

    # ensure all columns exist
    for c in cols:
        if c not in df.columns:
            df[c] = ""

    # normalize urls
    if "url" in df.columns:
        df["url"] = df["url"].astype(str).map(normalize_url)

    return df[cols]


def save_manual(df: pd.DataFrame) -> None:
    df = df.copy()
    df.to_csv(MANUAL_PATH, index=False, encoding="utf-8")


def load_canonical_prefectures() -> list[str]:
    if not CANON_PATH.exists():
        return []
    canon = pd.read_csv(CANON_PATH, dtype=str).fillna("")
    if "prefecture_en" not in canon.columns:
        return []
    opts = sorted([x for x in canon["prefecture_en"].astype(str).str.strip().unique().tolist() if x])
    return opts


# ---------- Load data ----------
manual_df = load_manual()
canon_en_options = load_canonical_prefectures()

# Fallback if canonical file missing
if not canon_en_options:
    canon_en_options = ["Attica"]


# ---------- Existing manual outlets ----------
st.subheader("Existing manual / independent outlets")

c1, c2, c3 = st.columns([2, 1, 1])
with c1:
    q = st.text_input("Search (name or url contains)", value="")
with c2:
    mt_filter = st.selectbox(
        "Media type",
        ["(all)", "website", "newspaper", "radio", "tv"],
        index=0,
    )
with c3:
    sort_choice = st.selectbox("Sort", ["Newest first", "Oldest first", "Name (A→Z)"], index=0)

view = manual_df.copy()
if q.strip():
    qq = q.strip().lower()
    view = view[
        view["name"].astype(str).str.lower().str.contains(qq, na=False)
        | view["url"].astype(str).str.lower().str.contains(qq, na=False)
    ].copy()

if mt_filter != "(all)":
    view = view[view["media_type"].astype(str).str.lower().str.strip() == mt_filter].copy()

if sort_choice == "Newest first":
    view = view.sort_values("added_at", ascending=False)
elif sort_choice == "Oldest first":
    view = view.sort_values("added_at", ascending=True)
else:
    view = view.sort_values("name", ascending=True)

if view.empty:
    st.info("No manual outlets yet (or no matches for your filters).")
else:
    st.dataframe(view, width="stretch", hide_index=True)

st.download_button(
    "Download manual outlets CSV",
    data=manual_df.to_csv(index=False).encode("utf-8"),
    file_name="manual_independent_outlets.csv",
    mime="text/csv",
    key="dl_manual_independent",
)

st.subheader("Edit an existing manual outlet")

if manual_df.empty:
    st.info("No manual outlets to edit yet.")
else:
    # Pick by name + url for clarity
    manual_df["_label"] = manual_df["name"].astype(str) + " — " + manual_df["url"].astype(str)
    labels = manual_df["_label"].tolist()
    sel = st.selectbox("Select outlet to edit", labels, index=0)

    row = manual_df.loc[manual_df["_label"] == sel].iloc[0].to_dict()
    edit_id = row["id"]

    with st.form("manual_edit_form", clear_on_submit=False):
        name_e = st.text_input("Outlet name *", value=row.get("name", ""))
        url_e_in = st.text_input("Website URL *", value=row.get("url", ""))

        col1, col2, col3 = st.columns(3)
        with col1:
            media_type_e = st.selectbox(
                "Media type *",
                ["website", "newspaper", "radio", "tv"],
                index=max(0, ["website", "newspaper", "radio", "tv"].index(row.get("media_type", "website") or "website")),
            )
            content_type_e = st.selectbox(
                "Content type *",
                ["news", "unknown", "sports", "other"],
                index=max(0, ["news", "unknown", "sports", "other"].index(row.get("content_type", "unknown") or "unknown")),
            )
        with col2:
            status_e = st.selectbox(
                "Status",
                ["operating", "unknown", "not_operating"],
                index=max(0, ["operating", "unknown", "not_operating"].index(row.get("status", "unknown") or "unknown")),
            )
            range_type_e = st.selectbox(
                "Range",
                ["national", "regional", "unknown"],
                index=max(0, ["national", "regional", "unknown"].index(row.get("range_type", "unknown") or "unknown")),
            )
        with col3:
            # Prefecture dropdown
            pref_val = row.get("prefecture_en", "")
            pref_index = canon_en_options.index(pref_val) if pref_val in canon_en_options else 0
            prefecture_en_e = st.selectbox("Prefecture (base)", canon_en_options, index=pref_index)

        owner_e = st.text_input("Owner / Publisher", value=row.get("owner", ""))

        st.markdown("**Social links (optional)**")
        s1, s2, s3 = st.columns(3)
        with s1:
            fb_e = st.text_input("Facebook URL", value=row.get("fb", ""))
        with s2:
            x_e = st.text_input("X (Twitter) URL", value=row.get("x", ""))
        with s3:
            youtube_e = st.text_input("YouTube URL", value=row.get("youtube", ""))

        notes_e = st.text_area("Notes", value=row.get("notes", ""), height=90)
        updated_by = st.text_input("Updated by", value="manual")

        save_edit = st.form_submit_button("Save changes")
        delete_row = st.form_submit_button("Delete this entry")

    if save_edit:
        name_e = (name_e or "").strip()
        url_e = normalize_url(url_e_in)

        if not name_e:
            st.error("Name is required.")
        elif not url_e or not is_valid_url(url_e):
            st.error("A valid URL is required.")
        else:
            # Update row by id
            manual_df2 = manual_df.drop(columns=["_label"], errors="ignore").copy()
            mask = manual_df2["id"].astype(str) == str(edit_id)

            # Warn if this URL is already used by another manual entry
            other_same_url = manual_df2[
                (manual_df2["id"].astype(str) != str(edit_id))
                & (manual_df2["url"].astype(str).map(normalize_url) == url_e)
            ]
            if len(other_same_url) > 0:
                st.warning(
                    "Warning: another manual entry already has this URL. "
                    "Saving will create duplicate URLs in manual_outlets.csv."
                )

            manual_df2.loc[mask, "name"] = name_e
            manual_df2.loc[mask, "url"] = url_e
            manual_df2.loc[mask, "media_type"] = media_type_e
            manual_df2.loc[mask, "content_type"] = content_type_e
            manual_df2.loc[mask, "status"] = status_e
            manual_df2.loc[mask, "range_type"] = range_type_e
            manual_df2.loc[mask, "prefecture_en"] = prefecture_en_e
            manual_df2.loc[mask, "owner"] = (owner_e or "").strip()
            manual_df2.loc[mask, "fb"] = normalize_url(fb_e) if (fb_e or "").strip() else ""
            manual_df2.loc[mask, "x"] = normalize_url(x_e) if (x_e or "").strip() else ""
            manual_df2.loc[mask, "youtube"] = normalize_url(youtube_e) if (youtube_e or "").strip() else ""
            manual_df2.loc[mask, "notes"] = (notes_e or "").strip()
            manual_df2.loc[mask, "updated_by"] = (updated_by or "manual").strip()
            manual_df2.loc[mask, "updated_at"] = utc_now_iso()

            save_manual(manual_df2)
            st.success("Saved changes. Refreshing…")
            st.rerun()

    if delete_row:
        manual_df2 = manual_df.drop(columns=["_label"], errors="ignore").copy()
        manual_df2 = manual_df2[manual_df2["id"].astype(str) != str(edit_id)].copy()
        save_manual(manual_df2)
        st.success("Deleted. Refreshing…")
        st.rerun()


st.divider()

# ---------- Add new outlet ----------
st.subheader("Add a new outlet")

with st.form("manual_add_form", clear_on_submit=True):
    name = st.text_input("Outlet name *")
    url_in = st.text_input("Website URL *", help="Paste the main homepage URL (e.g. https://thepressproject.gr/)")

    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        media_type = st.selectbox("Media type *", ["website", "newspaper", "radio", "tv"], index=0)
        content_type = st.selectbox("Content type *", ["news", "unknown", "sports", "other"], index=0)
    with col2:
        status = st.selectbox("Status", ["operating", "unknown", "not_operating"], index=0)
        range_type = st.selectbox("Range", ["national", "regional", "unknown"], index=0)
    with col3:
        prefecture_en = st.selectbox("Prefecture (base)", canon_en_options, index=0)

    owner = st.text_input("Owner / Publisher")

    st.markdown("**Social links (optional)**")
    s1, s2, s3 = st.columns(3)
    with s1:
        fb = st.text_input("Facebook URL", placeholder="https://www.facebook.com/...")
    with s2:
        x_url = st.text_input("X (Twitter) URL", placeholder="https://x.com/...")
    with s3:
        youtube = st.text_input("YouTube URL", placeholder="https://www.youtube.com/@...")

    notes = st.text_area("Notes (why not in ESR/MT?)", height=90)

    added_by = st.text_input("Added by", value="manual")

    submitted = st.form_submit_button("Add outlet")

if submitted:
    name2 = (name or "").strip()
    url2 = normalize_url(url_in)

    errors = []
    if not name2:
        errors.append("Name is required.")
    if not url2 or not is_valid_url(url2):
        errors.append("A valid URL is required (include domain; scheme optional).")

    if errors:
        st.error(" ".join(errors))
    else:
        # URL validation
        for label, val in [("Facebook", fb), ("X", x_url), ("YouTube", youtube)]:
            v = normalize_url(val) if val.strip() else ""
            if v and not is_valid_url(v):
                st.warning(f"{label} link doesn't look like a valid URL; it will still be saved as-is.")

        # Minimal duplicate check inside manual list
        if (manual_df["url"].astype(str) == url2).any():
            st.warning("This URL already exists in manual outlets. Not adding a duplicate.")
        else:
            row = {
                "id": make_manual_id(name2, url2),
                "name": name2,
                "url": url2,
                "media_type": media_type,
                "content_type": content_type,
                "status": status,
                "range_type": range_type,
                "prefecture_en": prefecture_en,
                "owner": (owner or "").strip(),
                "fb": normalize_url(fb) if fb.strip() else "",
                "x": normalize_url(x_url) if x_url.strip() else "",
                "youtube": normalize_url(youtube) if youtube.strip() else "",
                "notes": (notes or "").strip(),
                "added_by": (added_by or "manual").strip(),
                "added_at": utc_now_iso(),
            }

            out_df = pd.concat([manual_df, pd.DataFrame([row])], ignore_index=True)
            save_manual(out_df)
            st.success("Added. Refreshing…")
            st.rerun()

