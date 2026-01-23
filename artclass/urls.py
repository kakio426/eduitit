from django.urls import path
from . import views

app_name = 'artclass'

urlpatterns = [
    path('', views.setup_view, name='setup'),
    path('room/', views.classroom_view, name='classroom'),
    path('api/generate/', views.generate_steps_api, name='generate_steps_api'),
]
