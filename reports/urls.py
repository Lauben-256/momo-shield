from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    path('', views.report_list, name='list'),
    path('<int:job_id>/export/', views.export_report, name='export'),
]
