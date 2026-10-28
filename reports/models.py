from django.db import models
from django.conf import settings
from detection.models import DetectionJob


class Report(models.Model):
    REPORT_TYPES = [
        ('fraud_summary', 'Fraud Summary'),
        ('transaction_summary', 'Transaction Summary'),
        ('high_risk_accounts', 'High Risk Accounts'),
        ('weekly_digest', 'Weekly Digest'),
    ]
    FORMAT_CHOICES = [
        ('pdf', 'PDF'),
        ('excel', 'Excel'),
    ]

    title       = models.CharField(max_length=200)
    report_type = models.CharField(max_length=50, choices=REPORT_TYPES)
    format      = models.CharField(max_length=10, choices=FORMAT_CHOICES, default='pdf')
    detection_job = models.ForeignKey(DetectionJob, on_delete=models.SET_NULL, null=True, blank=True)
    file        = models.FileField(upload_to='reports/', null=True, blank=True)
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.format.upper()})"
