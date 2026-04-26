from django.urls import path
from . import views

app_name = 'tournament'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('matches/', views.matches_list, name='matches_list'),
    path('stage/<slug:stage_slug>/', views.stage_detail, name='stage_detail'),
    path('setup/migrate-db/', views.migrate_db_view, name='migrate_db'),
    path('setup/debug-error/', views.debug_error_view, name='debug_error'),
]
