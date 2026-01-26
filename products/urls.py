from django.urls import path
from . import views
from . import dutyticker_api
from . import dutyticker_admin_views

urlpatterns = [
    path('', views.product_list, name='product_list'),
    path('<int:pk>/', views.product_detail, name='product_detail'),
    path('preview/<int:pk>/', views.product_preview, name='product_preview'),
    path('yut/', views.yut_game, name='yut_game'),
    
    # DutyTicker Main
    path('dutyticker/', views.dutyticker_view, name='dutyticker'),
    
    # DutyTicker API
    path('dutyticker/api/data/', dutyticker_api.get_dutyticker_data, name='dt_api_data'),
    path('dutyticker/api/assignment/<int:assignment_id>/toggle/', dutyticker_api.update_assignment_status, name='dt_api_toggle'),
    path('dutyticker/api/student/<int:student_id>/toggle_mission/', dutyticker_api.toggle_student_mission_status, name='dt_api_toggle_mission'),
    path('dutyticker/api/assign/', dutyticker_api.assign_role, name='dt_api_assign'),
    path('dutyticker/api/rotate/', dutyticker_api.rotation_trigger, name='dt_api_rotate'),
    path('dutyticker/api/broadcast/update/', dutyticker_api.update_broadcast_message, name='dt_api_broadcast_update'),
    path('dutyticker/api/mission/update/', dutyticker_api.update_mission, name='dt_api_mission_update'),
    path('dutyticker/api/reset/', dutyticker_api.reset_data, name='dt_api_reset'),

    # DutyTicker Admin (Dashboard)
    path('dutyticker/admin/', dutyticker_admin_views.admin_dashboard, name='dt_admin_dashboard'),
    path('dutyticker/admin/students/add/', dutyticker_admin_views.add_student, name='dt_admin_add_student'),
    path('dutyticker/admin/students/<int:pk>/delete/', dutyticker_admin_views.delete_student, name='dt_admin_delete_student'),
    path('dutyticker/admin/roles/add/', dutyticker_admin_views.add_role, name='dt_admin_add_role'),
    path('dutyticker/admin/roles/<int:pk>/delete/', dutyticker_admin_views.delete_role, name='dt_admin_delete_role'),
]
