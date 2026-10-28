"""
MoMo Shield REST API Views
Provides endpoints for the React frontend.
"""
import logging
from django.db.models import Count, Avg, Sum, Q
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from dashboard.models import Transaction, FraudAlert
from detection.models import DetectionJob
from .serializers import (
    TransactionSerializer, DetectionJobSerializer,
    DetectionJobSummarySerializer, FraudAlertSerializer
)

logger = logging.getLogger(__name__)


class TransactionListAPI(generics.ListAPIView):
    """GET /api/transactions/ — paginated transaction list with optional filters."""
    serializer_class = TransactionSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        qs = Transaction.objects.select_related('alert').all()
        fraud = self.request.query_params.get('fraud')
        txn_type = self.request.query_params.get('type')
        risk = self.request.query_params.get('risk')
        job_id = self.request.query_params.get('job')

        if fraud == 'true':
            qs = qs.filter(is_fraud=True)
        elif fraud == 'false':
            qs = qs.filter(is_fraud=False)
        if txn_type:
            qs = qs.filter(transaction_type=txn_type)
        if risk == 'high':
            qs = qs.filter(fraud_probability__gte=0.75)
        elif risk == 'medium':
            qs = qs.filter(fraud_probability__gte=0.40, fraud_probability__lt=0.75)
        elif risk == 'low':
            qs = qs.filter(fraud_probability__lt=0.40)
        if job_id:
            qs = qs.filter(detection_job_id=job_id)

        return qs.order_by('-fraud_probability', '-created_at')


class AlertListAPI(generics.ListAPIView):
    """GET /api/alerts/ — fraud alerts."""
    serializer_class = FraudAlertSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        qs = FraudAlert.objects.select_related('transaction').all()
        severity = self.request.query_params.get('severity')
        if severity:
            qs = qs.filter(severity=severity)
        return qs.order_by('-created_at')


@api_view(['GET'])
def stats_api(request):
    """GET /api/stats/ — dashboard aggregate statistics."""
    total = Transaction.objects.count()
    fraud_count = Transaction.objects.filter(is_fraud=True).count()
    high_risk = Transaction.objects.filter(fraud_probability__gte=0.75).count()
    medium_risk = Transaction.objects.filter(
        fraud_probability__gte=0.40, fraud_probability__lt=0.75
    ).count()
    avg_prob = Transaction.objects.filter(is_fraud=True).aggregate(
        avg=Avg('fraud_probability')
    )['avg'] or 0
    total_value = Transaction.objects.aggregate(s=Sum('amount'))['s'] or 0
    fraud_value = Transaction.objects.filter(is_fraud=True).aggregate(s=Sum('amount'))['s'] or 0

    by_type = list(
        Transaction.objects.values('transaction_type')
        .annotate(total=Count('id'), fraud=Count('id', filter=Q(is_fraud=True)))
        .order_by('-total')
    )

    recent_jobs = DetectionJob.objects.order_by('-created_at')[:5]

    return Response({
        'total_transactions': total,
        'fraud_count': fraud_count,
        'legitimate_count': total - fraud_count,
        'fraud_rate': round(fraud_count / total * 100, 2) if total else 0,
        'high_risk_count': high_risk,
        'medium_risk_count': medium_risk,
        'avg_fraud_probability': round(float(avg_prob) * 100, 1),
        'total_value_ugx': float(total_value),
        'fraud_value_ugx': float(fraud_value),
        'by_transaction_type': by_type,
        'recent_jobs': DetectionJobSummarySerializer(recent_jobs, many=True).data,
    })


@api_view(['POST'])
@parser_classes([MultiPartParser, FormParser])
def upload_api(request):
    """
    POST /api/detect/upload/
    Accepts a CSV file, runs fraud detection, returns job results.
    """
    if 'file' not in request.FILES:
        return Response({'error': 'No file uploaded. Send CSV as "file" field.'},
                        status=status.HTTP_400_BAD_REQUEST)

    uploaded_file = request.FILES['file']
    if not uploaded_file.name.endswith('.csv'):
        return Response({'error': 'Only CSV files are accepted.'},
                        status=status.HTTP_400_BAD_REQUEST)

    # Create job record
    job = DetectionJob.objects.create(
        uploaded_file=uploaded_file,
        original_filename=uploaded_file.name,
        status='processing',
        uploaded_by=request.user if request.user.is_authenticated else None,
    )

    try:
        from detection.views import _run_detection
        _run_detection(job)
        serializer = DetectionJobSerializer(job)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    except FileNotFoundError as e:
        job.status = 'failed'
        job.error_message = str(e)
        job.save()
        return Response(
            {'error': str(e), 'hint': 'Run python detection/ml/train.py to train the model first.'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )
    except Exception as e:
        job.status = 'failed'
        job.error_message = str(e)
        job.save()
        logger.exception(f"Upload API job {job.pk} failed")
        return Response({'error': str(e), 'job_id': job.pk},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def job_detail_api(request, job_id):
    """GET /api/detect/jobs/<id>/ — job status + predictions."""
    try:
        job = DetectionJob.objects.get(pk=job_id)
    except DetectionJob.DoesNotExist:
        return Response({'error': 'Job not found'}, status=status.HTTP_404_NOT_FOUND)

    serializer = DetectionJobSerializer(job)
    return Response(serializer.data)


@api_view(['GET'])
def jobs_list_api(request):
    """GET /api/detect/jobs/ — list all detection jobs."""
    jobs = DetectionJob.objects.order_by('-created_at')[:20]
    serializer = DetectionJobSummarySerializer(jobs, many=True)
    return Response(serializer.data)


@api_view(['GET'])
def job_progress_api(request, job_id):
    """GET /api/detect/jobs/<id>/progress/ — lightweight progress polling."""
    try:
        job = DetectionJob.objects.get(pk=job_id)
    except DetectionJob.DoesNotExist:
        return Response({'error': 'Job not found'}, status=status.HTTP_404_NOT_FOUND)
    return Response({
        'status':        job.status,
        'progress_pct':  job.processing_log.get('progress_pct', 0),
        'rows_done':     job.processing_log.get('rows_done', 0),
        'total_records': job.total_records,
        'fraud_count':   job.fraud_count,
        'error':         job.error_message,
    })
