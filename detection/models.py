from django.db import models
from django.conf import settings


class DetectionJob(models.Model):
    STATUS_CHOICES = [
        ('pending',    'Pending'),
        ('processing', 'Processing'),
        ('done',       'Done'),
        ('failed',     'Failed'),
    ]

    uploaded_file  = models.FileField(upload_to='uploads/')
    original_filename = models.CharField(max_length=255, blank=True)
    status         = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    total_records  = models.IntegerField(default=0)
    fraud_count    = models.IntegerField(default=0)
    fraud_rate     = models.FloatField(default=0.0)
    error_message  = models.TextField(blank=True)
    processing_log = models.JSONField(default=dict, blank=True)
    uploaded_by    = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at     = models.DateTimeField(auto_now_add=True)
    completed_at   = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Job #{self.pk} — {self.status} ({self.total_records} records)"

    @property
    def is_complete(self):
        return self.status == 'done'

    @property
    def legitimate_count(self):
        return self.total_records - self.fraud_count
