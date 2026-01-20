from django.urls import path
from . import views

urlpatterns = [
    path('insights/', views.insight_list, name='insight_list'),
]
