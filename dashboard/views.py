from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from django.db.models import Count, Avg, Q
from .models import Transaction, FraudAlert


def _user_transactions(user):
    """Return only this user's transactions. Admins see everything."""
    if user.role == 'admin':
        return Transaction.objects.all()
    return Transaction.objects.filter(uploaded_by=user)


def _user_alerts(user):
    """Return only alerts for this user's transactions. Admins see everything."""
    if user.role == 'admin':
        return FraudAlert.objects.select_related('transaction').all()
    return FraudAlert.objects.select_related('transaction').filter(
        transaction__uploaded_by=user
    )


@login_required
def home(request):
    base_txns   = _user_transactions(request.user)
    total       = base_txns.count()
    fraud_count = base_txns.filter(is_fraud=True).count()
    fraud_rate  = round((fraud_count / total * 100), 2) if total else 0
    avg_score   = base_txns.filter(is_fraud=True).aggregate(
        avg=Avg('fraud_probability'))['avg'] or 0

    by_type = list(
        base_txns.values('transaction_type')
        .annotate(total=Count('id'), fraud=Count('id', filter=Q(is_fraud=True)))
        .order_by('-total')
    )

    # Only load 5 most recent alerts — no full table scan
    recent_alerts = _user_alerts(request.user).order_by('-created_at')[:5]

    context = {
        'total_transactions': total,
        'fraud_count':        fraud_count,
        'fraud_rate':         fraud_rate,
        'avg_fraud_score':    round(avg_score * 100, 1),
        'by_type':            by_type,
        'recent_alerts':      recent_alerts,
    }
    return render(request, 'dashboard/home.html', context)


@login_required
def transactions(request):
    qs = _user_transactions(request.user).select_related('uploaded_by')

    fraud_filter = request.GET.get('fraud', 'all')
    txn_type     = request.GET.get('type', '')
    page         = max(int(request.GET.get('page', 1)), 1)
    per_page     = 200
    offset       = (page - 1) * per_page

    if fraud_filter == 'fraud':
        qs = qs.filter(is_fraud=True)
    elif fraud_filter == 'clean':
        qs = qs.filter(is_fraud=False)
    if txn_type:
        qs = qs.filter(transaction_type=txn_type)

    total_count = qs.count()
    total_pages = max((total_count + per_page - 1) // per_page, 1)
    page_txns   = qs.order_by('-fraud_probability', '-created_at')[offset: offset + per_page]

    return render(request, 'dashboard/transactions.html', {
        'transactions': page_txns,
        'fraud_filter': fraud_filter,
        'txn_type':     txn_type,
        'page':         page,
        'total_pages':  total_pages,
        'total_count':  total_count,
        'has_prev':     page > 1,
        'has_next':     page < total_pages,
    })


@login_required
def fraud_alerts(request):
    qs       = _user_alerts(request.user)
    severity = request.GET.get('severity', 'all')
    page     = max(int(request.GET.get('page', 1)), 1)
    per_page = 50
    offset   = (page - 1) * per_page

    if severity != 'all':
        qs = qs.filter(severity=severity)

    total_count = qs.count()
    total_pages = max((total_count + per_page - 1) // per_page, 1)
    page_alerts = qs.order_by('-created_at')[offset: offset + per_page]

    return render(request, 'dashboard/fraud_alerts.html', {
        'alerts':       page_alerts,
        'severity':     severity,
        'page':         page,
        'total_pages':  total_pages,
        'total_count':  total_count,
        'has_prev':     page > 1,
        'has_next':     page < total_pages,
    })
