from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Tenant, TenantUser, IngestionBatch, EmissionRecord, AuditLog, ParseError


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']


class TenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = '__all__'


class IngestionBatchSerializer(serializers.ModelSerializer):
    ingested_by_name = serializers.SerializerMethodField()
    source_type_display = serializers.CharField(source='get_source_type_display', read_only=True)

    class Meta:
        model = IngestionBatch
        fields = '__all__'

    def get_ingested_by_name(self, obj):
        if obj.ingested_by:
            return obj.ingested_by.get_full_name() or obj.ingested_by.username
        return 'System'


class EmissionRecordSerializer(serializers.ModelSerializer):
    scope_display = serializers.CharField(source='get_scope_display', read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    reviewed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = EmissionRecord
        fields = '__all__'
        read_only_fields = ['id', 'tenant', 'batch', 'created_at', 'updated_at',
                            'source_system', 'source_record_id', 'raw_data']

    def get_reviewed_by_name(self, obj):
        if obj.reviewed_by:
            return obj.reviewed_by.get_full_name() or obj.reviewed_by.username
        return None


class AuditLogSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = '__all__'

    def get_user_name(self, obj):
        if obj.user:
            return obj.user.get_full_name() or obj.user.username
        return 'System'


class ParseErrorSerializer(serializers.ModelSerializer):
    class Meta:
        model = ParseError
        fields = '__all__'
