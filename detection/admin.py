from django.contrib import admin
from .models import DetectionJob

@admin.register(DetectionJob)
class DetectionJobAdmin(admin.ModelAdmin):
    list_display = ['id', 'original_filename', 'status', 'total_records', 'fraud_count', 'fraud_rate', 'uploaded_by', 'created_at']
    list_filter = ['status']
    readonly_fields = ['processing_log', 'completed_at']
