# Data Dictionary – Greek News Media Registry

This document describes the structure, meaning, and allowed values of the datasets
produced by the Greek News Media Registry project.

The registry is designed to be auditable and reproducible.
All fields originate either from authoritative public sources or from documented manual review.

---

## 1. Final Outlet Registry (`final_outlets.parquet`)

One row per **unique outlet** that satisfies the inclusion criteria
(operating + editorial content + valid website).

### Core Identifiers

| Field | Type | Description |
|-----|-----|------------|
| `id` | string | Stable unique identifier for the outlet (hash-based). |
| `name` | string | Canonical outlet name. |
| `owner` | string | Ownership entity name (as recorded in source or manual review). |

---

### Media Classification

| Field | Type | Allowed values | Description |
|-----|-----|---------------|-------------|
| `media_type` | string | `tv`, `radio`, `newspaper`, `website` | Primary medium of the outlet. |
| `frequency` | string | `daily`, `weekly`, `periodical`, `unknown` | Publication or broadcast frequency (mainly for press). |
| `range_type` | string | `national`, `regional` | Geographic coverage of the outlet. |
| `content_type` | string | `news`, `sports` | Editorial focus of the outlet. |

Notes:
- `website` indicates a web-based outlet, not necessarily web-native.
- `content_type=other` outlets are excluded from the final registry.

---

### Geographic Information

| Field | Type | Description |
|-----|-----|-------------|
| `prefecture_en` | string | Canonical English name of the prefecture where the outlet is based. |

Notes:
- Prefectures are normalized via editable alias tables.
- Attica sub-regions are merged under `Attica`.

---

### Website & Online Presence

| Field | Type | Description |
|-----|-----|-------------|
| `url` | string | Primary website URL of the outlet. |
| `fb` | string | Facebook page URL (if available). |
| `x` | string | X / Twitter account URL (if available). |
| `youtube` | string | YouTube channel URL (if available). |

---

### Operational Status

| Field | Type | Allowed values | Description |
|-----|-----|---------------|-------------|
| `status` | string | `operating` | Operational status (final registry includes only operating outlets). |

---

## 2. Gold Registry (`gold_outlets.parquet`)

Intermediate unified dataset including **all outlets** from all sources,
before final inclusion/exclusion rules are applied.

Contains all fields of the final registry **plus** the following:

### Source & Provenance

| Field | Type | Description |
|-----|-----|-------------|
| `source_name` | string | Source registry identifier (e.g. `esr_tv`, `mt_press`). |
| `row_id` | string | Unique identifier of the row in the source snapshot. |
| `snapshot_date` | date | Date when the source snapshot was taken. |

---

### Raw Source Fields

| Field | Type | Description |
|-----|-----|-------------|
| `name_raw` | string | Outlet name as recorded in the original source. |
| `owner_raw` | string | Owner name as recorded in the original source. |
| `prefecture_raw` | string | Raw prefecture or tax office value from source. |
| `content_type_raw` | string | Raw content type code or description from source. |
| `range_raw` | string | Raw geographic range value from source. |

---

### Review & Override Fields

| Field | Type | Allowed values | Description |
|-----|-----|---------------|-------------|
| `url_status` | string | `ok`, `no_website`, `broken`, `paywalled` | Result of manual URL verification. |
| `notes` | string | Free-text notes added during manual review. |
| `media_type_override` | string | Same as `media_type` | Manual correction of media type. |
| `content_type_override` | string | `news`, `sports`, `other` | Manual correction of content type. |
| `status_override` | string | `operating`, `not_operating`, `not_found` | Manual correction of status. |

Overrides take precedence over automatically inferred values.

---

## 3. URL Registry (`final_urls.parquet`)

One row per **unique website domain**, derived from the final outlet registry.

### URL Identity

| Field | Type | Description |
|-----|-----|-------------|
| `domain` | string | Normalized website domain. |
| `url` | string | Canonical URL associated with the domain. |

---

### Media Associations

| Field | Type | Description |
|-----|-----|-------------|
| `has_tv` | boolean | Domain is used by at least one TV outlet. |
| `has_radio` | boolean | Domain is used by at least one radio outlet. |
| `has_newspaper` | boolean | Domain is used by at least one newspaper outlet. |
| `has_website` | boolean | Domain is used by a web-based outlet. |
| `web_native` | boolean | Domain belongs exclusively to web-based outlets. |

---

### Counts & Flags

| Field | Type | Description |
|-----|-----|-------------|
| `outlet_count` | integer | Number of outlets sharing the domain. |
| `media_types` | string | Comma-separated list of media types using the domain. |
| `has_manual` | boolean | Domain originates from or is affected by manual entries. |

---

## 4. Manual & Independent Entries

Manual entries follow the same schema as gold outlets, with:

- `source_name = manual_independent`
- stable IDs generated from name + domain
- full participation in review and deduplication logic

---

## 5. Missing & Excluded Rows

Outlets excluded from the final registry remain in the gold dataset and are classified by reason:

- not operating
- not found
- missing website
- broken or paywalled website
- non-editorial content (`content_type=other`)

Exclusions are **explicit and reversible**.

---

## 6. Conventions & Notes

- All string values are trimmed and normalized
- Empty values are stored as empty strings or nulls depending on stage
- Boolean fields may be stored as 0/1 in parquet files
- Hash-based IDs are stable across rebuilds

---

## 7. Versioning

Schema changes are documented via:
- Git history
- migration logic in the pipeline
- updated documentation files


