from django.urls import path
from . import views

app_name = 'artclass'

urlpatterns = [
    path('', views.setup_view, name='setup'),
    path('setup/<int:pk>/', views.setup_view, name='setup_edit'),
    path('classroom/<int:pk>/', views.classroom_view, name='classroom'),
    path('api/parse-gemini-steps/', views.parse_gemini_steps_api, name='parse_gemini_steps_api'),
    path('library/', views.library_view, name='library'),
]
