from django.urls import path
from . import views

app_name = 'tournament'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('stage/<slug:stage_slug>/', views.stage_detail, name='stage_detail'),
]
