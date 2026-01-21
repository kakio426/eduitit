from django.urls import path
from . import views

app_name = 'autoarticle'

urlpatterns = [
    path('', views.ArticleCreateView.as_view(), name='create'),
    path('archive/', views.ArticleArchiveView.as_view(), name='archive'),
    path('result/<int:pk>/', views.ArticleDetailView.as_view(), name='detail'),
    path('result/<int:pk>/cardnews/', views.ArticleCardNewsView.as_view(), name='cardnews'),
]
