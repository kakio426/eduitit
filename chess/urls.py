from django.urls import path
from . import views

app_name = 'chess'

urlpatterns = [
    path('', views.index, name='index'),
    path('rules/', views.rules, name='rules'),
    path('play/', views.play, name='play'),
]
