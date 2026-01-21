from django.urls import path
from . import views

app_name = 'autoarticle'

urlpatterns = [
    path('', views.ArticleCreateView.as_view(), name='create'),
    path('result/<int:pk>/', views.ArticleDetailView.as_view(), name='detail'),
]
