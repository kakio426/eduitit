from django.urls import path
from . import views, oauth_views

app_name = 'classcalendar'

urlpatterns = [
    # Teacher views
    path('', views.main_view, name='main'),
    path('api/events/', views.api_events, name='api_events'),
    path('api/events/create/', views.api_create_event, name='api_create_event'),
    
    # OAuth routes
    path('oauth/login/', oauth_views.oauth_login, name='oauth_login'),
    path('oauth/callback/', oauth_views.oauth_callback, name='oauth_callback'),
    path('api/google/calendars/', oauth_views.api_google_calendars, name='api_google_calendars'),
    path('api/sync/', oauth_views.api_google_sync, name='api_google_sync'),
    path('api/export/<uuid:event_id>/', oauth_views.api_google_export, name='api_google_export'),
    path('api/disconnect/', oauth_views.api_google_disconnect, name='api_google_disconnect'),
    
    # Student views
    path('s/<str:slug>/', views.student_view, name='student_view'),
]
