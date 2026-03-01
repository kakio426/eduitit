from django.urls import path
from . import views

app_name = 'reservations'

urlpatterns = [
    # Dashboard
    path('', views.dashboard_landing, name='root'),
    path('dashboard/', views.dashboard_landing, name='dashboard_landing'), # 학교 선택/생성
    path('<str:school_slug>/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    
    # HTMX Partial Views for Dashboard
    path('<str:school_slug>/settings/rooms/', views.room_settings, name='room_settings'),
    path('<str:school_slug>/settings/recurring/', views.recurring_settings, name='recurring_settings'),
    path('<str:school_slug>/settings/blackout/', views.blackout_settings, name='blackout_settings'),

    # Public Reservation Views
    path('go/<int:school_id>/', views.short_url_redirect, name='short_url'),
    path('<str:school_slug>/', views.reservation_index, name='reservation_index'),
    path('<str:school_slug>/create/', views.create_reservation, name='create_reservation'),
    path('<str:school_slug>/delete/<int:reservation_id>/', views.delete_reservation, name='delete_reservation'),
    path('<str:school_slug>/admin-delete/<int:reservation_id>/', views.admin_delete_reservation, name='admin_delete_reservation'),
    
    # Config Settings
    path('<str:school_slug>/settings/config/', views.update_config, name='update_config'),
    path('<str:school_slug>/delete-school/', views.delete_school, name='delete_school'),
]
