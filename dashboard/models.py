from django.db import models
from django.conf import settings


class Transaction(models.Model):
    TXN_TYPES = [
        ('Send Money',    'Send Money'),
        ('Withdraw',      'Withdraw'),
        ('Deposit',       'Deposit'),
        ('Pay Bill',      'Pay Bill'),
        ('Buy Goods',     'Buy Goods'),
        ('Bank Transfer', 'Bank Transfer'),
        ('Airtime',       'Airtime'),
        ('Unknown',       'Unknown'),
    ]

    transaction_id    = models.CharField(max_length=100, unique=True)
    sender            = models.CharField(max_length=100, blank=True)
    receiver          = models.CharField(max_length=100, blank=True)
    amount            = models.DecimalField(max_digits=14, decimal_places=2)
    timestamp         = models.DateTimeField(null=True, blank=True)
    transaction_type  = models.CharField(max_length=50, choices=TXN_TYPES, default='Unknown')
    is_fraud          = models.BooleanField(default=False)
    fraud_score       = models.FloatField(null=True, blank=True)
    fraud_probability = models.FloatField(null=True, blank=True)
    detection_job     = models.ForeignKey(
        'detection.DetectionJob', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='transactions'
    )
    uploaded_by       = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='transactions'
    )
    created_at        = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['uploaded_by']),        # fast per-user filter
            models.Index(fields=['detection_job']),      # fast per-job filter
            models.Index(fields=['is_fraud']),
            models.Index(fields=['transaction_type']),
            models.Index(fields=['uploaded_by', 'is_fraud']),   # compound for dashboard stats
            models.Index(fields=['uploaded_by', 'created_at']), # compound for ordered listing
        ]

    def __str__(self):
        return f"{self.transaction_id} — {'FRAUD' if self.is_fraud else 'OK'}"

    @property
    def risk_level(self):
        p = self.fraud_probability
        if p is None:
            return 'unknown'
        if p >= 0.75:
            return 'high'
        if p >= 0.40:
            return 'medium'
        return 'low'


class FraudAlert(models.Model):
    SEVERITY = [
        ('low',    'Low'),
        ('medium', 'Medium'),
        ('high',   'High'),
    ]

    transaction = models.OneToOneField(
        Transaction, on_delete=models.CASCADE, related_name='alert'
    )
    severity    = models.CharField(max_length=10, choices=SEVERITY)
    reason      = models.TextField()
    reviewed    = models.BooleanField(default=False)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='reviewed_alerts'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            # Fast filter: alerts for a specific user's transactions
            models.Index(fields=['transaction']),
        ]

    def __str__(self):
        return f"Alert [{self.severity.upper()}] — {self.transaction.transaction_id}"


class AccountStatus(models.Model):
    """Tracks freeze/suspension state for a mobile money account number."""
    STATUS = [
        ('active',    'Active'),
        ('flagged',   'Flagged'),
        ('frozen',    'Frozen'),
        ('cleared',   'Cleared'),
    ]
    account_number  = models.CharField(max_length=100, unique=True)
    status          = models.CharField(max_length=20, choices=STATUS, default='active')
    fraud_hit_count = models.IntegerField(default=0)
    frozen_by       = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='frozen_accounts'
    )
    frozen_at       = models.DateTimeField(null=True, blank=True)
    cleared_at      = models.DateTimeField(null=True, blank=True)
    notes           = models.TextField(blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        indexes  = [models.Index(fields=['status']), models.Index(fields=['account_number'])]

    def __str__(self):
        return f"{self.account_number} [{self.status.upper()}]"

    @property
    def is_frozen(self):
        return self.status == 'frozen'


class ReviewQueue(models.Model):
    """Fraud transactions placed on hold pending human analyst decision."""
    DECISION = [
        ('pending',   'Pending Review'),
        ('confirmed', 'Confirmed Fraud — Blocked'),
        ('cleared',   'Cleared — Allowed'),
    ]
    transaction  = models.OneToOneField(
        Transaction, on_delete=models.CASCADE, related_name='review'
    )
    decision     = models.CharField(max_length=20, choices=DECISION, default='pending')
    auto_held    = models.BooleanField(default=True)   # True = held by model, False = manual
    analyst      = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='reviewed_queue'
    )
    decided_at   = models.DateTimeField(null=True, blank=True)
    analyst_note = models.TextField(blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes  = [models.Index(fields=['decision'])]

    def __str__(self):
        return f"Review [{self.decision}] — {self.transaction.transaction_id}"
