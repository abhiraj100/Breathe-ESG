"""
Management command to seed the database with demo data.
Usage: python manage.py seed
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from api.models import Tenant, TenantUser, IngestionBatch, EmissionRecord, AuditLog
from api.parsers import parse_sap_csv, parse_utility_csv, parse_travel_csv
from decimal import Decimal
import datetime


SAP_CSV = """BELNR;BUDAT;WERKS;MATNR;MATNR_DESC;MENGE;MEINS;DMBTR;WAERS;KOSTL;CATEGORY
5000000001;20240115;P001;HSD001;HIGH SPEED DIESEL;12500;L;625000;INR;CC-OPS;FUEL
5000000002;20240118;P002;MS002;PETROL;3200;L;217600;INR;CC-FLEET;FUEL
5000000003;20240122;P001;LPG003;LPG;850;L;42500;INR;CC-KITCHEN;FUEL
5000000004;20240205;P003;HSD001;HIGH SPEED DIESEL;8900;L;445000;INR;CC-OPS;FUEL
5000000005;20240210;P001;CHEM001;INDUSTRIAL CHEMICALS;0;L;285000;INR;CC-PROC;CHEM
5000000006;20240215;P002;MACH002;HEAVY MACHINERY PARTS;0;L;1850000;INR;CC-PROC;MACH
5000000007;20240220;P001;HSD001;HIGH SPEED DIESEL;15200;L;760000;INR;CC-OPS;FUEL
5000000008;20240228;P004;MS002;PETROL;2100;L;142800;INR;CC-FLEET;FUEL
5000000009;20240310;P003;ELEC003;ELECTRONIC COMPONENTS;0;L;425000;INR;CC-PROC;ELEC
5000000010;20240315;P001;HSD001;HIGH SPEED DIESEL;9800;L;490000;INR;CC-OPS;FUEL
5000000011;20240320;P005;LPG003;LPG;1200;L;60000;INR;CC-KITCHEN;FUEL
5000000012;20240401;P002;HSD001;HIGH SPEED DIESEL;6700;L;335000;INR;CC-OPS;FUEL
5000000013;20240415;P001;OFFC004;OFFICE SUPPLIES;0;L;95000;INR;CC-ADMIN;OFFC
5000000014;20240420;P003;HSD001;HIGH SPEED DIESEL;11300;L;565000;INR;CC-OPS;FUEL
5000000015;20240501;P004;MS002;PETROL;4500;L;306000;INR;CC-FLEET;FUEL
"""

UTILITY_CSV = """METER_ID,FACILITY,BILLING_START,BILLING_END,CONSUMPTION,UNIT,TARIFF,AMOUNT,CURRENCY
MTR-MUM-001,Mumbai HQ,20240101,20240131,185420,kWh,HT-Industrial,1558528,INR
MTR-MUM-002,Mumbai Factory,20240101,20240131,342800,kWh,HT-Industrial,2879520,INR
MTR-DEL-001,Delhi Office,20240101,20240131,48200,kWh,LT-Commercial,404880,INR
MTR-CHN-001,Chennai Plant,20240101,20240131,275600,kWh,HT-Industrial,2314840,INR
MTR-MUM-001,Mumbai HQ,20240201,20240229,172300,kWh,HT-Industrial,1447320,INR
MTR-MUM-002,Mumbai Factory,20240201,20240229,318500,kWh,HT-Industrial,2675400,INR
MTR-DEL-001,Delhi Office,20240201,20240229,52100,kWh,LT-Commercial,437640,INR
MTR-CHN-001,Chennai Plant,20240201,20240229,289400,kWh,HT-Industrial,2430760,INR
MTR-PUN-001,Pune R&D Centre,20240101,20240131,95300,kWh,LT-Commercial,800520,INR
MTR-PUN-001,Pune R&D Centre,20240201,20240229,88700,kWh,LT-Commercial,745080,INR
MTR-KOL-001,Kolkata Warehouse,20240101,20240131,41200,kWh,LT-Commercial,346080,INR
MTR-KOL-001,Kolkata Warehouse,20240201,20240229,38900,kWh,LT-Commercial,326760,INR
MTR-MUM-001,Mumbai HQ,20240301,20240331,195800,kWh,HT-Industrial,1644720,INR
MTR-MUM-002,Mumbai Factory,20240301,20240331,368200,kWh,HT-Industrial,3092880,INR
MTR-DEL-001,Delhi Office,20240301,20240331,55400,kWh,LT-Commercial,465360,INR
"""

TRAVEL_CSV = """TRIP_ID,EMPLOYEE,SEGMENT_TYPE,ORIGIN,DESTINATION,TRAVEL_DATE,RETURN_DATE,DISTANCE_KM,NIGHTS,CABIN_CLASS,COST_CENTRE,AMOUNT,CURRENCY,VENDOR
TRP-2024-001,Ananya Sharma,AIR,DEL,LHR,20240115,,6730,,Economy,CC-EXEC,85000,INR,IndiGo
TRP-2024-001,Ananya Sharma,HOTEL,,London,20240115,20240118,,3,Business,CC-EXEC,45000,INR,Marriott
TRP-2024-001,Ananya Sharma,AIR,LHR,DEL,20240118,,,Economy,CC-EXEC,85000,INR,IndiGo
TRP-2024-002,Rahul Mehta,AIR,BOM,DEL,20240120,,1148,,Economy,CC-SALES,12000,INR,Air India
TRP-2024-002,Rahul Mehta,TAXI,DEL,,20240120,,,65,,CC-SALES,1200,INR,Uber
TRP-2024-003,Priya Iyer,TRAIN,BLR,CHN,20240122,,362,,Business,CC-TECH,2500,INR,Southern Railways
TRP-2024-004,Vikram Singh,AIR,DEL,DXB,20240205,,2194,,Economy,CC-OPS,32000,INR,Emirates
TRP-2024-004,Vikram Singh,HOTEL,,Dubai,20240205,20240208,,3,,CC-OPS,38000,INR,Hilton
TRP-2024-005,Ananya Sharma,AIR,LHR,JFK,20240210,,5539,,Business,CC-EXEC,180000,INR,British Airways
TRP-2024-005,Ananya Sharma,HOTEL,,New York,20240210,20240214,,4,,CC-EXEC,92000,INR,Hyatt
TRP-2024-006,Kiran Patel,AIR,BOM,SIN,20240215,,5603,,Economy,CC-TECH,58000,INR,Singapore Airlines
TRP-2024-007,Deepa Nair,TAXI,MUM,,20240218,,,120,,CC-SALES,2200,INR,OlaCabs
TRP-2024-008,Arun Kumar,AIR,DEL,BOM,20240220,,1148,,Economy,CC-SALES,9500,INR,IndiGo
TRP-2024-008,Arun Kumar,HOTEL,,Mumbai,20240220,20240222,,2,,CC-SALES,18000,INR,Taj Hotels
TRP-2024-009,Sneha Reddy,TRAIN,HYD,BLR,20240225,,570,,Economy,CC-TECH,1800,INR,South Central Railway
TRP-2024-010,Ananya Sharma,AIR,DEL,LHR,20240301,,6730,,Business,CC-EXEC,145000,INR,Air India
TRP-2024-010,Ananya Sharma,HOTEL,,London,20240301,20240305,,4,,CC-EXEC,68000,INR,Marriott
"""


class Command(BaseCommand):
    help = 'Seed database with demo tenant, users, and emission records'

    def handle(self, *args, **options):
        self.stdout.write('Seeding database...')

        # Tenant
        tenant, _ = Tenant.objects.get_or_create(
            slug='acme-industries',
            defaults={'name': 'Acme Industries Ltd.'}
        )

        # Users
        admin_user, created = User.objects.get_or_create(username='admin')
        if created:
            admin_user.set_password('admin123')
            admin_user.first_name = 'Admin'
            admin_user.last_name = 'User'
            admin_user.is_staff = True
            admin_user.save()

        analyst_user, created = User.objects.get_or_create(username='analyst')
        if created:
            analyst_user.set_password('analyst123')
            analyst_user.first_name = 'Priya'
            analyst_user.last_name = 'Analyst'
            analyst_user.save()

        TenantUser.objects.get_or_create(user=admin_user, defaults={'tenant': tenant, 'role': 'admin'})
        TenantUser.objects.get_or_create(user=analyst_user, defaults={'tenant': tenant, 'role': 'analyst'})

        if EmissionRecord.objects.filter(tenant=tenant).count() > 0:
            self.stdout.write('Records already exist, skipping ingestion.')
        else:
            # SAP
            batch_sap = IngestionBatch.objects.create(
                tenant=tenant, source_type='sap', file_name='SAP_FY2024_Q1.csv',
                ingested_by=admin_user, status='processing'
            )
            parsed, errors = parse_sap_csv(SAP_CSV)
            self._save(parsed, errors, batch_sap, tenant, 'sap', admin_user)

            # Utility
            batch_util = IngestionBatch.objects.create(
                tenant=tenant, source_type='utility', file_name='utility_Q1_2024.csv',
                ingested_by=admin_user, status='processing'
            )
            parsed, errors = parse_utility_csv(UTILITY_CSV)
            self._save(parsed, errors, batch_util, tenant, 'utility_csv', admin_user)

            # Travel
            batch_travel = IngestionBatch.objects.create(
                tenant=tenant, source_type='travel', file_name='concur_Q1_2024.csv',
                ingested_by=admin_user, status='processing'
            )
            parsed, errors = parse_travel_csv(TRAVEL_CSV)
            self._save(parsed, errors, batch_travel, tenant, 'concur_csv', admin_user)

        self.stdout.write(self.style.SUCCESS(
            f'Done! Login: admin/admin123 or analyst/analyst123'
        ))

    def _save(self, parsed, errors, batch, tenant, source_system, user):
        from api.models import ParseError
        for r in parsed:
            rec = EmissionRecord(
                tenant=tenant, batch=batch,
                scope=r['scope'], category=r['category'],
                activity_value=r['activity_value'], activity_unit=r['activity_unit'],
                emission_factor=r.get('emission_factor'),
                emission_factor_source=r.get('emission_factor_source', ''),
                co2e_kg=r.get('co2e_kg'),
                period_start=r['period_start'], period_end=r['period_end'],
                source_system=source_system,
                source_record_id=r.get('source_record_id', ''),
                raw_data=r.get('raw_data', {}),
                facility_code=r.get('facility_code', ''),
                facility_name=r.get('facility_name', ''),
                is_suspicious=r.get('is_suspicious', False),
                suspicion_reason=r.get('suspicion_reason', ''),
            )
            rec.save()
            AuditLog.objects.create(record=rec, user=user, action='created',
                                    detail={'source': source_system})
        for e in errors:
            ParseError.objects.create(
                batch=batch, row_number=e.get('row'),
                raw_row=e.get('raw', {}), error_message=e.get('error', '')
            )
        batch.total_rows = len(parsed) + len(errors)
        batch.passed_rows = len(parsed)
        batch.failed_rows = len(errors)
        batch.status = 'completed'
        batch.save()
        self.stdout.write(f'  {source_system}: {len(parsed)} records, {len(errors)} errors')
