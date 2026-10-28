from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone

from .models import SimulationSession
from dashboard.models import Transaction, FraudAlert, AccountStatus, ReviewQueue


@login_required
def monitor(request):
    """Live simulation monitor page."""
    session = SimulationSession.objects.filter(status='running').first()
    pending_count = ReviewQueue.objects.filter(decision='pending').count()
    frozen_count  = AccountStatus.objects.filter(status='frozen').count()
    return render(request, 'simulation/monitor.html', {
        'session':       session,
        'pending_count': pending_count,
        'frozen_count':  frozen_count,
    })


@login_required
@require_POST
def start(request):
    """Start a new simulation session (called via AJAX)."""
    # Stop any running sessions first
    SimulationSession.objects.filter(status='running').update(
        status='stopped', stopped_at=timezone.now()
    )
    session = SimulationSession.objects.create(
        tps=float(request.POST.get('tps', 2.0)),
        started_by=request.user,
    )
    return JsonResponse({'session_id': session.pk, 'status': 'started'})


@login_required
@require_POST
def stop(request):
    """Stop the running simulation session."""
    updated = SimulationSession.objects.filter(status='running').update(
        status='stopped', stopped_at=timezone.now()
    )
    return JsonResponse({'stopped': updated})


@login_required
def review_queue(request):
    """Human review queue — pending fraud holds."""
    pending   = ReviewQueue.objects.filter(
        decision='pending').select_related('transaction', 'transaction__alert')
    decided   = ReviewQueue.objects.exclude(
        decision='pending').select_related('transaction', 'analyst')[:50]
    return render(request, 'simulation/review_queue.html', {
        'pending': pending,
        'decided': decided,
    })


@login_required
def accounts(request):
    """Account freeze management page."""
    frozen  = AccountStatus.objects.filter(status='frozen')
    flagged = AccountStatus.objects.filter(status='flagged')
    return render(request, 'simulation/accounts.html', {
        'frozen':  frozen,
        'flagged': flagged,
    })


@login_required
def api_status(request):
    """AJAX: return current simulation status and stats."""
    session = SimulationSession.objects.filter(status='running').first()
    pending = ReviewQueue.objects.filter(decision='pending').count()
    frozen  = AccountStatus.objects.filter(status='frozen').count()
    recent  = list(
        Transaction.objects.filter(timestamp__isnull=False)
        .order_by('-created_at')[:10]
        .values('transaction_id', 'sender', 'receiver',
                'amount', 'transaction_type', 'is_fraud',
                'fraud_probability', 'created_at')
    )
    return JsonResponse({
        'running':       bool(session),
        'session_id':    session.pk if session else None,
        'total':         session.total_generated if session else 0,
        'fraud':         session.total_fraud     if session else 0,
        'pending_holds': pending,
        'frozen_accounts': frozen,
        'recent':        recent,
    })
