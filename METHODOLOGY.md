# Methodology – Greek News Media Registry

This document explains the data sources, processing rules,
manual review logic, and inclusion criteria used to build the registry.

---

## Human-in-the-Loop, Data-Driven Approach

The registry is built using a hybrid methodology that combines automated, data-driven processing with structured human review.

Authoritative public registers provide the backbone of the dataset and are ingested through deterministic, reproducible pipelines. Automated rules are used wherever reliable signals exist (e.g. operational status codes, declared media type, geographic scope, URL normalization and deduplication). This ensures consistency, scalability, and traceability across rebuilds.

However, several critical attributes of media outlets cannot be inferred safely from source data alone. These include editorial focus (news vs sports vs other), actual website validity, paywall status, operational reality beyond formal registration, and the identification of independent or missing outlets. For these cases, the system intentionally introduces a human-in-the-loop review stage.

Manual review is implemented through a queue-based interface that:
- limits human intervention to clearly defined decision points,
- records every override explicitly as data,
- preserves original source values,
- allows corrections and re-review over time.

Human decisions are therefore not ad-hoc edits but first-class, auditable inputs to the pipeline. The final registry reflects the combination of automated ingestion and documented human judgment, enabling both reproducibility and analytical reliability.

---

## 1. Authoritative Sources

### 1.1 National Council for Radio and Television (ESR)

**Source:** https://www.esr.gr/

#### Television
- National TV stations: `tve.xls`
- Regional TV stations: `tvtp.xls`

Key fields used:
- Station name
- Operational status (Λ / ΜΛ)
- Program profile (news / non-news)
- Coverage range (national / regional)
- Prefecture
- Ownership entity

#### Radio
- Operating radio stations: `bnl.xlsx`
- One sheet per prefecture

Key fields used:
- Station name
- Operational status
- Program profile
- Ownership entity

---

### 1.2 Register of Print & Electronic Media (MT Media)

**Source:** https://mt.media.gov.gr/

#### Press (Print)
- Exported Excel registry

Key fields used:
- Publication name
- Ownership entity
- Tax office (used to infer prefecture)
- Publication type (used to infer media type, range, frequency)

Magazines are excluded from the final registry.

#### Websites
- Exported Excel registry

Key fields used:
- Website URL
- Ownership entity
- Tax office (used to infer prefecture)

This registry includes:
- press websites
- broadcaster websites
- web-native outlets

---

## 2. Geographic Normalization

- All outlets are assigned a **canonical prefecture (English)**
- Source prefecture values are aliased via editable CSV tables
- Attica sub-regions are merged into a single prefecture (Attica)

Prefecture aliasing is fully transparent and editable in the app UI.

---

## 3. URL Handling & Deduplication

- URLs are normalized to domains
- Multiple outlets may legitimately share the same domain
- A separate **URL registry** is built to:
  - deduplicate domains
  - detect cross-media websites (e.g. TV + newspaper)
  - identify web-native outlets

An outlet’s website does not automatically make it “web-native”.

---

## 4. Manual Overrides & Review

Certain attributes require human verification:
- content type (news / sports / other)
- operational status
- URL validity
- social media presence

Manual review is performed through a queue-based UI:
- each decision is stored
- no data is overwritten
- incorrect decisions can be corrected later

---

## 5. Inclusion Criteria (Final Registry)

An outlet is included in the **final registry** if and only if:

- status = operating
- content_type ∈ {news, sports}
- has a valid website URL
- URL is not marked as broken, paywalled, or non-existent

All other outlets remain excluded but visible for auditability.

---

## 6. Independent & Manual Additions

Some legitimate outlets are not listed in official registers
(e.g. independent newspapers or investigative websites).

These can be:
- manually added via the app
- reviewed like all other outlets
- deduplicated against existing data

Manual entries are clearly marked and traceable.

---

## 7. Transparency & Reproducibility

Key principles:
- original source data is preserved
- every transformation is deterministic
- every exclusion has a reason
- every manual decision is recorded

The registry is designed to be:
- reproducible
- auditable
- extensible over time

---

## 8. Known Limitations

- Ownership is not yet fully normalized
- Funding data is not yet integrated
- Some outlets require continuous monitoring
- Public broadcasters require special handling

These are considered future extensions.

