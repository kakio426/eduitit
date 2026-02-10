from django.urls import path
from . import views

app_name = 'encyclopedia'

urlpatterns = [
    path('', views.landing, name='landing'),
    path('create/', views.entry_create, name='entry_create'),
    path('<int:pk>/edit/', views.entry_edit, name='entry_edit'),
    path('<int:pk>/delete/', views.entry_delete, name='entry_delete'),
]
