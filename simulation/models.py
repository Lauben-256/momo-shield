from django.db import models
from django.conf import settings


class SimulationSession(models.Model):
    """Tracks a live simulation run."""
    STATUS = [('running', 'Running'), ('paused', 'Paused'), ('stopped', 'Stopped')]
    status          = models.CharField(max_length=20, choices=STATUS, default='running')
    started_by      = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    tps             = models.FloatField(default=2.0)   # transactions per second
    total_generated = models.IntegerField(default=0)
    total_fraud     = models.IntegerField(default=0)
    started_at      = models.DateTimeField(auto_now_add=True)
    stopped_at      = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        return f"Session #{self.pk} [{self.status}] — {self.total_generated} txns"
