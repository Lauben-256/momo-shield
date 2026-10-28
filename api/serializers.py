from rest_framework import serializers
from dashboard.models import Transaction, FraudAlert
from detection.models import DetectionJob


class FraudAlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = FraudAlert
        fields = ['severity', 'reason', 'reviewed', 'created_at']


class TransactionSerializer(serializers.ModelSerializer):
    alert = FraudAlertSerializer(read_only=True)
    risk_level = serializers.ReadOnlyField()

    class Meta:
        model = Transaction
        fields = [
            'transaction_id', 'sender', 'receiver', 'amount',
            'transaction_type', 'is_fraud', 'fraud_score',
            'fraud_probability', 'risk_level', 'alert', 'created_at',
        ]


class DetectionJobSerializer(serializers.ModelSerializer):
    transactions = TransactionSerializer(many=True, read_only=True)
    legitimate_count = serializers.ReadOnlyField()

    class Meta:
        model = DetectionJob
        fields = [
            'id', 'original_filename', 'status', 'total_records',
            'fraud_count', 'legitimate_count', 'fraud_rate',
            'processing_log', 'error_message', 'created_at', 'completed_at',
            'transactions',
        ]


class DetectionJobSummarySerializer(serializers.ModelSerializer):
    legitimate_count = serializers.ReadOnlyField()

    class Meta:
        model = DetectionJob
        fields = [
            'id', 'original_filename', 'status', 'total_records',
            'fraud_count', 'legitimate_count', 'fraud_rate',
            'created_at', 'completed_at',
        ]
