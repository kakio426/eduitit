from django.urls import path
from . import views

urlpatterns = [
    path('', views.product_list, name='product_list'),
    path('<int:pk>/', views.product_detail, name='product_detail'),
    path('preview/<int:pk>/', views.product_preview, name='product_preview'),
    path('yut/', views.yut_game, name='yut_game'),
]
