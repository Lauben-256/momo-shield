from django.contrib import admin
from .models import Transaction, FraudAlert

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['transaction_id', 'sender', 'receiver', 'amount', 'transaction_type', 'is_fraud', 'fraud_probability', 'created_at']
    list_filter = ['is_fraud', 'transaction_type']
    search_fields = ['transaction_id', 'sender', 'receiver']

@admin.register(FraudAlert)
class FraudAlertAdmin(admin.ModelAdmin):
    list_display = ['transaction', 'severity', 'reviewed', 'created_at']
    list_filter = ['severity', 'reviewed']
