from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from detection.models import DetectionJob
from dashboard.models import Transaction
from .utils import generate_pdf_report, generate_excel_report


@login_required
def report_list(request):
    jobs = DetectionJob.objects.filter(status='done').order_by('-created_at')
    return render(request, 'reports/report_detail.html', {'jobs': jobs})


@login_required
def export_report(request, job_id):
    job = get_object_or_404(DetectionJob, pk=job_id, status='done')
    transactions = job.transactions.all()
    fmt = request.GET.get('format', 'pdf')

    if fmt == 'excel':
        data = generate_excel_report(job, transactions)
        response = HttpResponse(
            data,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="momoshield_report_{job.pk}.xlsx"'
    else:
        data = generate_pdf_report(job, transactions)
        response = HttpResponse(data, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="momoshield_report_{job.pk}.pdf"'

    return response
