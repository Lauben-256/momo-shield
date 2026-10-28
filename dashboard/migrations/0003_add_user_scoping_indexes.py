# Stub migration — database already has these changes applied.
from django.db import migrations


class Migration(migrations.Migration):
    """
    This migration was applied during the initial project build.
    The database already contains all indexes and schema changes.
    This file exists solely so Django's migration history is consistent.
    """
    dependencies = [
        ('dashboard', '0002_fraudalert_dashboard_f_severit_7e498d_idx_and_more'),
    ]
    operations = []
