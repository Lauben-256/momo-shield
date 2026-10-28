from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Extended user model for MoMo Shield."""
    ROLES = [
        ('admin', 'Administrator'),
        ('analyst', 'Fraud Analyst'),
        ('viewer', 'Viewer'),
    ]
    role = models.CharField(max_length=20, choices=ROLES, default='analyst')
    organisation = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.role})"

    @property
    def is_analyst(self):
        return self.role in ('admin', 'analyst')

    def get_initials(self):
        """Return up to 2 initials for the avatar display."""
        full = self.get_full_name()
        if full:
            parts = full.split()
            return (parts[0][0] + parts[-1][0]).upper() if len(parts) > 1 else parts[0][:2].upper()
        return self.username[:2].upper()
