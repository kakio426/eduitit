from django.urls import path
from . import views

app_name = 'insights'

urlpatterns = [
    path('insights/', views.insight_list, name='list'), # Changed name to list for consistency, keeping url
    path('insights/<int:pk>/', views.InsightDetailView.as_view(), name='detail'),
]
