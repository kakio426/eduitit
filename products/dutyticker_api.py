from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
import json
from .models import DTStudent, DTRole, DTRoleAssignment, DTSchedule, DTSettings
import datetime

def create_mockup_data(user):
    """Generates initial sample data for new users to demonstrate DutyTicker."""
    # 1. Sample Students
    student_names = ["김철수", "이영희", "박민수", "정지원", "최하늘", "강다니엘", "조유리", "한지민", "서태웅", "윤대협"]
    students = []
    for i, name in enumerate(student_names, 1):
        students.append(DTStudent.objects.create(user=user, name=name, number=i))
    
    # 2. Sample Roles
    roles_data = [
        {"name": "칠판 지우기", "time_slot": "쉬는시간", "description": "수업 후 칠판을 깨끗하게 정리합니다."},
        {"name": "우유 나르기", "time_slot": "아침시간", "description": "급식실에서 우유를 가져와 배부합니다."},
        {"name": "컴퓨터 끄기", "time_slot": "종례시간", "description": "교실 멀티미디어 기기 전원을 확인합니다."},
        {"name": "우리반 정리왕", "time_slot": "점심시간", "description": "식사 후 교실 바닥의 쓰레기를 줍습니다."},
        {"name": "식물 도우미", "time_slot": "아침시간", "description": "교실 창가 화분에 물을 줍니다."}
    ]
    roles = []
    for r in roles_data:
        role = DTRole.objects.create(user=user, **r)
        roles.append(role)
    
    # 3. Sample Assignments (Assign first 5 students to roles)
    for i in range(min(5, len(students))):
        DTRoleAssignment.objects.create(user=user, role=roles[i], student=students[i])
        
    # 4. Sample Schedule (Mon-Fri)
    subjects = ["국어", "수학", "사회", "과학", "영어", "체육", "미술", "음악"]
    for day in range(1, 6): # Mon to Fri
        for period in range(1, 5): # 4 periods per day
            DTSchedule.objects.create(
                user=user,
                day=day,
                period=period,
                subject=subjects[(day + period) % len(subjects)],
                start_time=datetime.time(9 + period - 1, 0),
                end_time=datetime.time(9 + period - 1, 40)
            )
    return True
def get_dutyticker_data(request):
    user = request.user
    
    # Ensure settings exist
    settings, created = DTSettings.objects.get_or_create(user=user)
    
    # Fetch Data
    students_qs = DTStudent.objects.filter(user=user, is_active=True)
    roles_qs = DTRole.objects.filter(user=user)
    
    # If no data, seed it once
    if not students_qs.exists() and not roles_qs.exists():
        create_mockup_data(user)
        students_qs = DTStudent.objects.filter(user=user, is_active=True)
        roles_qs = DTRole.objects.filter(user=user)

    students = list(students_qs.values('id', 'name', 'number', 'is_mission_completed'))
    roles = list(roles_qs.values('id', 'name', 'description', 'time_slot', 'icon', 'color'))
    
    # Get Assignments (Current state)
    assignments_qs = DTRoleAssignment.objects.filter(user=user).select_related('role', 'student')
    assignments = []
    for a in assignments_qs:
        assignments.append({
            'id': a.id,
            'role_id': a.role.id,
            'student_id': a.student.id if a.student else None,
            'student_name': a.student.name if a.student else "Unassigned",
            'is_completed': a.is_completed
        })
        
    # Get Schedule
    schedules = DTSchedule.objects.filter(user=user).order_by('day', 'period')
    weekly_schedule = {}
    for s in schedules:
        day = s.day
        if day not in weekly_schedule:
            weekly_schedule[day] = []
        weekly_schedule[day].append({
            'id': s.id,
            'name': s.subject, # JS expects 'name'
            'startTime': s.start_time.strftime("%H:%M"),
            'endTime': s.end_time.strftime("%H:%M"),
            'period': s.period
        })
        
    return JsonResponse({
        'students': students,
        'roles': roles,
        'assignments': assignments,
        'schedule': weekly_schedule,
        'settings': {
            'auto_rotation': settings.auto_rotation,
            'rotation_frequency': settings.rotation_frequency,
            'last_broadcast': settings.last_broadcast_message,
            'mission_title': settings.mission_title,
            'mission_desc': settings.mission_desc
        }
    })

@login_required
@require_http_methods(["POST"])
@csrf_exempt
def update_assignment_status(request, assignment_id):
    try:
        data = json.loads(request.body)
        status = data.get('is_completed')
        
        assignment = DTRoleAssignment.objects.get(id=assignment_id, user=request.user)
        assignment.is_completed = status
        assignment.save()
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@login_required
@require_http_methods(["POST"])
@csrf_exempt
def toggle_student_mission_status(request, student_id):
    """Toggles 'is_mission_completed' for a student (Generic Mission)"""
    try:
        student = DTStudent.objects.get(id=student_id, user=request.user)
        student.is_mission_completed = not student.is_mission_completed
        student.save()
        return JsonResponse({'success': True, 'is_completed': student.is_mission_completed})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@login_required
@require_http_methods(["POST"])
@csrf_exempt
def update_broadcast_message(request):
    """Updates persistent broadcast message"""
    try:
        data = json.loads(request.body)
        msg = data.get('message', '')
        
        settings, _ = DTSettings.objects.get_or_create(user=request.user)
        settings.last_broadcast_message = msg
        settings.save()
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@login_required
@require_http_methods(["POST"])
@csrf_exempt
def update_mission(request):
    """Updates mission title and description"""
    try:
        data = json.loads(request.body)
        title = data.get('title')
        desc = data.get('description')
        
        settings, _ = DTSettings.objects.get_or_create(user=request.user)
        if title is not None: settings.mission_title = title
        if desc is not None: settings.mission_desc = desc
        settings.save()
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@login_required
@require_http_methods(["POST"])
@csrf_exempt
def assign_role(request):
    # Manually assign start/student to role
    try:
        data = json.loads(request.body)
        role_id = data.get('role_id')
        student_id = data.get('student_id')
        
        role = DTRole.objects.get(id=role_id, user=request.user)
        if student_id:
            student = DTStudent.objects.get(id=student_id, user=request.user)
        else:
            student = None
            
        # Update or Create Assignment
        assignment, created = DTRoleAssignment.objects.get_or_create(
            user=request.user, 
            role=role,
            defaults={'student': student}
        )
        if not created:
            assignment.student = student
            assignment.is_completed = False # Reset status on new assignment?
            assignment.save()
            
        return JsonResponse({'success': True, 'assignment_id': assignment.id})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@login_required
@require_http_methods(["POST"])
@csrf_exempt
def rotation_trigger(request):
    """
    Manually trigger rotation or used by automation
    Simple logic: Shift students by 1 for all roles?
    """
    user = request.user
    
    # Get all active students
    students = list(DTStudent.objects.filter(user=user, is_active=True).order_by('number'))
    if not students:
        return JsonResponse({'success': False, 'error': 'No students'})
        
    # Get all assignments
    assignments = list(DTRoleAssignment.objects.filter(user=user))
    
    # Simple Shift Logic
    student_ids = [s.id for s in students]
    total_students = len(student_ids)
    
    for assign in assignments:
        if assign.student:
            try:
                current_idx = student_ids.index(assign.student.id)
                next_idx = (current_idx + 1) % total_students
                assign.student = DTStudent.objects.get(id=student_ids[next_idx])
                assign.is_completed = False
                assign.save()
            except ValueError:
                pass
                
    return JsonResponse({'success': True, 'message': 'Rotated successfully'})

@login_required
@require_http_methods(["POST"])
@csrf_exempt
def reset_data(request):
    """Deletes all user data for DutyTicker and regenerates mockup."""
    user = request.user
    DTStudent.objects.filter(user=user).delete()
    DTRole.objects.filter(user=user).delete()
    DTSchedule.objects.filter(user=user).delete()
    DTRoleAssignment.objects.filter(user=user).delete()
    
    # Reset Settings too if likely
    settings, _ = DTSettings.objects.get_or_create(user=user)
    settings.last_broadcast_message = ""
    settings.save()
    
    create_mockup_data(user)
    return JsonResponse({'success': True, 'message': 'Data reset to mockup'})
