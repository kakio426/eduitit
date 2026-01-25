from django.urls import path
from . import views

app_name = 'insights'

urlpatterns = [
    path('insights/', views.insight_list, name='list'),
    path('insights/create/', views.insight_create, name='create'),
    path('insights/<int:pk>/', views.InsightDetailView.as_view(), name='detail'),
    path('insights/<int:pk>/edit/', views.insight_update, name='update'),
    path('insights/<int:pk>/like/', views.insight_like_toggle, name='like_toggle'),
]
