from django.urls import path
from . import views

app_name = 'simulation'

urlpatterns = [
    path('',               views.monitor,        name='monitor'),
    path('start/',         views.start,          name='start'),
    path('stop/',          views.stop,           name='stop'),
    path('review/',        views.review_queue,   name='review_queue'),
    path('accounts/',      views.accounts,       name='accounts'),
    path('api/status/',    views.api_status,     name='api_status'),
]
