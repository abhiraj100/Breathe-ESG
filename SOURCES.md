# Sources — Research and Sample Data Rationale

## 1. SAP Fuel & Procurement

### What I researched
SAP stores material movements in the Materials Management (MM) module. The relevant transactions are:
- **MB51** — Material Document List: exports all goods receipts/issues with material code, plant, quantity, unit, posting date, document number
- **ME2M** — Purchase Orders by Material: shows procurement by vendor, material, cost centre
- **FAGLL03** — G/L Account Line Items: for spend-based procurement in FI

IDoc (Intermediate Document) is SAP's EDI format — XML or flat-file segments with EDIDC control records and EDID4 data records. It's used for system-to-system integration. For a sustainability analyst, the realistic format is a flat file exported via SE16 (table browser) or a custom report — semicolon-delimited, UTF-8 or Latin-1 encoded.

German column names appear in SAP instances installed in German (common in European multinationals): MENGE (Menge = quantity), MEINS (Mengeneinheit = unit of measure), WERKS (Werk = plant), BUDAT (Buchungsdatum = posting date), BELNR (Belegnummer = document number), DMBTR (Betrag in Hauswährung = amount in local currency).

### What my sample data looks like
15 rows covering Q1 2024. Mix of:
- Fuel rows (HSD = High Speed Diesel, Petrol/MS, LPG) with quantity in litres, plant codes P001–P005
- Procurement rows (CHEM, MACH, ELEC, OFFC categories) with INR amounts, zero quantity (spend-based)
- Dates in YYYYMMDD format (SAP standard)
- Semicolon delimiter
- Plant codes P001–P005 resolved via lookup table to named facilities

### What would break in real deployment
1. **Units**: SAP stores whatever unit the PO was created in. A plant might record diesel in m³, another in litres. The parser handles L, M3, GAL, KG, TON — but MT (metric ton) vs t (tonne) ambiguity could cause silent errors.
2. **Material codes**: The demo uses simplified codes (HSD001, MS002). Real SAP material codes are 8-18 character alphanumeric strings with no inherent semantics — you need a material master extract to classify them as diesel vs chemicals.
3. **Multi-currency**: SAP stores amounts in local currency. A global company has INR, USD, EUR, GBP records. Currency conversion requires FX rates at the posting date.
4. **Fiscal year variants**: SAP fiscal years don't always align with calendar years. An April–March fiscal year means Q1 in SAP ≠ Q1 January–March.

---

## 2. Utility (Electricity)

### What I researched
Indian electricity utilities (DISCOMs) provide bills in three ways:
1. **PDF bills** — MSEDCL, BESCOM, TNEB, etc. all have PDF bills with consumption, tariff slab, billing period. Layout varies per DISCOM.
2. **Portal CSV export** — Most enterprise customers with HT (High Tension) connections can download consumption data from the DISCOM portal as CSV. Common fields: account number, meter number, billing period, units consumed (kWh), demand (kVA), charges.
3. **Smart meter API** — Limited rollout. Some DISCOMs expose APIs under the Smart Meter National Programme but penetration is still low.

Tariff categories relevant to industrial/commercial clients:
- **LT (Low Tension)** — <11 kV, offices, small commercial
- **HT (High Tension)** — 11 kV+, industrial, large commercial
- **HT Category I/II** — varies by DISCOM

### What my sample data looks like
15 rows across 5 meters, Jan–Mar 2024:
- Meters: Mumbai HQ and Factory (HT-Industrial), Delhi Office, Chennai Plant, Pune R&D, Kolkata Warehouse
- Monthly billing periods (billing period ≠ calendar month in some rows — intentional)
- Consumption in kWh (realistic: 41,000–368,000 kWh/month range for industrial use)
- INR amounts based on approximate HT tariff rates (~₹8.40/kWh blended)

Emission factor used: **0.708 kgCO₂e/kWh** — India national grid emission factor, CEA (Central Electricity Authority) CO₂ Baseline Database for the Indian Power Sector, Version 18 (FY 2022-23), published 2023.

### What would break in real deployment
1. **State-specific grid factors**: CEA publishes state-wise emission factors. Tamil Nadu grid (more renewables) has a lower factor than coal-heavy states like Jharkhand. Using a national average understates emissions in coal-heavy states and overstates in renewable-heavy ones.
2. **Billing period vs calendar period misalignment**: If a billing cycle runs 15th–14th, a January bill covers half of December and half of January. Production needs temporal interpolation.
3. **Demand charges vs consumption**: Indian HT bills have both energy charges (kWh) and demand charges (kVA). We only track kWh; demand is irrelevant for emissions but needs to be stripped from cost calculations.
4. **Meter type**: Some meters record import + export (solar prosumers). Net consumption needs to subtract export.

---

## 3. Corporate Travel (Flights, Hotels, Ground Transport)

### What I researched
Concur (SAP Concur) is the dominant corporate travel platform. Its standard expense/travel export includes:

**Trip Report fields (air):** Trip ID, traveller name, booking date, travel date, origin airport (IATA), destination airport (IATA), carrier, cabin class (Economy/Business/First), ticket cost, cost centre.

**Navan (formerly TripActions)** has an identical data model with slightly different column names. Both platforms offer:
1. **API**: OAuth 2.0, scopes for expense, travel, and analytics. Rate-limited at ~1000 calls/hour.
2. **Scheduled CSV export**: Nightly or weekly export to SFTP or email. Easiest for onboarding.

**Emission factor methodology:**
- DEFRA 2023 (UK Department for Energy Security and Net Zero) provides per-passenger-km emission factors by cabin class and haul type
- Short-haul (<3,700 km): 0.2551 kgCO₂e/pkm economy; 0.5102 Business (1.5× radiative forcing multiplier applies but excluded here — noted for production)
- Long-haul (≥3,700 km): 0.1951 kgCO₂e/pkm economy

**Distance inference:** When distance is absent, great-circle distance between IATA airport codes is used. I maintain a lookup table of ~20 common routes. Production would use a IATA route distance API (e.g. OAG, Cirium) or the Haversine formula with airport lat/lon coordinates.

### What my sample data looks like
17 rows across Q1 2024:
- 6 employees, including a frequent-flyer exec (Ananya Sharma: DEL-LHR round trip twice, DEL-JFK Business class)
- Mix of long-haul (DEL-LHR, DEL-JFK, BOM-SIN) and short-haul (BOM-DEL, BLR-CHN)
- Hotel stays with nights
- Ground transport (taxi, train) with estimated distances
- Cost centres: CC-EXEC, CC-SALES, CC-TECH, CC-OPS
- INR amounts (realistic for India-based corporate)

### What would break in real deployment
1. **Radiative forcing multiplier**: Aviation has non-CO₂ warming effects (contrails, NOx) at altitude. DEFRA includes a radiative forcing index (~1.9× for long-haul). I've excluded it as it's contested and not required by all frameworks (CDP vs GHG Protocol differ). Production needs a toggle.
2. **Missing distances for non-catalogued routes**: My lookup table covers ~20 routes. A global client would have routes not in the table. Production needs an airport coordinates dataset and Haversine computation.
3. **Hotel emission factors by region**: I use a single global average (31 kgCO₂e/room-night, DEFRA 2023). A London 5-star hotel has a very different carbon intensity than a Mumbai business hotel. Production needs hotel-specific or at minimum country-specific factors.
4. **Ground transport**: Taxi and car rental factors vary enormously by vehicle type (EV vs petrol, size). Without vehicle data from the platform, a fleet average is all we can do.
