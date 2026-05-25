# Decisions — Breathe ESG Prototype

## SAP: IDoc flat-file over OData/BAPI

**Chosen:** Semicolon-delimited flat file, IDoc-style structure.

**Why:** SAP has four common export mechanisms — IDoc (EDI), flat file (SE16/MB51 export), OData (SAP Gateway), and BAPI/RFC. For a sustainability team, the most realistic export is what a finance or procurement team sends: a CSV pulled from transaction MB51 (material document list) or ME2M (purchase order report). These are semicolon-delimited, often have German column headers in German SAP instances (MENGE=quantity, MEINS=unit, WERKS=plant, BUDAT=posting date), and dates in YYYYMMDD. An OData integration would be cleaner but requires SAP Basis configuration and API credentials — something a new client would not hand over immediately.

**What I ignored:**
- IDoc XML structure (relevant for EDI pipelines, not analyst exports)
- BAPI RFC calls (requires SAP connectivity we can't assume)
- SAP S/4HANA SOAP APIs
- Multi-currency ledger consolidation
- Cost centre hierarchy lookups (plant code → cost centre → BU)

**What I'd ask the PM:**
> Is the client on SAP ECC or S/4HANA? Do they have a regular batch export scheduled, or will we be receiving ad-hoc files? Is there a SAP Basis contact who can set up an RFC user for us in Phase 2?

---

## Utility: Portal CSV export over PDF or API

**Chosen:** CSV export from utility web portal.

**Why:** Three options exist:
1. PDF bills — requires OCR, fragile to layout changes, error-prone
2. Portal CSV export — most facilities teams do this monthly; structured, consistent
3. Utility API (e.g. Green Button Data) — ideal but not universally available in India

PDF parsing was rejected because it requires computer vision or brittle regex against utility-specific formats (MSEDCL, BESCOM, TNEB all differ). API availability in India is poor — most state DISCOMs don't expose APIs. Portal CSV is what a facilities manager actually downloads and emails across. It has meter ID, billing period, consumption in kWh or MWh, and tariff code.

**What I ignored:**
- Multi-building sub-metering (one meter ID per row is assumed)
- Time-of-use tariff segmentation (peak/off-peak kWh not separated)
- T&D loss factors for market-based Scope 2
- RECs (Renewable Energy Certificates) and their impact on Scope 2

**What I'd ask the PM:**
> Does the client report market-based or location-based Scope 2? If market-based, we need REC purchase data and supplier emission factors, not just grid averages.

---

## Travel: Concur-style CSV over API pull

**Chosen:** Concur-style CSV export (same structure works for Navan/TripActions/Egencia).

**Why:** Corporate travel platforms expose booking data in two ways: live API (OAuth, webhooks) or scheduled CSV exports. For an onboarding client, a CSV export is the safest starting point — no OAuth flow to configure, no rate limits to negotiate. The Concur standard export contains: trip ID, traveller, segment type (air/hotel/car), origin/destination (IATA codes for air), travel dates, cabin class, and cost centre. Navan's export format is structurally identical.

**Distance inference:** When distance is absent (common for hotel and ground segments), I infer distance from IATA airport code pairs using a lookup table of great-circle distances. This is a documented approximation — actual flight distance is 5–8% longer than great-circle.

**What I ignored:**
- Train (inter-city) emission factors by country
- Cruise/ferry segments
- Personal vehicle reimbursement (mileage claims)
- Layover emissions (multiple legs in one ticket)
- Offsetting programs (Atmosfair, Gold Standard)

**What I'd ask the PM:**
> Does the client want us to pull live from Concur's API, or is a monthly CSV export acceptable? If live, I need Concur OAuth app credentials and we need to discuss data refresh frequency.

---

## Suspicion flagging heuristics

Records are auto-flagged when:
- Activity value is ≤ 0 (zero/negative consumption is always an error)
- Activity value exceeds configurable thresholds per category (e.g. >200,000 litres of diesel in a single record — likely a unit error, e.g. m³ entered instead of litres)

The thresholds are intentionally conservative. False positives are better than false negatives when auditors are downstream.

---

## Lock on approval, not on rejection

Approved records are locked (`is_locked=True`) and cannot be edited. Rejected records remain unlocked. The rationale: an approved record has been signed off for the audit trail. If it needs correction, the source data should be re-ingested as a new batch and the original rejected. Rejection means "do not include" — it doesn't need to be immutable since it won't appear in audit exports.
