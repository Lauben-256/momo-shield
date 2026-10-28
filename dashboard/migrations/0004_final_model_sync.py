"""
Final model sync migration.
All schema changes (indexes, field alterations) were already applied to the database
during the project build. This migration uses SeparateDatabaseAndState to update
Django's internal model state without touching the database.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0003_add_user_scoping_indexes'),
        ('detection', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # SeparateDatabaseAndState: update model state only, no DB operations.
        # The database already has all these changes from the build environment.
        migrations.SeparateDatabaseAndState(
            database_operations=[],   # do nothing to the database
            state_operations=[
                migrations.AlterField(
                    model_name='transaction',
                    name='receiver',
                    field=models.CharField(blank=True, max_length=100),
                ),
                migrations.AlterField(
                    model_name='transaction',
                    name='sender',
                    field=models.CharField(blank=True, max_length=100),
                ),
                migrations.AlterField(
                    model_name='transaction',
                    name='transaction_type',
                    field=models.CharField(
                        choices=[
                            ('Send Money', 'Send Money'), ('Withdraw', 'Withdraw'),
                            ('Deposit', 'Deposit'), ('Pay Bill', 'Pay Bill'),
                            ('Buy Goods', 'Buy Goods'), ('Bank Transfer', 'Bank Transfer'),
                            ('Airtime', 'Airtime'), ('Unknown', 'Unknown'),
                        ],
                        default='Unknown', max_length=50,
                    ),
                ),
                migrations.AlterField(
                    model_name='transaction',
                    name='uploaded_by',
                    field=models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='transactions',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                migrations.AddIndex(
                    model_name='fraudalert',
                    index=models.Index(fields=['transaction'], name='dashboard_f_transac_6dbaec_idx'),
                ),
                migrations.AddIndex(
                    model_name='transaction',
                    index=models.Index(fields=['uploaded_by'], name='dashboard_t_uploade_99acbc_idx'),
                ),
                migrations.AddIndex(
                    model_name='transaction',
                    index=models.Index(fields=['detection_job'], name='dashboard_t_detecti_5df0a8_idx'),
                ),
                migrations.AddIndex(
                    model_name='transaction',
                    index=models.Index(fields=['uploaded_by', 'is_fraud'], name='dashboard_t_uploade_3ecd66_idx'),
                ),
                migrations.AddIndex(
                    model_name='transaction',
                    index=models.Index(fields=['uploaded_by', 'created_at'], name='dashboard_t_uploade_683363_idx'),
                ),
            ],
        ),
    ]
