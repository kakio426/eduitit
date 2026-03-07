from django.urls import path
from . import views
from . import views_ai

app_name = 'textbooks'

urlpatterns = [
    path('', views.main_view, name='main'),
    path('api/categorize/', views_ai.auto_categorize, name='api_categorize'),
    path('api/generate_prompt/', views_ai.generate_prompt, name='api_generate_prompt'),
    path('generate/', views.generate_material, name='generate'),
    path('shared/', views.shared_library, name='shared_library'),
    path('like/<uuid:pk>/', views.toggle_like, name='toggle_like'),
    path('<uuid:pk>/', views.material_detail, name='detail'),
    path('s/<uuid:pk>/', views.student_view, name='student_view'),
    path('s/<uuid:pk>/raw/', views.raw_content, name='raw_content'),
]
