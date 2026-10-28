# Stub migration — database already has these changes applied.
from django.db import migrations


class Migration(migrations.Migration):
    """
    This migration was applied during the initial project build.
    The database already contains all these schema changes.
    This file exists solely so Django's migration history is consistent.
    """
    dependencies = [
        ('dashboard', '0001_initial'),
    ]
    operations = []
