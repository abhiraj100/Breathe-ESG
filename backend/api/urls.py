from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register('records', views.EmissionRecordViewSet, basename='record')
router.register('batches', views.IngestionBatchViewSet, basename='batch')

urlpatterns = [
    path('auth/login/',     views.login_view),
    path('auth/logout/',    views.logout_view),
    path('auth/me/',        views.me_view),
    path('dashboard/',      views.dashboard_stats),
    path('ingest/sap/',     views.ingest_sap),
    path('ingest/utility/', views.ingest_utility),
    path('ingest/travel/',  views.ingest_travel),
    path('bulk-approve/',   views.bulk_approve),
    path('', include(router.urls)),
]