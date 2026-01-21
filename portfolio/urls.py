from django.urls import path
from . import views

app_name = 'portfolio'

urlpatterns = [
    path('', views.PortfolioListView.as_view(), name='list'),
    path('inquiry/', views.InquiryCreateView.as_view(), name='inquiry'),
    path('inquiry/success/', views.InquirySuccessView.as_view(), name='inquiry_success'),
]
