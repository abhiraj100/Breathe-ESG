from django.db import models
from django.contrib.auth.models import User
import uuid


class Tenant(models.Model):
    """Multi-tenancy: each client company is a Tenant."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class TenantUser(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='tenant_user')
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='users')
    role = models.CharField(max_length=50, choices=[('admin','Admin'),('analyst','Analyst'),('viewer','Viewer')], default='analyst')

    def __str__(self):
        return f"{self.user.username} @ {self.tenant.name}"


class IngestionBatch(models.Model):
    """Tracks a single import run — source, time, who triggered it."""
    SOURCE_TYPES = [
        ('sap', 'SAP Fuel & Procurement'),
        ('utility', 'Utility (Electricity)'),
        ('travel', 'Corporate Travel'),
    ]
    STATUS_CHOICES = [
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='batches')
    source_type = models.CharField(max_length=20, choices=SOURCE_TYPES)
    file_name = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='processing')
    total_rows = models.IntegerField(default=0)
    passed_rows = models.IntegerField(default=0)
    failed_rows = models.IntegerField(default=0)
    ingested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='batches')
    ingested_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-ingested_at']

    def __str__(self):
        return f"{self.source_type} batch {self.id} ({self.tenant.name})"


class EmissionRecord(models.Model):
    """
    Normalized emission record. Every row — regardless of source —
    lands here after parsing and unit normalization.

    Scope categorization follows GHG Protocol:
      Scope 1 — Direct (fuel combustion on-site/in owned vehicles)
      Scope 2 — Indirect electricity purchased
      Scope 3 — Value chain (business travel, supply chain procurement)
    """
    SCOPE_CHOICES = [('1','Scope 1'),('2','Scope 2'),('3','Scope 3')]
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('flagged', 'Flagged / Suspicious'),
    ]
    CATEGORY_CHOICES = [
        # Scope 1
        ('stationary_combustion', 'Stationary Combustion'),
        ('mobile_combustion', 'Mobile Combustion'),
        # Scope 2
        ('purchased_electricity', 'Purchased Electricity'),
        # Scope 3
        ('business_travel_air', 'Business Travel - Air'),
        ('business_travel_hotel', 'Business Travel - Hotel'),
        ('business_travel_ground', 'Business Travel - Ground'),
        ('purchased_goods', 'Purchased Goods & Services'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='records')
    batch = models.ForeignKey(IngestionBatch, on_delete=models.CASCADE, related_name='records')

    # GHG Classification
    scope = models.CharField(max_length=1, choices=SCOPE_CHOICES)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)

    # Activity data (normalized)
    activity_value = models.DecimalField(max_digits=18, decimal_places=4)
    activity_unit = models.CharField(max_length=30)  # always normalized: kWh, liters, km, nights

    # Calculated emissions (kgCO2e)
    emission_factor = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    emission_factor_source = models.CharField(max_length=255, blank=True)
    co2e_kg = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)

    # Time period
    period_start = models.DateField()
    period_end = models.DateField()

    # Source provenance
    source_system = models.CharField(max_length=50)       # 'sap', 'utility_csv', 'concur'
    source_record_id = models.CharField(max_length=255, blank=True)  # original PK from source
    raw_data = models.JSONField(default=dict)              # verbatim row as parsed

    # Location / facility
    facility_code = models.CharField(max_length=100, blank=True)
    facility_name = models.CharField(max_length=255, blank=True)
    country = models.CharField(max_length=100, blank=True)

    # Review workflow
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    review_notes = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_records')
    reviewed_at = models.DateTimeField(null=True, blank=True)

    # Flags for analyst attention
    is_suspicious = models.BooleanField(default=False)
    suspicion_reason = models.TextField(blank=True)

    # Audit / edit trail — locked once approved
    is_locked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-period_start', 'scope']

    def __str__(self):
        return f"[{self.get_scope_display()}] {self.get_category_display()} — {self.co2e_kg} kgCO2e"


class AuditLog(models.Model):
    """Immutable log of every change to an EmissionRecord."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    record = models.ForeignKey(EmissionRecord, on_delete=models.CASCADE, related_name='audit_logs')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=50)   # 'created', 'approved', 'rejected', 'edited', 'flagged'
    detail = models.JSONField(default=dict)    # diff or note
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']


class ParseError(models.Model):
    """Rows that failed parsing — surfaces in the review dashboard."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    batch = models.ForeignKey(IngestionBatch, on_delete=models.CASCADE, related_name='errors')
    row_number = models.IntegerField(null=True, blank=True)
    raw_row = models.JSONField(default=dict)
    error_message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
