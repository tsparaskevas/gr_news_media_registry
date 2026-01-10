# Greek News Media Registry

An auditable, reproducible registry of Greek news media outlets (TV, radio, press, and web-native),
built from official public registers and enriched through structured manual review.

The project combines automated ingestion from authoritative sources with a transparent,
human-in-the-loop review process implemented in a Streamlit application.

---

## Purpose

The goal of this project is to create a **clean, documented, and reproducible registry of active Greek news media outlets with websites**, suitable for:

- media pluralism and ownership analysis
- academic research
- investigative journalism
- policy and transparency projects

The registry focuses on **editorial outlets** (news and sports), excludes inactive media,
and clearly documents all exclusions and manual decisions.

---

## What the Registry Contains

For each outlet, the final registry may include:

- unique outlet ID
- name
- website URL
- media type (tv, radio, newspaper, web-native)
- frequency (daily, weekly, periodical, unknown)
- geographic range (national / regional)
- prefecture (canonical English name)
- content type (news, sports)
- operational status
- social media links (Facebook, X, YouTube)
- ownership name

---

## Data Pipeline (Bronze → Silver → Gold → Final)

The pipeline is deliberately staged to ensure auditability:

### 1. Bronze (Raw snapshots)
- Original files downloaded from official sources
- Stored with snapshot dates
- Never modified

### 2. Silver (Normalized & cleaned)
- Relevant columns extracted
- Greek codes mapped to readable values
- Prefectures aliased to canonical English names
- Initial media type / range / frequency assigned

### 3. Gold (Unified registry)
- All sources merged into a single table
- URLs matched and deduplicated
- Manual overrides applied
- Status, content type, and URL validity enforced

### 4. Final registry
- Only **operating outlets**
- Only **editorial content (news or sports)**
- Only **outlets with valid websites**
- Fully traceable back to source rows

---

## Streamlit App

The Streamlit app is the primary interface for:

- refreshing official snapshots
- reviewing and fixing prefecture aliases
- manual outlet review (status, content type, URL, socials)
- tracking progress and exclusions
- exploring the final registry
- visualizing outlets on a prefecture map

Key pages include:
- Pipeline
- Prefecture Aliases
- Review Overrides
- Final Registry
- Map (Prefectures)
- Manual / Independent Intake

---

## Demo (Streamlit Cloud)

A read-only demo is hosted on Streamlit Cloud.

### What works
- Browse the published Final Registry (editorial/news/sports)
- Inspect exclusions and URL registry
- View the prefecture choropleth map and drill down by prefecture
- Download published CSV outputs

### What is hidden/disabled in the demo (and why)
The following pages are hidden in the cloud demo:
- Pipeline (snapshot refresh + rebuild)
- Prefecture alias editing
- Review overrides / manual review queue
- Manual / independent intake

Reason: Streamlit Cloud provides an ephemeral filesystem and no persistence by default, so edits to `data/overrides/` would not reliably persist across restarts or redeploys. The cloud demo therefore ships with pre-built published artifacts under `data/published/` and focuses on exploration/inspection only.

---

## Full functionality locally

### Requirements
- Python 3.10+ (recommended)
- A virtual environment tool (venv, uv, conda)

### Setup
```bash
git clone https://github.com/tsparaskevas/gr_news_media_registry.git
cd gr_news_media_registry

python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

pip install -r requirements-full.txt
```

### Run the app
From the project root:
```bash
streamlit run app/home.py
```

### Build/publish data (optional)
Use the Pipeline page inside the app to:
- refresh official snapshots
- rebuild Bronze → Silver → Gold
- publish final outputs

Published artifacts are written under:
- data/published/

---

## Citation

If you use this app or dataset(s), please cite:

### How to cite: software vs dataset

This repository serves two related but distinct purposes:

1. Software – the pipeline and Streamlit application used to build, review, and publish the registry

2. Dataset(s) – the published outputs produced by the pipeline (e.g. the final registry of Greek media outlets)

Please cite according to what you are actually using.

### Citing the software (this repository)

If you use the codebase, methodology, or application (for example to reproduce the registry, adapt it to another country, or study the workflow), cite the software:

Paraskevas, T. (2026). Greek News Media Registry (Version 1.0.0) [Software]. GitHub.
https://github.com/tsparaskevas/gr_news_media_registry

```bibtex
@software{Paraskevas_GreekNewsMediaRegistry_2026,
  author  = {Paraskevas, Thodoris},
  title   = {Greek News Media Registry},
  year    = {2026},
  version = {1.0.0},
  url     = {https://github.com/tsparaskevas/gr_news_media_registry},
  note    = {Software}
}
```

### Citing the dataset(s)

If you use published data outputs from this project (for example the final registry of news media outlets, URL registries, or derived statistics), cite the dataset and the software.

Until a separate DOI is issued for dataset releases, please cite:

Paraskevas, T. (2026). Greek News Media Registry – Published Data (Version 1.0.0) [Dataset].
Generated using the Greek News Media Registry software.
https://github.com/tsparaskevas/gr_news_media_registry

You may optionally also cite the specific release tag or commit hash used to generate the data.

---

## Manual Review Philosophy

Not all information can be reliably inferred automatically.

The app therefore supports:
- queue-based manual review
- explicit override logging
- separation between **included**, **excluded**, and **pending** outlets
- later re-review without data loss

Manual decisions are treated as **first-class data**, not ad-hoc fixes.

---

## Scope & Limitations

- The registry is **not a list of all Greek media ever existing**
- It reflects the **current state of official registers + verified independent outlets**
- Some outlets may be missing until manually added
- Ownership structures are recorded but not yet normalized
- Public broadcasters are treated separately

See `METHODOLOGY.md` for full details.

---

## License

This project is intended for research and public-interest use and is licensed under the MIT License. See `LICENSE` for details.

© 2026 Thodoris Paraskevas

