from django.urls import path

from . import views

app_name = 'qrgen'

urlpatterns = [
    path('', views.landing, name='landing'),
]

