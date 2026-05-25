# Data Model — Breathe ESG Emissions Platform

## Core Design Principles

1. **Every emission record, regardless of source, normalises to one table** (`EmissionRecord`). Analysts see a uniform interface; the source provenance is preserved in `source_system`, `source_record_id`, and the verbatim `raw_data` JSON field.
2. **Multi-tenancy is row-level**: every `EmissionRecord` and `IngestionBatch` carries a `tenant` FK. There is no shared data between tenants. A `TenantUser` join table maps Django `User` to `Tenant` + role.
3. **Audit trail is append-only**: `AuditLog` rows are created but never updated or deleted. Every state transition on an `EmissionRecord` (created, approved, rejected, flagged, edited) writes a log entry with the acting user, timestamp, and a diff/note payload.
4. **Lock on approval**: `is_locked = True` is set when a record is approved. Locked records cannot be modified, ensuring audit integrity. Rejection does not lock (the record can be re-submitted via a new batch if the source data is corrected).

---

## Tables

### `Tenant`
| Field | Type | Notes |
|-------|------|-------|
| id | UUID PK | |
| name | varchar(255) | e.g. "Acme Industries Ltd." |
| slug | slug, unique | URL-safe identifier |
| created_at | datetime | |

### `TenantUser`
Maps Django `User` → `Tenant` with a role.
| Field | Type | Notes |
|-------|------|-------|
| user | FK User (1:1) | |
| tenant | FK Tenant | |
| role | enum | admin / analyst / viewer |

### `IngestionBatch`
One row per upload/pull operation. Tracks provenance at the batch level.
| Field | Type | Notes |
|-------|------|-------|
| id | UUID PK | |
| tenant | FK Tenant | |
| source_type | enum | sap / utility / travel |
| file_name | varchar | original filename |
| status | enum | processing / completed / failed |
| total_rows | int | rows attempted |
| passed_rows | int | rows successfully parsed |
| failed_rows | int | rows that threw a ParseError |
| ingested_by | FK User | nullable |
| ingested_at | datetime | |
| notes | text | error summary if failed |

### `EmissionRecord` ← central table
| Field | Type | Notes |
|-------|------|-------|
| id | UUID PK | |
| tenant | FK Tenant | row-level tenancy |
| batch | FK IngestionBatch | which import created this |
| **scope** | char(1) | 1 / 2 / 3 — GHG Protocol |
| **category** | varchar(50) | stationary_combustion, purchased_electricity, business_travel_air, etc. |
| activity_value | Decimal(18,4) | normalised quantity |
| activity_unit | varchar(30) | litres / kWh / km / nights / USD |
| emission_factor | Decimal(12,6) | kgCO₂e per activity_unit |
| emission_factor_source | varchar | e.g. "DEFRA 2023 — diesel" |
| co2e_kg | Decimal(18,4) | computed: activity_value × emission_factor |
| period_start | date | |
| period_end | date | |
| **source_system** | varchar | sap / utility_csv / concur_csv |
| source_record_id | varchar | FK from source (e.g. SAP document number) |
| raw_data | JSON | verbatim parsed row — never modified |
| facility_code | varchar | plant code, meter ID, cost centre |
| facility_name | varchar | human-readable lookup result |
| country | varchar | |
| **status** | enum | pending / approved / rejected / flagged |
| review_notes | text | analyst comment |
| reviewed_by | FK User | nullable |
| reviewed_at | datetime | nullable |
| **is_suspicious** | bool | set by parser heuristics or manually |
| suspicion_reason | text | parser explanation |
| **is_locked** | bool | true after approval — immutable |
| created_at | datetime | |
| updated_at | datetime | |

**Scope assignment logic:**
- Scope 1: fuel combustion identified via material code → diesel/petrol/LPG/CNG/HFO
- Scope 2: all utility electricity records
- Scope 3: procurement rows (spend-based) + all travel segments

### `AuditLog`
Append-only. Never updated.
| Field | Type | Notes |
|-------|------|-------|
| id | UUID PK | |
| record | FK EmissionRecord | |
| user | FK User | nullable (system actions) |
| action | varchar | created / approved / rejected / flagged / edited |
| detail | JSON | diff, notes, or metadata |
| timestamp | datetime auto | |

### `ParseError`
Rows that failed parsing. Surfaced in the review dashboard for analyst inspection.
| Field | Type | Notes |
|-------|------|-------|
| id | UUID PK | |
| batch | FK IngestionBatch | |
| row_number | int | nullable |
| raw_row | JSON | verbatim input |
| error_message | text | exception message |
| created_at | datetime | |

---

## Unit Normalisation

All activity values are normalised to a canonical unit before storage:

| Category | Canonical unit | Common inputs |
|----------|---------------|---------------|
| Fuel combustion | litres | L, m³, kg, GAL, ton |
| Electricity | kWh | MWh, kWh |
| Business travel — air | km | km, or derived from IATA codes |
| Business travel — hotel | nights | integer |
| Business travel — ground | km | km |
| Procurement | USD | INR/EUR converted or used as-is |

---

## What would need to change in production

1. **Currency normalisation**: procurement spend should be converted to USD using real FX rates before storage. Currently uses raw INR/USD as-is.
2. **Emission factor versioning**: factors are hardcoded constants. Production needs a `EmissionFactor` table with vintage year, geography, and source, so historical records aren't retroactively recalculated.
3. **PostgreSQL**: SQLite is fine for the prototype. Row-level security (RLS) policies in Postgres would be the right multi-tenancy enforcement layer in production.
4. **Soft deletes**: records should be soft-deleted (`deleted_at`) rather than hard-deleted to preserve audit completeness.
