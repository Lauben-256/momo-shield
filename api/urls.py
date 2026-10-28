from django.urls import path
from . import views

urlpatterns = [
    path('transactions/',           views.TransactionListAPI.as_view(), name='api-transactions'),
    path('alerts/',                 views.AlertListAPI.as_view(),        name='api-alerts'),
    path('stats/',                  views.stats_api,                     name='api-stats'),
    path('detect/upload/',          views.upload_api,                    name='api-upload'),
    path('detect/jobs/',            views.jobs_list_api,                 name='api-jobs-list'),
    path('detect/jobs/<int:job_id>/',          views.job_detail_api,    name='api-job-detail'),
    path('detect/jobs/<int:job_id>/progress/', views.job_progress_api,  name='api-job-progress'),
]
