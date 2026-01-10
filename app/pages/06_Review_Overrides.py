import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import urllib.parse
import streamlit as st
import pandas as pd

from src.config import get_paths
from src.overrides.outlet_overrides import (
    load_outlet_overrides,
    upsert_outlet_override,
    apply_outlet_overrides,
)

st.set_page_config(page_title="Review Overrides", layout="wide")

from app.demo import is_demo_mode

if is_demo_mode():
    st.warning("Demo mode: read-only. Overrides editing is disabled.")
    st.stop()

root = Path(__file__).resolve().parents[2]
paths = get_paths(root)

st.title("Review Overrides")

gold_path = paths.gold / "registry_gold.parquet"
if not gold_path.exists():
    st.error("Missing data/gold/registry_gold.parquet. Build Gold first.")
    st.stop()

overrides_path = paths.overrides / "outlet_overrides.csv"

gold = pd.read_parquet(gold_path)
overrides = load_outlet_overrides(overrides_path)
gold = apply_outlet_overrides(gold, overrides)

st.subheader("Scope")

scope_ct = st.multiselect(
    "Only include outlets with these content_type values",
    options=["(blank)", "unknown", "news", "sports", "other"],
    default=["(blank)", "unknown", "news"],
)

def ct_in_scope(df):
    ct = df["content_type"].astype(str).str.strip().str.lower()
    blank = (df["content_type"].isna()) | (ct == "") | (ct == "nan")
    keep = pd.Series(False, index=df.index)

    if "(blank)" in scope_ct:
        keep = keep | blank
    if "unknown" in scope_ct:
        keep = keep | (ct == "unknown")
    if "news" in scope_ct:
        keep = keep | (ct == "news")
    if "sports" in scope_ct:
        keep = keep | (ct == "sports")
    if "other" in scope_ct:
        keep = keep | (ct == "other")
    return keep

scope_status = st.multiselect(
    "Only include outlets with these status values",
    options=["(blank)", "unknown", "operating", "not_operating", "not_found"],
    default=["(blank)", "unknown", "operating"],
)

def status_in_scope(df):
    s = df["status"].astype(str).str.strip().str.lower()
    blank = (df["status"].isna()) | (s == "") | (s == "nan")
    keep = pd.Series(False, index=df.index)

    if "(blank)" in scope_status:
        keep = keep | blank
    if "unknown" in scope_status:
        keep = keep | (s == "unknown")
    if "operating" in scope_status:
        keep = keep | (s == "operating")
    if "not_operating" in scope_status:
        keep = keep | (s == "not_operating")
    if "not_found" in scope_status:
        keep = keep | (s == "not_found")
    return keep


# ---- Queue selection ----
st.subheader("Queue")

queue_type = st.selectbox(
    "Choose a queue",
    ["Excluded from Final (any reason)", "Missing URL", "Missing Socials", "Needs content_type", "Needs status"],
    index=0,
)

pref_filter = st.selectbox(
    "Filter by prefecture_en (optional)",
    options=["(all)"] + sorted([p for p in gold.get("prefecture_en", pd.Series([], dtype=str)).dropna().unique().tolist() if str(p).strip() != ""]),
    index=0,
)

# ---- Extra filters ----
st.subheader("Filters")

# Filter by media_type
media_type_all = sorted(
    [m for m in gold.get("media_type", pd.Series([], dtype=str)).dropna().astype(str).unique().tolist() if str(m).strip() != ""]
)
media_type_sel = st.multiselect(
    "Filter by media_type (optional)",
    options=media_type_all,
    default=media_type_all,
)

# “Almost final except content_type” (high-yield false exclusions)
only_excluded_due_to_content_type = st.checkbox(
    "Only show outlets excluded ONLY because of content_type (operating + url_status ok + has URL, but content_type != news)",
    value=False,
)


def is_blank(s):
    return s.isna() | (s.astype(str).str.strip() == "")

q = gold.copy()
## Apply scope filters
#q = q[ct_in_scope(q) & status_in_scope(q)].copy()

# Apply scope filters for the “working” queues.
# IMPORTANT: for "Excluded from Final (any reason)", we ignore scope.
if queue_type != "Excluded from Final (any reason)":
    q = q[ct_in_scope(q) & status_in_scope(q)].copy()

if pref_filter != "(all)" and "prefecture_en" in q.columns:
    q = q[q["prefecture_en"].astype(str).str.strip() == pref_filter].copy()

# Apply media_type filter
if media_type_sel and "media_type" in q.columns:
    q = q[q["media_type"].astype(str).str.strip().str.lower().isin([str(m).strip().lower() for m in media_type_sel])].copy()

if queue_type == "Excluded from Final (any reason)":
    def _norm(s):
        return s.astype(str).str.strip().str.lower()

    stt = _norm(q.get("status", pd.Series([""] * len(q))))
    ct = _norm(q.get("content_type", pd.Series([""] * len(q))))
    us = _norm(q.get("url_status", pd.Series(["ok"] * len(q))))

    url_raw = q.get("url", pd.Series([pd.NA] * len(q)))
    url = url_raw.fillna("").astype(str).str.strip().str.lower()
    has_url = (~url_raw.isna()) & (~url.isin(["", "nan", "<na>", "none"]))

    in_final = (stt == "operating") & (ct == "news") & (us == "ok") & (has_url)
    q = q[~in_final].copy()
#elif queue_type == "Missing URL":
#    # Only queue items that are missing URL AND still expected to have one
#    if "url_status" in q.columns:
#        q = q[is_blank(q["url"]) & (q["url_status"].astype(str).str.strip().str.lower() == "ok")].copy()
#    else:
#        q = q[is_blank(q["url"])].copy()
elif queue_type == "Missing URL":
    def _norm(s):
        return s.astype(str).str.strip().str.lower()

    stt = _norm(q.get("status", pd.Series([""] * len(q))))
    ct = _norm(q.get("content_type", pd.Series([""] * len(q))))
    us = _norm(q.get("url_status", pd.Series(["ok"] * len(q))))

    url_raw = q.get("url", pd.Series([pd.NA] * len(q)))
    url = url_raw.fillna("").astype(str).str.strip().str.lower()
    has_url = (~url_raw.isna()) & (~url.isin(["", "nan", "<na>", "none"]))

    # Missing URL = url_status ok, but no real URL
    q = q[(us == "ok") & (~has_url)].copy()
elif queue_type == "Missing Socials":
    q = q[is_blank(q["fb"]) | is_blank(q["x"]) | is_blank(q["youtube"])].copy()
elif queue_type == "Needs content_type":
    q = q[is_blank(q["content_type"]) | (q["content_type"].astype(str).str.strip() == "unknown")].copy()
elif queue_type == "Needs status":
    s = q["status"].astype(str).str.strip().str.lower()
    q = q[is_blank(q["status"]) | (s == "unknown")].copy()

# Apply “excluded ONLY because of content_type” filter (high-yield)
if only_excluded_due_to_content_type:
    def _norm(s):
        return s.astype(str).str.strip().str.lower()

    stt = _norm(q.get("status", pd.Series([""] * len(q))))
    ct = _norm(q.get("content_type", pd.Series([""] * len(q))))
    us = _norm(q.get("url_status", pd.Series(["ok"] * len(q))))

    url_raw = q.get("url", pd.Series([pd.NA] * len(q)))
    url = url_raw.fillna("").astype(str).str.strip().str.lower()
    has_url = (~url_raw.isna()) & (~url.isin(["", "nan", "<na>", "none"]))

    q = q[
        (stt == "operating")
        & (us == "ok")
        & (has_url)
        & (ct != "news")
    ].copy()


q = q.sort_values(["prefecture_en", "media_type", "name"], na_position="last")

st.caption(f"Items in queue: {len(q)}")

if len(q) == 0:
    st.success("Queue is empty 🎉")
    st.stop()

# Keep a pointer in session_state
key = f"queue_idx::{queue_type}::{pref_filter}"
if key not in st.session_state:
    st.session_state[key] = 0

idx = st.session_state[key]
if idx >= len(q):
    st.session_state[key] = 0
    idx = 0

row = q.iloc[idx].to_dict()

def _quick_override(patch: dict):
    # Minimal upsert: only fields in patch (plus id)
    from src.overrides.outlet_overrides import upsert_outlet_override

    payload = {"id": row["id"]}
    payload.update(patch)
    upsert_outlet_override(overrides_path, payload)

    # Advance pointer and reset form
    st.session_state[key] = min(st.session_state[key] + 1, max(len(q) - 1, 0))
    st.session_state["override_form_reset"] += 1
    st.rerun()

# Reset token to force new widget instances (clears form safely)
if "override_form_reset" not in st.session_state:
    st.session_state["override_form_reset"] = 0
reset = st.session_state["override_form_reset"]


# ---- Record display ----
st.subheader("Current item")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Index", f"{idx+1}/{len(q)}")
c2.metric("Media type", str(row.get("media_type", "")))
c3.metric("Prefecture", str(row.get("prefecture_en", "")))
c4.metric("Status", str(row.get("status", "")))

st.write(f"**{row.get('name','')}**")
st.write(f"Prefecture: **{row.get('prefecture_en','')}**")

name = str(row.get("name", "") or "").strip()
pref = str(row.get("prefecture_en", "") or "").strip()

google_q = f"{name} {pref} site:gr".strip()
google_url = "https://www.google.com/search?q=" + urllib.parse.quote(google_q)

fb_q = f"{name} {pref}".strip()
fb_url = "https://www.facebook.com/search/top/?q=" + urllib.parse.quote(fb_q)

x_q = f"{name} {pref}".strip()
x_url = "https://x.com/search?q=" + urllib.parse.quote(x_q) + "&src=typed_query"

yt_q = f"{name} {pref}".strip()
yt_url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote(yt_q)

b1, b2, b3, b4 = st.columns(4)
with b1:
    st.markdown(f'<a href="{google_url}" target="_blank" rel="noopener noreferrer">🔎 Google</a>', unsafe_allow_html=True)
with b2:
    st.markdown(f'<a href="{fb_url}" target="_blank" rel="noopener noreferrer">📘 Facebook</a>', unsafe_allow_html=True)
with b3:
    st.markdown(f'<a href="{x_url}" target="_blank" rel="noopener noreferrer">𝕏 X</a>', unsafe_allow_html=True)
with b4:
    st.markdown(f'<a href="{yt_url}" target="_blank" rel="noopener noreferrer">▶️ YouTube</a>', unsafe_allow_html=True)


st.write(f"Current content_type: **{row.get('content_type','')}**")
st.write(f"Current url_status: **{row.get('url_status','ok')}**")
if row.get("fb"):
    st.write(f"Facebook: {row.get('fb')}")
if row.get("x"):
    st.write(f"X: {row.get('x')}")
if row.get("youtube"):
    st.write(f"YouTube: {row.get('youtube')}")
st.caption(f"Owner: {row.get('owner','')}")

if row.get("url"):
    st.write(f"Current URL: {row.get('url')}")

# ---- Edit form ----
st.subheader("Fast actions")
st.caption("One-click overrides for common cases. These remove the current item from the queue when applicable.")

b1, b2, b3, b4, b5, b6 = st.columns(6)

with b1:
    if st.button("No website", use_container_width=True):
        _quick_override({"url_status": "no_website"})
with b2:
    if st.button("Paywalled", use_container_width=True):
        _quick_override({"url_status": "paywalled"})
with b3:
    if st.button("Broken URL", use_container_width=True):
        _quick_override({"url_status": "broken"})
with b4:
    if st.button("Not found", use_container_width=True):
        _quick_override({"status": "not_found"})
with b5:
    if st.button("Not news", use_container_width=True):
        _quick_override({"content_type": "other"})
with b6:
    if st.button("Sports", use_container_width=True):
        _quick_override({"content_type": "sports"})

st.subheader("Apply override")

with st.form("override_form", clear_on_submit=True):
    # Stable keys so we can clear fields after apply
    url = st.text_input("URL", value=str(row.get("url") or ""), key=f"ov_url_{reset}")

    url_status_options = ["ok", "paywalled", "no_website", "broken"]
    current_url_status = str(row.get("url_status") or "ok").strip() or "ok"
    if current_url_status not in url_status_options:
        current_url_status = "ok"

    url_status = st.selectbox(
        "URL status",
        url_status_options,
        index=url_status_options.index(current_url_status),
        key=f"ov_url_status_{reset}",
    )

    fb = st.text_input("Facebook URL", value=str(row.get("fb") or ""), key=f"ov_fb_{reset}")
    x = st.text_input("X (Twitter) URL", value=str(row.get("x") or ""), key=f"ov_x_{reset}")
    youtube = st.text_input("YouTube URL", value=str(row.get("youtube") or ""), key=f"ov_youtube_{reset}")

    status_options = ["", "operating", "not_operating", "not_found"]
    current_status = str(row.get("status") or "").strip().lower()

    if current_status not in status_options:
        current_status = ""

    status = st.selectbox(
        "Status (optional)",
        status_options,
        index=status_options.index(current_status),
    )

    content_type_options = ["", "news", "sports", "other", "unknown"]
    current_ct = str(row.get("content_type") or "").strip().lower()

    # if current is not in options (e.g. None), default to blank
    if current_ct not in content_type_options:
        current_ct = ""

    content_type = st.selectbox(
        "Content type (optional)",
        content_type_options,
        index=content_type_options.index(current_ct),
    )

    media_type_options = ["", "tv", "radio", "newspaper", "website", "unknown"]
    current_mt = str(row.get("media_type") or "").strip().lower()
    if current_mt not in media_type_options:
        current_mt = ""

    media_type = st.selectbox(
        "Media type (optional)",
        media_type_options,
        index=media_type_options.index(current_mt),
    )

    notes = st.text_input("Notes (optional)", value="")

    colA, colB = st.columns(2)
    applied = colA.form_submit_button("Apply override (and remove from queue)", type="primary")
    next_only = colB.form_submit_button("Next (skip for now)")

    if applied:
        upsert_outlet_override(
            overrides_path,
            {
                "id": row["id"],
                "url": url,
                "url_status": url_status,
                "fb": fb,
                "x": x,
                "youtube": youtube,
                "status": status,
                "content_type": content_type,
                "media_type": media_type,
                "notes": notes,
            },
        )
        # Move to next index; since this item will likely drop from queue after rerun, we keep same idx.
        st.success("Saved override.")
        # Advance pointer; safe even if item is removed from queue on rerun
        st.session_state[key] = min(st.session_state[key] + 1, max(len(q) - 1, 0))
        # Force form fields to reset on next render
        st.session_state["override_form_reset"] += 1
        st.rerun()

    if next_only:
        st.session_state[key] = min(idx + 1, len(q) - 1)
        st.rerun()

# Convenience controls
st.divider()
col1, col2 = st.columns(2)
with col1:
    if st.button("Previous"):
        st.session_state[key] = max(idx - 1, 0)
        st.rerun()
with col2:
    if st.button("Reset queue pointer"):
        st.session_state[key] = 0
        st.rerun()

