"""
Parsers for the three ingestion sources.

SAP:   Flat-file IDoc-derived CSV (semicolon-delimited, German-ish headers,
       YYYYMMDD dates, plant codes, inconsistent units).
Utility: Portal CSV export (kWh or MWh per meter per billing period).
Travel:  Concur-style CSV (trip segments: air/hotel/ground, airport codes,
         cost centre, distances sometimes missing).
"""

import csv
import io
import re
from datetime import datetime, date
from decimal import Decimal, InvalidOperation


# ---------------------------------------------------------------------------
# Emission factors (kg CO2e per unit) — simplified, sourced from IPCC AR6 /
# UK DESNZ 2023 / DEFRA 2023 / EPA 2023
# ---------------------------------------------------------------------------
EMISSION_FACTORS = {
    # Fuel combustion (Scope 1) — kg CO2e per litre
    'diesel':   Decimal('2.6391'),
    'petrol':   Decimal('2.3122'),
    'lpg':      Decimal('1.5550'),
    'cng':      Decimal('2.0420'),   # per kg → converted below
    'hfo':      Decimal('3.1790'),   # heavy fuel oil
    # Electricity (Scope 2) — kg CO2e per kWh, India grid 2023
    'electricity_india': Decimal('0.7080'),
    # Travel (Scope 3)
    'flight_short_haul_economy': Decimal('0.2551'),   # per km, passenger
    'flight_long_haul_economy':  Decimal('0.1951'),
    'hotel_night':               Decimal('31.0000'),  # per room-night, kg CO2e
    'car_rental':                Decimal('0.1710'),   # per km
    'taxi':                      Decimal('0.1490'),   # per km
    'train':                     Decimal('0.0410'),   # per km
    # Procurement (Scope 3) — spend-based, kg CO2e per USD
    'chemicals':        Decimal('0.450'),
    'machinery':        Decimal('0.320'),
    'electronics':      Decimal('0.410'),
    'office_supplies':  Decimal('0.280'),
    'default_goods':    Decimal('0.350'),
}

# Airport code → country (subset for demo)
AIRPORT_COUNTRY = {
    'DEL':'India','BOM':'India','BLR':'India','MAA':'India','CCU':'India',
    'HYD':'India','LHR':'UK','LGW':'UK','CDG':'France','FRA':'Germany',
    'JFK':'USA','EWR':'USA','LAX':'USA','ORD':'USA','SFO':'USA',
    'DXB':'UAE','SIN':'Singapore','HKG':'Hong Kong','NRT':'Japan',
    'SYD':'Australia',
}

SHORT_HAUL_KM = 3700  # flights under this distance = short haul

# Great-circle distance approximations (km) for common routes (both directions)
ROUTE_DISTANCES = {
    frozenset(['DEL','BOM']): 1148,
    frozenset(['DEL','BLR']): 1740,
    frozenset(['DEL','LHR']): 6730,
    frozenset(['DEL','DXB']): 2194,
    frozenset(['BOM','LHR']): 7191,
    frozenset(['DEL','JFK']): 11768,
    frozenset(['DEL','SIN']): 5603,
    frozenset(['LHR','JFK']): 5539,
    frozenset(['LHR','CDG']): 344,
    frozenset(['FRA','JFK']): 6197,
}


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _parse_date(raw: str) -> date:
    """Try multiple date formats; raise ValueError if none match."""
    raw = str(raw).strip()
    for fmt in ('%Y%m%d', '%d.%m.%Y', '%m/%d/%Y', '%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y'):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unrecognised date format: {raw!r}")


def _to_decimal(raw) -> Decimal:
    """Convert string/float to Decimal, handling European comma decimals."""
    s = str(raw).strip().replace(',', '.').replace(' ', '')
    return Decimal(s)


def _normalise_unit_to_litres(value: Decimal, unit: str) -> Decimal:
    """Convert fuel quantity to litres."""
    unit = unit.strip().upper()
    conversions = {
        'L': Decimal('1'), 'LITER': Decimal('1'), 'LITRE': Decimal('1'), 'LTR': Decimal('1'),
        'M3': Decimal('1000'), 'CBM': Decimal('1000'),
        'GAL': Decimal('3.78541'), 'GALLON': Decimal('3.78541'),
        'KG': Decimal('1.136'),    # diesel approx
        'TON': Decimal('1136'),
        'MT': Decimal('1136'),
    }
    factor = conversions.get(unit, Decimal('1'))
    return value * factor


def _normalise_to_kwh(value: Decimal, unit: str) -> Decimal:
    unit = unit.strip().upper()
    if unit in ('MWH',):
        return value * 1000
    if unit in ('KWH', 'KW·H'):
        return value
    return value  # assume kWh


def _get_route_distance(origin: str, dest: str) -> int:
    key = frozenset([origin.upper(), dest.upper()])
    return ROUTE_DISTANCES.get(key, 2000)  # default 2000 km if unknown


def _flight_factor(distance_km: int) -> Decimal:
    if distance_km <= SHORT_HAUL_KM:
        return EMISSION_FACTORS['flight_short_haul_economy']
    return EMISSION_FACTORS['flight_long_haul_economy']


# ---------------------------------------------------------------------------
# Suspicion checks
# ---------------------------------------------------------------------------

def _flag_suspicious(value: Decimal, category: str) -> str | None:
    thresholds = {
        'mobile_combustion':     (0, 200_000),   # litres per record
        'stationary_combustion': (0, 500_000),
        'purchased_electricity': (0, 5_000_000),  # kWh
        'business_travel_air':   (0, 100_000),    # km
        'hotel_night':           (0, 365),
    }
    lo, hi = thresholds.get(category, (0, 1e12))
    if value <= 0:
        return "Non-positive activity value"
    if value > hi:
        return f"Value {value} exceeds expected maximum {hi} for {category}"
    return None


# ---------------------------------------------------------------------------
# SAP Parser  (semicolon-delimited flat file, IDoc-style)
# ---------------------------------------------------------------------------

SAP_FUEL_COLUMN_MAP = {
    # German → normalised
    'MENGE': 'quantity', 'QUANTITY': 'quantity',
    'MEINS': 'unit',     'UNIT': 'unit', 'UOM': 'unit',
    'MATNR': 'material', 'MATERIAL': 'material',
    'WERKS': 'plant',    'PLANT': 'plant',
    'BUDAT': 'posting_date', 'POSTING_DATE': 'posting_date', 'DATE': 'posting_date',
    'BLDAT': 'document_date',
    'BELNR': 'document_no', 'DOCUMENT_NO': 'document_no',
    'KOSTL': 'cost_centre', 'COST_CENTRE': 'cost_centre',
    'MATNR_DESC': 'material_desc', 'DESCRIPTION': 'material_desc',
    'LIFNR': 'vendor', 'VENDOR': 'vendor',
    'DMBTR': 'amount_usd', 'AMOUNT': 'amount_usd',
    'WAERS': 'currency', 'CURRENCY': 'currency',
    'SCOPE': 'scope_hint', 'CATEGORY': 'category_hint',
}

MATERIAL_TO_FUEL = {
    'DIESEL': 'diesel', 'DI': 'diesel', 'HSD': 'diesel', 'HIGH SPEED DIESEL': 'diesel',
    'PETROL': 'petrol', 'MS': 'petrol', 'GASOLINE': 'petrol',
    'LPG': 'lpg', 'LIQUEFIED PETROLEUM': 'lpg',
    'CNG': 'cng',
    'HFO': 'hfo', 'FUEL OIL': 'hfo',
}

PLANT_CODES = {
    'P001': 'Mumbai Refinery', 'P002': 'Delhi Plant', 'P003': 'Chennai Facility',
    'P004': 'Pune Manufacturing', 'P005': 'Kolkata Warehouse',
    '1000': 'HQ Operations', '2000': 'North Region', '3000': 'South Region',
}

PROCUREMENT_CATEGORIES = {
    'CHEM': 'chemicals', 'MACH': 'machinery', 'ELEC': 'electronics',
    'OFFC': 'office_supplies',
}


def parse_sap_csv(file_content: str) -> list[dict]:
    """
    Parse SAP flat-file export. Returns list of normalised row dicts.
    Each dict has keys: scope, category, activity_value, activity_unit,
    period_start, period_end, facility_code, facility_name, source_record_id,
    raw_data, emission_factor, co2e_kg, is_suspicious, suspicion_reason,
    emission_factor_source.
    """
    records = []
    errors = []

    # Detect delimiter
    sample = file_content[:2000]
    delimiter = ';' if sample.count(';') > sample.count(',') else ','

    reader = csv.DictReader(io.StringIO(file_content), delimiter=delimiter)

    for i, raw_row in enumerate(reader, start=2):
        try:
            row = {SAP_FUEL_COLUMN_MAP.get(k.strip().upper(), k.strip().lower()): str(v).strip()
                   for k, v in raw_row.items() if k}

            # Quantity + unit
            qty_raw = row.get('quantity', '0')
            qty = _to_decimal(qty_raw) if qty_raw else Decimal('0')
            unit = row.get('unit', 'L').upper()

            # Date
            date_raw = row.get('posting_date') or row.get('document_date', '')
            posting_date = _parse_date(date_raw)
            period_start = posting_date.replace(day=1)
            import calendar
            last_day = calendar.monthrange(posting_date.year, posting_date.month)[1]
            period_end = posting_date.replace(day=last_day)

            # Plant / facility
            plant = row.get('plant', '')
            facility_name = PLANT_CODES.get(plant, plant)

            # Determine if fuel or procurement
            material = row.get('material', '').upper()
            material_desc = row.get('material_desc', '').upper()
            category_hint = row.get('category_hint', '').lower()
            scope_hint = row.get('scope_hint', '')

            fuel_key = None
            for k, v in MATERIAL_TO_FUEL.items():
                if k in material or k in material_desc:
                    fuel_key = v
                    break

            if fuel_key:
                # Scope 1 fuel combustion
                litres = _normalise_unit_to_litres(qty, unit)
                ef = EMISSION_FACTORS[fuel_key]
                co2e = litres * ef
                category = 'mobile_combustion' if 'VEHICLE' in material_desc or 'TRANSPORT' in material_desc else 'stationary_combustion'
                suspicion = _flag_suspicious(litres, category)
                records.append({
                    'scope': '1', 'category': category,
                    'activity_value': litres, 'activity_unit': 'litres',
                    'period_start': period_start, 'period_end': period_end,
                    'facility_code': plant, 'facility_name': facility_name,
                    'source_record_id': row.get('document_no', f'row_{i}'),
                    'raw_data': dict(raw_row),
                    'emission_factor': ef,
                    'emission_factor_source': f'IPCC AR6 / DEFRA 2023 — {fuel_key}',
                    'co2e_kg': co2e,
                    'is_suspicious': bool(suspicion),
                    'suspicion_reason': suspicion or '',
                })
            else:
                # Scope 3 procurement — spend-based
                amount_raw = row.get('amount_usd', '0')
                amount = _to_decimal(amount_raw) if amount_raw else Decimal('0')
                proc_cat = 'default_goods'
                for code, cat in PROCUREMENT_CATEGORIES.items():
                    if code in material or code in category_hint.upper():
                        proc_cat = cat
                        break
                ef = EMISSION_FACTORS[proc_cat]
                co2e = amount * ef
                suspicion = _flag_suspicious(amount, 'purchased_goods') if amount > 0 else "Zero spend value"
                records.append({
                    'scope': '3', 'category': 'purchased_goods',
                    'activity_value': amount, 'activity_unit': 'USD',
                    'period_start': period_start, 'period_end': period_end,
                    'facility_code': plant, 'facility_name': facility_name,
                    'source_record_id': row.get('document_no', f'row_{i}'),
                    'raw_data': dict(raw_row),
                    'emission_factor': ef,
                    'emission_factor_source': f'EPA EEIO 2023 — {proc_cat}',
                    'co2e_kg': co2e,
                    'is_suspicious': bool(suspicion),
                    'suspicion_reason': suspicion or '',
                })

        except Exception as e:
            errors.append({'row': i, 'error': str(e), 'raw': dict(raw_row) if 'raw_row' in dir() else {}})

    return records, errors


# ---------------------------------------------------------------------------
# Utility CSV Parser
# ---------------------------------------------------------------------------

UTILITY_COLUMN_MAP = {
    'METER_ID': 'meter_id', 'METER': 'meter_id', 'ACCOUNT': 'meter_id',
    'FACILITY': 'facility', 'SITE': 'facility', 'LOCATION': 'facility',
    'BILLING_START': 'billing_start', 'PERIOD_START': 'billing_start', 'FROM': 'billing_start',
    'BILLING_END': 'billing_end', 'PERIOD_END': 'billing_end', 'TO': 'billing_end',
    'CONSUMPTION': 'consumption', 'USAGE': 'consumption', 'KWH': 'consumption', 'UNITS': 'consumption',
    'UNIT': 'unit', 'UOM': 'unit',
    'TARIFF': 'tariff', 'RATE': 'tariff',
    'AMOUNT': 'amount', 'BILL_AMOUNT': 'amount', 'CHARGES': 'amount',
    'CURRENCY': 'currency',
    'METER_TYPE': 'meter_type',
}


def parse_utility_csv(file_content: str) -> tuple[list[dict], list[dict]]:
    records = []
    errors = []
    delimiter = ';' if file_content[:2000].count(';') > file_content[:2000].count(',') else ','
    reader = csv.DictReader(io.StringIO(file_content), delimiter=delimiter)

    for i, raw_row in enumerate(reader, start=2):
        try:
            row = {UTILITY_COLUMN_MAP.get(k.strip().upper(), k.strip().lower()): str(v).strip()
                   for k, v in raw_row.items() if k}

            consumption = _to_decimal(row.get('consumption', '0'))
            unit = row.get('unit', 'kWh')
            kwh = _normalise_to_kwh(consumption, unit)

            billing_start = _parse_date(row.get('billing_start', ''))
            billing_end   = _parse_date(row.get('billing_end', billing_start.strftime('%Y%m%d')))

            ef = EMISSION_FACTORS['electricity_india']
            co2e = kwh * ef
            suspicion = _flag_suspicious(kwh, 'purchased_electricity')

            records.append({
                'scope': '2', 'category': 'purchased_electricity',
                'activity_value': kwh, 'activity_unit': 'kWh',
                'period_start': billing_start, 'period_end': billing_end,
                'facility_code': row.get('meter_id', ''),
                'facility_name': row.get('facility', ''),
                'source_record_id': f"{row.get('meter_id','')}_{billing_start}",
                'raw_data': dict(raw_row),
                'emission_factor': ef,
                'emission_factor_source': 'CEA India Grid Emission Factor 2023 (0.708 kgCO2e/kWh)',
                'co2e_kg': co2e,
                'is_suspicious': bool(suspicion),
                'suspicion_reason': suspicion or '',
            })
        except Exception as e:
            errors.append({'row': i, 'error': str(e), 'raw': dict(raw_row)})

    return records, errors


# ---------------------------------------------------------------------------
# Corporate Travel CSV Parser (Concur-style)
# ---------------------------------------------------------------------------

TRAVEL_COLUMN_MAP = {
    'TRIP_ID': 'trip_id', 'BOOKING_REF': 'trip_id', 'RECORD_ID': 'trip_id',
    'EMPLOYEE': 'employee', 'TRAVELER': 'employee',
    'SEGMENT_TYPE': 'segment_type', 'TYPE': 'segment_type', 'CATEGORY': 'segment_type',
    'ORIGIN': 'origin', 'FROM': 'origin', 'DEPARTURE': 'origin',
    'DESTINATION': 'destination', 'TO': 'destination', 'ARRIVAL': 'destination',
    'TRAVEL_DATE': 'travel_date', 'DEPARTURE_DATE': 'travel_date', 'DATE': 'travel_date',
    'RETURN_DATE': 'return_date', 'CHECK_OUT': 'return_date',
    'DISTANCE_KM': 'distance_km', 'DISTANCE': 'distance_km', 'KM': 'distance_km',
    'NIGHTS': 'nights', 'HOTEL_NIGHTS': 'nights',
    'CABIN_CLASS': 'cabin_class', 'CLASS': 'cabin_class',
    'COST_CENTRE': 'cost_centre',
    'AMOUNT': 'amount', 'COST': 'amount',
    'CURRENCY': 'currency',
    'VENDOR': 'vendor', 'AIRLINE': 'vendor', 'HOTEL': 'vendor',
}

SEGMENT_MAP = {
    'AIR': 'business_travel_air', 'FLIGHT': 'business_travel_air', 'FLY': 'business_travel_air',
    'HOTEL': 'business_travel_hotel', 'ACCOMMODATION': 'business_travel_hotel',
    'CAR': 'business_travel_ground', 'TAXI': 'business_travel_ground',
    'TRAIN': 'business_travel_ground', 'RAIL': 'business_travel_ground',
    'GROUND': 'business_travel_ground', 'BUS': 'business_travel_ground',
}


def parse_travel_csv(file_content: str) -> tuple[list[dict], list[dict]]:
    records = []
    errors = []
    delimiter = ';' if file_content[:2000].count(';') > file_content[:2000].count(',') else ','
    reader = csv.DictReader(io.StringIO(file_content), delimiter=delimiter)

    for i, raw_row in enumerate(reader, start=2):
        try:
            row = {TRAVEL_COLUMN_MAP.get(k.strip().upper(), k.strip().lower()): str(v).strip()
                   for k, v in raw_row.items() if k}

            seg_raw = row.get('segment_type', 'AIR').upper()
            category = SEGMENT_MAP.get(seg_raw, 'business_travel_air')

            travel_date = _parse_date(row.get('travel_date', ''))
            period_start = travel_date

            if category == 'business_travel_air':
                origin = row.get('origin', '').upper().strip()[:3]
                dest   = row.get('destination', '').upper().strip()[:3]
                dist_raw = row.get('distance_km', '')
                if dist_raw and dist_raw not in ('', '0', 'N/A'):
                    distance = int(_to_decimal(dist_raw))
                else:
                    distance = _get_route_distance(origin, dest)

                ef = _flight_factor(distance)
                co2e = Decimal(distance) * ef
                suspicion = _flag_suspicious(Decimal(distance), 'business_travel_air')
                period_end = travel_date

                records.append({
                    'scope': '3', 'category': category,
                    'activity_value': Decimal(distance), 'activity_unit': 'km',
                    'period_start': period_start, 'period_end': period_end,
                    'facility_code': row.get('cost_centre', ''),
                    'facility_name': f"{origin}→{dest}",
                    'source_record_id': row.get('trip_id', f'row_{i}'),
                    'raw_data': dict(raw_row),
                    'emission_factor': ef,
                    'emission_factor_source': f'DEFRA 2023 — {"short" if distance <= SHORT_HAUL_KM else "long"} haul economy',
                    'co2e_kg': co2e,
                    'is_suspicious': bool(suspicion),
                    'suspicion_reason': suspicion or '',
                })

            elif category == 'business_travel_hotel':
                nights = _to_decimal(row.get('nights', '1') or '1')
                return_date_raw = row.get('return_date', '')
                if return_date_raw:
                    period_end = _parse_date(return_date_raw)
                else:
                    import datetime as dt
                    period_end = travel_date + dt.timedelta(days=int(nights))

                ef = EMISSION_FACTORS['hotel_night']
                co2e = nights * ef
                suspicion = _flag_suspicious(nights, 'hotel_night')
                records.append({
                    'scope': '3', 'category': category,
                    'activity_value': nights, 'activity_unit': 'nights',
                    'period_start': period_start, 'period_end': period_end,
                    'facility_code': row.get('cost_centre', ''),
                    'facility_name': row.get('destination', row.get('vendor', '')),
                    'source_record_id': row.get('trip_id', f'row_{i}'),
                    'raw_data': dict(raw_row),
                    'emission_factor': ef,
                    'emission_factor_source': 'DEFRA 2023 — hotel room-night',
                    'co2e_kg': co2e,
                    'is_suspicious': bool(suspicion),
                    'suspicion_reason': suspicion or '',
                })

            else:  # ground transport
                dist_raw = row.get('distance_km', '50')
                distance = _to_decimal(dist_raw) if dist_raw and dist_raw not in ('', 'N/A') else Decimal('50')
                vendor = row.get('vendor', '').upper()
                if 'TRAIN' in vendor or 'RAIL' in vendor or seg_raw in ('TRAIN', 'RAIL'):
                    ef = EMISSION_FACTORS['train']
                    ef_source = 'DEFRA 2023 — train'
                else:
                    ef = EMISSION_FACTORS['taxi']
                    ef_source = 'DEFRA 2023 — taxi/car'
                co2e = distance * ef
                suspicion = _flag_suspicious(distance, 'business_travel_air')
                import datetime as dt
                records.append({
                    'scope': '3', 'category': category,
                    'activity_value': distance, 'activity_unit': 'km',
                    'period_start': period_start, 'period_end': travel_date,
                    'facility_code': row.get('cost_centre', ''),
                    'facility_name': f"{row.get('origin','')}→{row.get('destination','')}",
                    'source_record_id': row.get('trip_id', f'row_{i}'),
                    'raw_data': dict(raw_row),
                    'emission_factor': ef,
                    'emission_factor_source': ef_source,
                    'co2e_kg': co2e,
                    'is_suspicious': bool(suspicion),
                    'suspicion_reason': suspicion or '',
                })

        except Exception as e:
            errors.append({'row': i, 'error': str(e), 'raw': dict(raw_row)})

    return records, errors
