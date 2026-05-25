# Breathe ESG — Emissions Ingestion & Review Platform

A Django REST + React prototype that ingests emissions and activity data from three enterprise sources, normalises it, and surfaces a review dashboard where analysts can sign off before data goes to auditors.

## Live Demo

> Deploy to Render/Railway — see deployment section below.

**Demo credentials:**
- `admin / admin123` — full access
- `analyst / analyst123` — review access

---

## Architecture

```
breathe-esg/
├── backend/          # Django 5 + DRF
│   ├── api/
│   │   ├── models.py       # Data model (Tenant, EmissionRecord, AuditLog, ...)
│   │   ├── parsers.py      # SAP / Utility / Travel CSV parsers
│   │   ├── views.py        # REST endpoints
│   │   ├── serializers.py
│   │   └── management/commands/seed.py
│   └── config/             # Django settings, URLs
├── frontend/         # React + Tailwind CSS
│   └── src/
│       ├── pages/    # Dashboard, Ingest, Review, Batches
│       └── components/
├── sample_data/      # Test CSV files for all three sources
├── MODEL.md          # Data model documentation
├── DECISIONS.md      # Ambiguity resolution log
├── TRADEOFFS.md      # Deliberate omissions
└── SOURCES.md        # Source format research
```

---

## Quick Start

### Backend

```bash
cd backend
pip3 install django djangorestframework django-cors-headers
python3 manage.py migrate
python3 manage.py seed          # creates demo tenant, users, sample records
python3 manage.py runserver
```

### Frontend

```bash
cd frontend
npm install
REACT_APP_API_URL=http://localhost:8000/api npm start
```

---

## The Three Sources

| Source | Format | Scope | Ingestion |
|--------|--------|-------|-----------|
| SAP Fuel & Procurement | Semicolon CSV (IDoc-derived) | 1 + 3 | File upload |
| Utility (Electricity) | Portal CSV export | 2 | File upload |
| Corporate Travel | Concur-style CSV | 3 | File upload |

See `sample_data/` for test files and `SOURCES.md` for research rationale.

---

## Deployment (Render)

1. Create a **Web Service** → connect your repo → set root to `backend/`
2. Build command: `pip install -r requirements.txt && python manage.py migrate && python manage.py seed`
3. Start command: `gunicorn config.wsgi:application`
4. Create a **Static Site** → root `frontend/` → build `npm run build` → publish `build/`
5. Set `REACT_APP_API_URL` env var to your backend URL

---

## Review Workflow

```
Ingest CSV → [EmissionRecord status=pending] → Analyst reviews
  → Approve → is_locked=True, status=approved → AuditLog entry
  → Reject  → status=rejected (not locked, can be re-ingested)
  → Flag    → status=flagged, is_suspicious=True → analyst notes
```

Auto-flagging: parser heuristics flag zero/negative values and outliers above category-specific thresholds.
# Breathe-ESG
