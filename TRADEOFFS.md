# Tradeoffs — Three Deliberate Omissions

## 1. No real-time API pull from SAP / Concur / utility portals

**What I built instead:** File upload (drag-and-drop CSV).

**Why I skipped it:** Implementing live API integrations would require OAuth flows, credential storage (secrets management), retry/backoff logic, webhook receivers, and rate-limit handling — roughly 3–4x more infrastructure than file upload. For an onboarding prototype with a 4-day window, file upload is the correct minimum viable ingestion mechanism. It also mirrors the actual first-week workflow: clients send files over email or shared drives while OAuth access is being arranged.

**What live integration would need:** A `DataSource` model storing encrypted credentials, a Celery task queue for scheduled pulls, a webhook endpoint for push notifications, and idempotency logic to avoid double-counting records already ingested.

**Cost of omission:** Analysts must manually download and upload files. This is acceptable for a prototype but would become friction at scale (>5 clients, >monthly frequency).

---

## 2. No emission factor versioning / factor database

**What I built instead:** Hardcoded Decimal constants in `parsers.py`.

**Why I skipped it:** A production-grade system needs an `EmissionFactor` table with: factor value, unit, category, geography, vintage year, source (DEFRA/EPA/IPCC), and valid-from/valid-to dates. This matters because:
- DEFRA updates factors annually (UK electricity grid gets greener each year)
- A record ingested with 2022 factors should not be retroactively recalculated when 2023 factors are published
- Different geographies need different factors (India grid ≠ UK grid ≠ US grid)

Building this properly requires a factor management UI, import tooling for DEFRA/EPA spreadsheets, and a versioned linkage between `EmissionRecord` and the `EmissionFactor` used at ingestion time.

**Cost of omission:** All records use a single India-specific grid factor for electricity (0.708 kgCO₂e/kWh — CEA 2023) and fixed fuel factors. If the client has overseas facilities or operates across multiple grids, the numbers will be wrong. This is called out in SOURCES.md.

---

## 3. No export / audit report generation

**What I built instead:** A review dashboard where analysts can approve/reject records.

**Why I skipped it:** The final step of the workflow — generating a structured audit export (GHG inventory report, CDP disclosure template, GRI 305 tables) — requires knowing the reporting standard, consolidation boundary (equity share vs operational control), and base year. These are business logic decisions that need product input, not engineering assumptions. Building a PDF/Excel exporter on top of undecided business logic would produce the wrong artifact confidently.

**What it would need:** A `ReportTemplate` model, a report generation pipeline (likely a background task), and either PDF (WeasyPrint) or Excel (openpyxl) output with scope-by-scope breakdowns, methodology notes, and the locked record IDs that constitute the inventory.

**Cost of omission:** Analysts can review and approve records but cannot produce the final deliverable for auditors without a manual export step. Given the 4-day scope, this is the right call.
