from django.urls import path
from . import views

app_name = 'detection'

urlpatterns = [
    path('upload/',                views.upload,       name='upload'),
    path('results/<int:job_id>/',  views.results,      name='results'),
    path('progress/<int:job_id>/', views.job_progress, name='progress'),
    path('train-status/',          views.train_status, name='train_status'),
]
