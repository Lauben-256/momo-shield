import sys
import logging
import threading
from pathlib import Path
from datetime import datetime, timezone

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db import connection as db_connection

import pandas as pd

from .models import DetectionJob
from .forms import UploadForm
from dashboard.models import Transaction, FraudAlert

logger = logging.getLogger(__name__)

ML_DIR = Path(__file__).parent / 'ml'
sys.path.insert(0, str(ML_DIR))


def _run_detection(job_id: int):
    """
    Core detection pipeline. Always called in a background thread.
    Opens its own fresh DB connection (required for SQLite thread safety).
    """
    from preprocess import preprocess_inference_data, validate_inference_csv
    from predict import predict_dataframe, get_fraud_reason

    # Close any inherited connection — Django will open a fresh one for this thread
    db_connection.close()

    log_lines = []
    try:
        job = DetectionJob.objects.get(pk=job_id)
        job.status = 'processing'
        job.save(update_fields=['status'])

        df = pd.read_csv(job.uploaded_file.path)
        log_lines.append(f"Loaded {len(df):,} rows from uploaded file")

        validation = validate_inference_csv(df)
        if not validation['valid']:
            raise ValueError(f"CSV validation failed: {'; '.join(validation['errors'])}")

        X_features, df_enriched = preprocess_inference_data(df)
        log_lines.append(f"Preprocessing complete — {X_features.shape[1]} features")

        results = predict_dataframe(X_features)
        log_lines.append(
            f"Inference complete — {results['fraud_count']} fraud / {results['total']} total"
        )

        id_col = next(
            (c for c in ['txn_id', 'transaction_id', 'id'] if c in df.columns), None
        )

        transactions_to_create = []
        for i, (prob, pred) in enumerate(zip(results['probabilities'], results['predictions'])):
            row    = df_enriched.iloc[i]
            txn_id = str(row[id_col]) if id_col else f"JOB{job.pk}-{i+1:06d}"

            transactions_to_create.append(Transaction(
                transaction_id    = txn_id,
                sender            = str(row.get('sender', '')),
                receiver          = str(row.get('receiver', '')),
                amount            = float(row.get('amount_ugx', 0)),
                transaction_type  = str(row.get('txn_type', 'Unknown')),
                is_fraud          = bool(pred),
                fraud_score       = round(float(prob), 4),
                fraud_probability = round(float(prob), 4),
                detection_job     = job,
                uploaded_by       = job.uploaded_by,
            ))

        Transaction.objects.bulk_create(transactions_to_create, ignore_conflicts=True)
        log_lines.append(f"Saved {len(transactions_to_create)} transactions")

        saved_fraud = Transaction.objects.filter(detection_job=job, is_fraud=True)

        alerts_to_create  = []
        fraud_value_ugx   = 0.0
        high_risk_count   = 0
        medium_risk_count = 0
        low_risk_count    = 0

        id_to_idx = {}
        for i, t in enumerate(transactions_to_create):
            id_to_idx[t.transaction_id] = i

        for txn in saved_fraud:
            idx      = id_to_idx.get(txn.transaction_id, 0)
            row_dict = df_enriched.iloc[idx].to_dict()
            prob     = txn.fraud_probability or 0.0

            severity = (
                'high'   if prob >= 0.75 else
                'medium' if prob >= 0.40 else
                'low'
            )
            reason = get_fraud_reason(row_dict, prob)

            alerts_to_create.append(
                FraudAlert(transaction=txn, severity=severity, reason=reason)
            )
            fraud_value_ugx += float(txn.amount)
            if severity == 'high':
                high_risk_count += 1
            elif severity == 'medium':
                medium_risk_count += 1
            else:
                low_risk_count += 1

        FraudAlert.objects.bulk_create(alerts_to_create, ignore_conflicts=True)
        log_lines.append(f"Created {len(alerts_to_create)} fraud alerts")

        total = results['total']
        fraud = results['fraud_count']
        rate  = round((fraud / total * 100), 2) if total else 0.0

        job.status         = 'done'
        job.total_records  = total
        job.fraud_count    = fraud
        job.fraud_rate     = rate
        job.processing_log = {
            'high_risk_count':   high_risk_count,
            'medium_risk_count': medium_risk_count,
            'low_risk_count':    low_risk_count,
            'fraud_value_ugx':   round(fraud_value_ugx, 2),
            'log':               log_lines,
        }
        job.completed_at = datetime.now(timezone.utc)
        job.save()

    except Exception as e:
        logger.exception("Detection job failed")
        try:
            job = DetectionJob.objects.get(pk=job_id)
            job.status         = 'failed'
            job.error_message  = str(e)
            job.processing_log = {'log': log_lines, 'error': str(e)}
            job.save()
        except Exception:
            logger.exception("Could not save failure status")
    finally:
        # Always close the DB connection when the thread finishes
        db_connection.close()


def _run_detection_async(job_id: int):
    """Spawn a background thread to run detection without blocking the HTTP response."""
    t = threading.Thread(target=_run_detection, args=(job_id,), daemon=True)
    t.start()


@login_required
def upload(request):
    from predict import model_loaded, get_training_metrics, get_model_comparison

    form = UploadForm(request.POST or None, request.FILES or None)

    if request.method == 'POST' and form.is_valid():
        f = form.cleaned_data['csv_file']
        job = DetectionJob.objects.create(
            uploaded_file     = f,
            original_filename = f.name,
            uploaded_by       = request.user,
        )
        # Kick off detection in a background thread — returns immediately
        _run_detection_async(job.pk)
        # Redirect to results page (shows spinner until job is done)
        return redirect('detection:results', job_id=job.pk)

    return render(request, 'detection/upload.html', {
        'form':        form,
        'model_ready': model_loaded(),
        'metrics':     get_training_metrics(),
        'comparison':  get_model_comparison(),
    })


@login_required
def results(request, job_id):
    job = get_object_or_404(DetectionJob, pk=job_id, uploaded_by=request.user)
    transactions = (
        Transaction.objects
        .filter(detection_job=job)
        .order_by('-fraud_probability')
        .select_related('alert')
    )
    return render(request, 'detection/results.html', {
        'job':          job,
        'transactions': transactions[:300],
    })


@login_required
def job_progress(request, job_id):
    """AJAX polling endpoint — returns live job status for the progress spinner."""
    job = get_object_or_404(DetectionJob, pk=job_id, uploaded_by=request.user)
    return JsonResponse({
        'status':        job.status,
        'total_records': job.total_records,
        'fraud_count':   job.fraud_count,
        'fraud_rate':    job.fraud_rate,
        'is_complete':   job.is_complete,
        'error_message': job.error_message,
    })


@login_required
def train_status(request):
    from predict import model_loaded, get_training_metrics, get_model_comparison
    return JsonResponse({
        'model_ready': model_loaded(),
        'metrics':     get_training_metrics(),
        'comparison':  get_model_comparison(),
    })
