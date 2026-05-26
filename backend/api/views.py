from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import Sum, Q
from django.views.decorators.csrf import csrf_exempt
from rest_framework import viewsets
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response

from .models import Tenant, TenantUser, IngestionBatch, EmissionRecord, AuditLog, ParseError
from .serializers import (IngestionBatchSerializer, EmissionRecordSerializer,
                          AuditLogSerializer, ParseErrorSerializer)
from .parsers import parse_sap_csv, parse_utility_csv, parse_travel_csv


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    user = authenticate(request, username=request.data.get('username'), password=request.data.get('password'))
    if user:
        login(request, user)
        try:
            tu = user.tenant_user
            tenant = {'id': str(tu.tenant.id), 'name': tu.tenant.name, 'slug': tu.tenant.slug}
            role = tu.role
        except TenantUser.DoesNotExist:
            tenant = None
            role = 'admin'
        return Response({'id': user.id, 'username': user.username,
                         'full_name': user.get_full_name(), 'email': user.email,
                         'tenant': tenant, 'role': role})
    return Response({'error': 'Invalid credentials'}, status=400)


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def logout_view(request):
    logout(request)
    return Response({'ok': True})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me_view(request):
    user = request.user
    try:
        tu = user.tenant_user
        tenant = {'id': str(tu.tenant.id), 'name': tu.tenant.name, 'slug': tu.tenant.slug}
        role = tu.role
    except TenantUser.DoesNotExist:
        tenant = None
        role = 'admin'
    return Response({'id': user.id, 'username': user.username,
                     'full_name': user.get_full_name(), 'email': user.email,
                     'tenant': tenant, 'role': role})


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_stats(request):
    try:
        tenant = request.user.tenant_user.tenant
    except TenantUser.DoesNotExist:
        tenant = Tenant.objects.first()

    qs = EmissionRecord.objects.filter(tenant=tenant)
    total_co2e = qs.filter(status='approved').aggregate(t=Sum('co2e_kg'))['t'] or 0

    scope_breakdown = {}
    for s in ['1', '2', '3']:
        val = qs.filter(scope=s, status='approved').aggregate(t=Sum('co2e_kg'))['t'] or 0
        scope_breakdown[f'scope{s}'] = float(val)

    category_breakdown = []
    for cat, label in EmissionRecord.CATEGORY_CHOICES:
        val = qs.filter(category=cat, status='approved').aggregate(t=Sum('co2e_kg'))['t'] or 0
        if val > 0:
            category_breakdown.append({'category': cat, 'label': label, 'co2e_kg': float(val)})

    recent_batches = IngestionBatch.objects.filter(tenant=tenant).order_by('-ingested_at')[:5]

    return Response({
        'total_co2e_kg': float(total_co2e),
        'pending':  qs.filter(status='pending').count(),
        'flagged':  qs.filter(is_suspicious=True).count(),
        'approved': qs.filter(status='approved').count(),
        'rejected': qs.filter(status='rejected').count(),
        'scope_breakdown': scope_breakdown,
        'category_breakdown': category_breakdown,
        'recent_batches': IngestionBatchSerializer(recent_batches, many=True).data,
    })


# ---------------------------------------------------------------------------
# Ingestion helpers
# ---------------------------------------------------------------------------

def _get_tenant(user):
    try:
        return user.tenant_user.tenant
    except TenantUser.DoesNotExist:
        return Tenant.objects.first()


def _save_records(parsed, errors, batch, tenant, source_system):
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
        AuditLog.objects.create(record=rec, user=None, action='created',
                                detail={'source': source_system, 'batch': str(batch.id)})
    for e in errors:
        ParseError.objects.create(batch=batch, row_number=e.get('row'),
                                  raw_row=e.get('raw', {}), error_message=e.get('error', ''))
    batch.total_rows  = len(parsed) + len(errors)
    batch.passed_rows = len(parsed)
    batch.failed_rows = len(errors)
    batch.status = 'completed'
    batch.save()


# ---------------------------------------------------------------------------
# Ingest endpoints
# ---------------------------------------------------------------------------

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ingest_sap(request):
    file = request.FILES.get('file')
    if not file:
        return Response({'error': 'No file'}, status=400)
    tenant = _get_tenant(request.user)
    batch = IngestionBatch.objects.create(tenant=tenant, source_type='sap',
                file_name=file.name, ingested_by=request.user, status='processing')
    try:
        parsed, errors = parse_sap_csv(file.read().decode('utf-8', errors='replace'))
        _save_records(parsed, errors, batch, tenant, 'sap')
        return Response(IngestionBatchSerializer(batch).data, status=201)
    except Exception as e:
        batch.status = 'failed'; batch.notes = str(e); batch.save()
        return Response({'error': str(e)}, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ingest_utility(request):
    file = request.FILES.get('file')
    if not file:
        return Response({'error': 'No file'}, status=400)
    tenant = _get_tenant(request.user)
    batch = IngestionBatch.objects.create(tenant=tenant, source_type='utility',
                file_name=file.name, ingested_by=request.user, status='processing')
    try:
        parsed, errors = parse_utility_csv(file.read().decode('utf-8', errors='replace'))
        _save_records(parsed, errors, batch, tenant, 'utility_csv')
        return Response(IngestionBatchSerializer(batch).data, status=201)
    except Exception as e:
        batch.status = 'failed'; batch.notes = str(e); batch.save()
        return Response({'error': str(e)}, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ingest_travel(request):
    file = request.FILES.get('file')
    if not file:
        return Response({'error': 'No file'}, status=400)
    tenant = _get_tenant(request.user)
    batch = IngestionBatch.objects.create(tenant=tenant, source_type='travel',
                file_name=file.name, ingested_by=request.user, status='processing')
    try:
        parsed, errors = parse_travel_csv(file.read().decode('utf-8', errors='replace'))
        _save_records(parsed, errors, batch, tenant, 'concur_csv')
        return Response(IngestionBatchSerializer(batch).data, status=201)
    except Exception as e:
        batch.status = 'failed'; batch.notes = str(e); batch.save()
        return Response({'error': str(e)}, status=500)


# ---------------------------------------------------------------------------
# ViewSets
# ---------------------------------------------------------------------------

class EmissionRecordViewSet(viewsets.ModelViewSet):
    serializer_class = EmissionRecordSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        tenant = _get_tenant(self.request.user)
        qs = EmissionRecord.objects.filter(tenant=tenant).select_related('batch', 'reviewed_by')
        p = self.request.query_params
        if p.get('scope'):      qs = qs.filter(scope=p['scope'])
        if p.get('status'):     qs = qs.filter(status=p['status'])
        if p.get('suspicious') == 'true': qs = qs.filter(is_suspicious=True)
        if p.get('source'):     qs = qs.filter(source_system=p['source'])
        if p.get('batch'):      qs = qs.filter(batch_id=p['batch'])
        if p.get('search'):
            qs = qs.filter(Q(facility_name__icontains=p['search']) | Q(category__icontains=p['search']))
        return qs

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        rec = self.get_object()
        if rec.is_locked:
            return Response({'error': 'Locked'}, status=400)
        rec.status = 'approved'; rec.reviewed_by = request.user
        rec.reviewed_at = timezone.now(); rec.is_locked = True
        rec.review_notes = request.data.get('notes', ''); rec.save()
        AuditLog.objects.create(record=rec, user=request.user, action='approved',
                                detail={'notes': rec.review_notes})
        return Response(EmissionRecordSerializer(rec).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        rec = self.get_object()
        if rec.is_locked:
            return Response({'error': 'Locked'}, status=400)
        rec.status = 'rejected'; rec.reviewed_by = request.user
        rec.reviewed_at = timezone.now()
        rec.review_notes = request.data.get('notes', ''); rec.save()
        AuditLog.objects.create(record=rec, user=request.user, action='rejected',
                                detail={'notes': rec.review_notes})
        return Response(EmissionRecordSerializer(rec).data)

    @action(detail=True, methods=['post'])
    def flag(self, request, pk=None):
        rec = self.get_object()
        rec.is_suspicious = True
        rec.suspicion_reason = request.data.get('reason', 'Manually flagged')
        rec.status = 'flagged'; rec.save()
        AuditLog.objects.create(record=rec, user=request.user, action='flagged',
                                detail={'reason': rec.suspicion_reason})
        return Response(EmissionRecordSerializer(rec).data)

    @action(detail=True, methods=['get'])
    def audit(self, request, pk=None):
        logs = AuditLog.objects.filter(record=self.get_object())
        return Response(AuditLogSerializer(logs, many=True).data)


class IngestionBatchViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = IngestionBatchSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return IngestionBatch.objects.filter(tenant=_get_tenant(self.request.user))

    @action(detail=True, methods=['get'])
    def errors(self, request, pk=None):
        return Response(ParseErrorSerializer(ParseError.objects.filter(batch=self.get_object()), many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def bulk_approve(request):
    tenant = _get_tenant(request.user)
    recs = EmissionRecord.objects.filter(tenant=tenant, id__in=request.data.get('ids', []), is_locked=False)
    now = timezone.now()
    for rec in recs:
        rec.status = 'approved'; rec.reviewed_by = request.user
        rec.reviewed_at = now; rec.is_locked = True; rec.save()
        AuditLog.objects.create(record=rec, user=request.user, action='approved', detail={'bulk': True})
    return Response({'approved': recs.count()})


# from django.contrib.auth import authenticate, login, logout
# from django.contrib.auth.models import User
# from django.utils import timezone
# from django.db.models import Sum, Count, Q
# from rest_framework import viewsets, status
# from rest_framework.decorators import api_view, permission_classes, action
# from rest_framework.permissions import IsAuthenticated, AllowAny
# from rest_framework.response import Response
# from decimal import Decimal
# import json

# from .models import Tenant, TenantUser, IngestionBatch, EmissionRecord, AuditLog, ParseError
# from .serializers import (TenantSerializer, IngestionBatchSerializer,
#                           EmissionRecordSerializer, AuditLogSerializer, ParseErrorSerializer)
# from .parsers import parse_sap_csv, parse_utility_csv, parse_travel_csv


# # ---------------------------------------------------------------------------
# # Auth
# # ---------------------------------------------------------------------------

# @api_view(['POST'])
# @permission_classes([AllowAny])
# def login_view(request):
#     username = request.data.get('username')
#     password = request.data.get('password')
#     user = authenticate(request, username=username, password=password)
#     if user:
#         login(request, user)
#         try:
#             tu = user.tenant_user
#             tenant = {'id': str(tu.tenant.id), 'name': tu.tenant.name, 'slug': tu.tenant.slug}
#             role = tu.role
#         except TenantUser.DoesNotExist:
#             tenant = None
#             role = 'admin'
#         return Response({
#             'id': user.id, 'username': user.username,
#             'full_name': user.get_full_name(),
#             'email': user.email, 'tenant': tenant, 'role': role
#         })
#     return Response({'error': 'Invalid credentials'}, status=400)


# @api_view(['POST'])
# def logout_view(request):
#     logout(request)
#     return Response({'ok': True})


# @api_view(['GET'])
# @permission_classes([IsAuthenticated])
# def me_view(request):
#     user = request.user
#     try:
#         tu = user.tenant_user
#         tenant = {'id': str(tu.tenant.id), 'name': tu.tenant.name, 'slug': tu.tenant.slug}
#         role = tu.role
#     except TenantUser.DoesNotExist:
#         tenant = None
#         role = 'admin'
#     return Response({
#         'id': user.id, 'username': user.username,
#         'full_name': user.get_full_name(),
#         'email': user.email, 'tenant': tenant, 'role': role
#     })


# # ---------------------------------------------------------------------------
# # Dashboard stats
# # ---------------------------------------------------------------------------

# @api_view(['GET'])
# @permission_classes([IsAuthenticated])
# def dashboard_stats(request):
#     try:
#         tenant = request.user.tenant_user.tenant
#     except TenantUser.DoesNotExist:
#         tenant = Tenant.objects.first()

#     qs = EmissionRecord.objects.filter(tenant=tenant)

#     total_co2e = qs.filter(status='approved').aggregate(t=Sum('co2e_kg'))['t'] or 0
#     pending = qs.filter(status='pending').count()
#     flagged = qs.filter(is_suspicious=True).count()
#     approved = qs.filter(status='approved').count()
#     rejected = qs.filter(status='rejected').count()

#     scope_breakdown = {}
#     for s in ['1', '2', '3']:
#         val = qs.filter(scope=s, status='approved').aggregate(t=Sum('co2e_kg'))['t'] or 0
#         scope_breakdown[f'scope{s}'] = float(val)

#     category_breakdown = []
#     for cat, label in EmissionRecord.CATEGORY_CHOICES:
#         val = qs.filter(category=cat, status='approved').aggregate(t=Sum('co2e_kg'))['t'] or 0
#         if val > 0:
#             category_breakdown.append({'category': cat, 'label': label, 'co2e_kg': float(val)})

#     recent_batches = IngestionBatch.objects.filter(tenant=tenant).order_by('-ingested_at')[:5]
#     batches_data = IngestionBatchSerializer(recent_batches, many=True).data

#     return Response({
#         'total_co2e_kg': float(total_co2e),
#         'pending': pending, 'flagged': flagged,
#         'approved': approved, 'rejected': rejected,
#         'scope_breakdown': scope_breakdown,
#         'category_breakdown': category_breakdown,
#         'recent_batches': batches_data,
#     })


# # ---------------------------------------------------------------------------
# # Ingestion
# # ---------------------------------------------------------------------------

# def _get_tenant(user):
#     try:
#         return user.tenant_user.tenant
#     except TenantUser.DoesNotExist:
#         return Tenant.objects.first()


# def _save_records(parsed, errors, batch, tenant, source_system):
#     for r in parsed:
#         rec = EmissionRecord(
#             tenant=tenant, batch=batch,
#             scope=r['scope'], category=r['category'],
#             activity_value=r['activity_value'], activity_unit=r['activity_unit'],
#             emission_factor=r.get('emission_factor'),
#             emission_factor_source=r.get('emission_factor_source', ''),
#             co2e_kg=r.get('co2e_kg'),
#             period_start=r['period_start'], period_end=r['period_end'],
#             source_system=source_system,
#             source_record_id=r.get('source_record_id', ''),
#             raw_data=r.get('raw_data', {}),
#             facility_code=r.get('facility_code', ''),
#             facility_name=r.get('facility_name', ''),
#             is_suspicious=r.get('is_suspicious', False),
#             suspicion_reason=r.get('suspicion_reason', ''),
#         )
#         rec.save()
#         AuditLog.objects.create(record=rec, user=None, action='created',
#                                 detail={'source': source_system, 'batch': str(batch.id)})

#     for e in errors:
#         ParseError.objects.create(
#             batch=batch, row_number=e.get('row'),
#             raw_row=e.get('raw', {}), error_message=e.get('error', '')
#         )

#     batch.total_rows = len(parsed) + len(errors)
#     batch.passed_rows = len(parsed)
#     batch.failed_rows = len(errors)
#     batch.status = 'completed'
#     batch.save()


# @api_view(['POST'])
# @permission_classes([IsAuthenticated])
# def ingest_sap(request):
#     file = request.FILES.get('file')
#     if not file:
#         return Response({'error': 'No file provided'}, status=400)
#     tenant = _get_tenant(request.user)
#     batch = IngestionBatch.objects.create(
#         tenant=tenant, source_type='sap', file_name=file.name,
#         ingested_by=request.user, status='processing'
#     )
#     try:
#         content = file.read().decode('utf-8', errors='replace')
#         parsed, errors = parse_sap_csv(content)
#         _save_records(parsed, errors, batch, tenant, 'sap')
#         return Response(IngestionBatchSerializer(batch).data, status=201)
#     except Exception as e:
#         batch.status = 'failed'
#         batch.notes = str(e)
#         batch.save()
#         return Response({'error': str(e)}, status=500)


# @api_view(['POST'])
# @permission_classes([IsAuthenticated])
# def ingest_utility(request):
#     file = request.FILES.get('file')
#     if not file:
#         return Response({'error': 'No file provided'}, status=400)
#     tenant = _get_tenant(request.user)
#     batch = IngestionBatch.objects.create(
#         tenant=tenant, source_type='utility', file_name=file.name,
#         ingested_by=request.user, status='processing'
#     )
#     try:
#         content = file.read().decode('utf-8', errors='replace')
#         parsed, errors = parse_utility_csv(content)
#         _save_records(parsed, errors, batch, tenant, 'utility_csv')
#         return Response(IngestionBatchSerializer(batch).data, status=201)
#     except Exception as e:
#         batch.status = 'failed'
#         batch.notes = str(e)
#         batch.save()
#         return Response({'error': str(e)}, status=500)


# @api_view(['POST'])
# @permission_classes([IsAuthenticated])
# def ingest_travel(request):
#     file = request.FILES.get('file')
#     if not file:
#         return Response({'error': 'No file provided'}, status=400)
#     tenant = _get_tenant(request.user)
#     batch = IngestionBatch.objects.create(
#         tenant=tenant, source_type='travel', file_name=file.name,
#         ingested_by=request.user, status='processing'
#     )
#     try:
#         content = file.read().decode('utf-8', errors='replace')
#         parsed, errors = parse_travel_csv(content)
#         _save_records(parsed, errors, batch, tenant, 'concur_csv')
#         return Response(IngestionBatchSerializer(batch).data, status=201)
#     except Exception as e:
#         batch.status = 'failed'
#         batch.notes = str(e)
#         batch.save()
#         return Response({'error': str(e)}, status=500)


# # ---------------------------------------------------------------------------
# # Records viewset
# # ---------------------------------------------------------------------------

# class EmissionRecordViewSet(viewsets.ModelViewSet):
#     serializer_class = EmissionRecordSerializer
#     permission_classes = [IsAuthenticated]

#     def get_queryset(self):
#         try:
#             tenant = self.request.user.tenant_user.tenant
#         except TenantUser.DoesNotExist:
#             tenant = Tenant.objects.first()

#         qs = EmissionRecord.objects.filter(tenant=tenant).select_related('batch', 'reviewed_by')

#         # Filters
#         scope = self.request.query_params.get('scope')
#         if scope:
#             qs = qs.filter(scope=scope)
#         status_f = self.request.query_params.get('status')
#         if status_f:
#             qs = qs.filter(status=status_f)
#         suspicious = self.request.query_params.get('suspicious')
#         if suspicious == 'true':
#             qs = qs.filter(is_suspicious=True)
#         source = self.request.query_params.get('source')
#         if source:
#             qs = qs.filter(source_system=source)
#         batch_id = self.request.query_params.get('batch')
#         if batch_id:
#             qs = qs.filter(batch_id=batch_id)
#         search = self.request.query_params.get('search')
#         if search:
#             qs = qs.filter(Q(facility_name__icontains=search) | Q(category__icontains=search))

#         return qs

#     @action(detail=True, methods=['post'])
#     def approve(self, request, pk=None):
#         record = self.get_object()
#         if record.is_locked:
#             return Response({'error': 'Record is locked'}, status=400)
#         record.status = 'approved'
#         record.reviewed_by = request.user
#         record.reviewed_at = timezone.now()
#         record.is_locked = True
#         record.review_notes = request.data.get('notes', '')
#         record.save()
#         AuditLog.objects.create(record=record, user=request.user, action='approved',
#                                 detail={'notes': record.review_notes})
#         return Response(EmissionRecordSerializer(record).data)

#     @action(detail=True, methods=['post'])
#     def reject(self, request, pk=None):
#         record = self.get_object()
#         if record.is_locked:
#             return Response({'error': 'Record is locked'}, status=400)
#         record.status = 'rejected'
#         record.reviewed_by = request.user
#         record.reviewed_at = timezone.now()
#         record.review_notes = request.data.get('notes', '')
#         record.save()
#         AuditLog.objects.create(record=record, user=request.user, action='rejected',
#                                 detail={'notes': record.review_notes})
#         return Response(EmissionRecordSerializer(record).data)

#     @action(detail=True, methods=['post'])
#     def flag(self, request, pk=None):
#         record = self.get_object()
#         record.is_suspicious = True
#         record.suspicion_reason = request.data.get('reason', 'Manually flagged by analyst')
#         record.status = 'flagged'
#         record.save()
#         AuditLog.objects.create(record=record, user=request.user, action='flagged',
#                                 detail={'reason': record.suspicion_reason})
#         return Response(EmissionRecordSerializer(record).data)

#     @action(detail=True, methods=['get'])
#     def audit(self, request, pk=None):
#         record = self.get_object()
#         logs = AuditLog.objects.filter(record=record)
#         return Response(AuditLogSerializer(logs, many=True).data)


# class IngestionBatchViewSet(viewsets.ReadOnlyModelViewSet):
#     serializer_class = IngestionBatchSerializer
#     permission_classes = [IsAuthenticated]

#     def get_queryset(self):
#         try:
#             tenant = self.request.user.tenant_user.tenant
#         except TenantUser.DoesNotExist:
#             tenant = Tenant.objects.first()
#         return IngestionBatch.objects.filter(tenant=tenant)

#     @action(detail=True, methods=['get'])
#     def errors(self, request, pk=None):
#         batch = self.get_object()
#         errors = ParseError.objects.filter(batch=batch)
#         return Response(ParseErrorSerializer(errors, many=True).data)


# @api_view(['POST'])
# @permission_classes([IsAuthenticated])
# def bulk_approve(request):
#     ids = request.data.get('ids', [])
#     try:
#         tenant = request.user.tenant_user.tenant
#     except TenantUser.DoesNotExist:
#         tenant = Tenant.objects.first()
#     records = EmissionRecord.objects.filter(tenant=tenant, id__in=ids, is_locked=False)
#     now = timezone.now()
#     for rec in records:
#         rec.status = 'approved'
#         rec.reviewed_by = request.user
#         rec.reviewed_at = now
#         rec.is_locked = True
#         rec.save()
#         AuditLog.objects.create(record=rec, user=request.user, action='approved',
#                                 detail={'bulk': True})
#     return Response({'approved': records.count()})
