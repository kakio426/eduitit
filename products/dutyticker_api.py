from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
import json
import datetime
import uuid
from .models import DTStudent, DTRole, DTRoleAssignment, DTSchedule, DTSettings

def get_guest_default_data():
    """Returns the structure for guest session data."""
    student_names = ["김철수", "이영희", "박민수", "정지원", "최하늘", "강다니엘", "조유리", "한지민", "서태웅", "윤대협"]
    students = []
    for i, name in enumerate(student_names, 1):
        students.append({'id': i, 'name': name, 'number': i, 'is_mission_completed': False})
    
    roles_data = [
        {"id": 1, "name": "칠판 지우기", "time_slot": "쉬는시간", "description": "수업 후 칠판을 깨끗하게 정리합니다.", "icon": "📋", "color": "bg-white"},
        {"id": 2, "name": "우유 나르기", "time_slot": "아침시간", "description": "급식실에서 우유를 가져와 배부합니다.", "icon": "📋", "color": "bg-white"},
        {"id": 3, "name": "컴퓨터 끄기", "time_slot": "종례시간", "description": "교실 멀티미디어 기기 전원을 확인합니다.", "icon": "📋", "color": "bg-white"},
        {"id": 4, "name": "우리반 정리왕", "time_slot": "점심시간", "description": "식사 후 교실 바닥의 쓰레기를 줍습니다.", "icon": "📋", "color": "bg-white"},
        {"id": 5, "name": "식물 도우미", "time_slot": "아침시간", "description": "교실 창가 화분에 물을 줍니다.", "icon": "📋", "color": "bg-white"}
    ]
    
    assignments = []
    for i in range(min(5, len(students))):
        assignments.append({
            'id': i + 1,
            'role_id': roles_data[i]['id'],
            'student_id': students[i]['id'],
            'student_name': students[i]['name'],
            'is_completed': False
        })
        
    subjects = ["국어", "수학", "사회", "과학", "영어", "체육", "미술", "음악"]
    weekly_schedule = {}
    for day in range(1, 6):
        weekly_schedule[str(day)] = []
        for period in range(1, 5):
            weekly_schedule[str(day)].append({
                'id': day * 10 + period,
                'name': subjects[(day + period) % len(subjects)],
                'startTime': f"{9 + period - 1:02d}:00",
                'endTime': f"{9 + period - 1:02d}:40",
                'period': period
            })
            
    return {
        'students': students,
        'roles': roles_data,
        'assignments': assignments,
        'schedule': weekly_schedule,
        'settings': {
            'auto_rotation': False,
            'rotation_frequency': 'daily',
            'last_broadcast': "환영합니다! 게스트 모드로 체험 중입니다.",
            'mission_title': "오늘도 행복한 우리 교실",
            'mission_desc': "선생님 말씀에 집중해 주세요."
        }
    }

def create_mockup_data(user):
    """Generates initial sample data for new users to demonstrate DutyTicker."""
    student_names = ["김철수", "이영희", "박민수", "정지원", "최하늘", "강다니엘", "조유리", "한지민", "서태웅", "윤대협"]
    students = []
    for i, name in enumerate(student_names, 1):
        students.append(DTStudent.objects.create(user=user, name=name, number=i))
    
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
    
    for i in range(min(5, len(students))):
        DTRoleAssignment.objects.create(user=user, role=roles[i], student=students[i])
        
    subjects = ["국어", "수학", "사회", "과학", "영어", "체육", "미술", "음악"]
    for day in range(1, 6):
        for period in range(1, 5):
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
    if not request.user.is_authenticated:
        if 'guest_dt_data' not in request.session:
            request.session['guest_dt_data'] = get_guest_default_data()
        return JsonResponse(request.session['guest_dt_data'])

    user = request.user
    settings, created = DTSettings.objects.get_or_create(user=user)
    
    students_qs = DTStudent.objects.filter(user=user, is_active=True)
    roles_qs = DTRole.objects.filter(user=user)
    
    if not students_qs.exists() and not roles_qs.exists():
        create_mockup_data(user)
        students_qs = DTStudent.objects.filter(user=user, is_active=True)
        roles_qs = DTRole.objects.filter(user=user)

    students = list(students_qs.values('id', 'name', 'number', 'is_mission_completed'))
    roles = list(roles_qs.values('id', 'name', 'description', 'time_slot', 'icon', 'color'))
    
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
        
    schedules = DTSchedule.objects.filter(user=user).order_by('day', 'period')
    weekly_schedule = {}
    for s in schedules:
        day = str(s.day)
        if day not in weekly_schedule:
            weekly_schedule[day] = []
        weekly_schedule[day].append({
            'id': s.id,
            'name': s.subject,
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

@require_http_methods(["POST"])
@csrf_exempt
def update_assignment_status(request, assignment_id):
    try:
        data = json.loads(request.body)
        status = data.get('is_completed')
        
        if not request.user.is_authenticated:
            guest_data = request.session.get('guest_dt_data')
            if guest_data:
                for a in guest_data['assignments']:
                    if a['id'] == assignment_id:
                        a['is_completed'] = status
                        request.session.modified = True
                        return JsonResponse({'success': True})
            return JsonResponse({'success': False, 'error': 'Guest data not found'}, status=400)

        assignment = DTRoleAssignment.objects.get(id=assignment_id, user=request.user)
        assignment.is_completed = status
        assignment.save()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@require_http_methods(["POST"])
@csrf_exempt
def toggle_student_mission_status(request, student_id):
    try:
        if not request.user.is_authenticated:
            guest_data = request.session.get('guest_dt_data')
            if guest_data:
                for s in guest_data['students']:
                    if s['id'] == student_id:
                        s['is_mission_completed'] = not s['is_mission_completed']
                        request.session.modified = True
                        return JsonResponse({'success': True, 'is_completed': s['is_mission_completed']})
            return JsonResponse({'success': False, 'error': 'Guest data not found'}, status=400)

        student = DTStudent.objects.get(id=student_id, user=request.user)
        student.is_mission_completed = not student.is_mission_completed
        student.save()
        return JsonResponse({'success': True, 'is_completed': student.is_mission_completed})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@require_http_methods(["POST"])
@csrf_exempt
def update_broadcast_message(request):
    try:
        data = json.loads(request.body)
        msg = data.get('message', '')
        
        if not request.user.is_authenticated:
            guest_data = request.session.get('guest_dt_data')
            if guest_data:
                guest_data['settings']['last_broadcast'] = msg
                request.session.modified = True
                return JsonResponse({'success': True})
            return JsonResponse({'success': False}, status=400)

        settings, _ = DTSettings.objects.get_or_create(user=request.user)
        settings.last_broadcast_message = msg
        settings.save()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@require_http_methods(["POST"])
@csrf_exempt
def update_mission(request):
    try:
        data = json.loads(request.body)
        title = data.get('title')
        desc = data.get('description')
        
        if not request.user.is_authenticated:
            guest_data = request.session.get('guest_dt_data')
            if guest_data:
                if title is not None: guest_data['settings']['mission_title'] = title
                if desc is not None: guest_data['settings']['mission_desc'] = desc
                request.session.modified = True
                return JsonResponse({'success': True})
            return JsonResponse({'success': False}, status=400)

        settings, _ = DTSettings.objects.get_or_create(user=request.user)
        if title is not None: settings.mission_title = title
        if desc is not None: settings.mission_desc = desc
        settings.save()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@require_http_methods(["POST"])
@csrf_exempt
def assign_role(request):
    try:
        data = json.loads(request.body)
        role_id = data.get('role_id')
        student_id = data.get('student_id')
        
        if not request.user.is_authenticated:
            guest_data = request.session.get('guest_dt_data')
            if guest_data:
                student_name = ""
                if student_id:
                    student_name = next((s['name'] for s in guest_data['students'] if s['id'] == student_id), "Unassigned")
                
                found = False
                for a in guest_data['assignments']:
                    if a['role_id'] == role_id:
                        a['student_id'] = student_id
                        a['student_name'] = student_name
                        a['is_completed'] = False
                        found = True
                        break
                if not found:
                    guest_data['assignments'].append({
                        'id': len(guest_data['assignments']) + 1,
                        'role_id': role_id,
                        'student_id': student_id,
                        'student_name': student_name,
                        'is_completed': False
                    })
                request.session.modified = True
                return JsonResponse({'success': True})
            return JsonResponse({'success': False}, status=400)

        role = DTRole.objects.get(id=role_id, user=request.user)
        student = DTStudent.objects.get(id=student_id, user=request.user) if student_id else None
        assignment, created = DTRoleAssignment.objects.get_or_create(user=request.user, role=role, defaults={'student': student})
        if not created:
            assignment.student = student
            assignment.is_completed = False
            assignment.save()
        return JsonResponse({'success': True, 'assignment_id': assignment.id})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@require_http_methods(["POST"])
@csrf_exempt
def rotation_trigger(request):
    if not request.user.is_authenticated:
        guest_data = request.session.get('guest_dt_data')
        if not guest_data or not guest_data['students']:
             return JsonResponse({'success': False, 'error': 'No data'})
        
        student_ids = [s['id'] for s in guest_data['students']]
        total = len(student_ids)
        for a in guest_data['assignments']:
            if a['student_id']:
                try:
                    curr_idx = student_ids.index(a['student_id'])
                    next_idx = (curr_idx + 1) % total
                    a['student_id'] = student_ids[next_idx]
                    a['student_name'] = guest_data['students'][next_idx]['name']
                    a['is_completed'] = False
                except ValueError: pass
        request.session.modified = True
        return JsonResponse({'success': True})

    user = request.user
    students = list(DTStudent.objects.filter(user=user, is_active=True).order_by('number'))
    if not students: return JsonResponse({'success': False, 'error': 'No students'})
    assignments = list(DTRoleAssignment.objects.filter(user=user).select_related('student'))
    student_ids = [s.id for s in students]
    student_map = {s.id: s for s in students}
    total_students = len(student_ids)
    
    updated_assignments = []
    for assign in assignments:
        if assign.student:
            try:
                current_idx = student_ids.index(assign.student.id)
                next_idx = (current_idx + 1) % total_students
                assign.student = student_map[student_ids[next_idx]]
                assign.is_completed = False
                updated_assignments.append(assign)
            except (ValueError, KeyError): pass
            
    if updated_assignments:
        DTRoleAssignment.objects.bulk_update(updated_assignments, ['student', 'is_completed'])
        
    return JsonResponse({'success': True, 'message': 'Rotated successfully'})

@require_http_methods(["POST"])
@csrf_exempt
def reset_data(request):
    if not request.user.is_authenticated:
        request.session['guest_dt_data'] = get_guest_default_data()
        return JsonResponse({'success': True, 'message': 'Guest data reset'})

    user = request.user
    DTStudent.objects.filter(user=user).delete()
    DTRole.objects.filter(user=user).delete()
    DTSchedule.objects.filter(user=user).delete()
    DTRoleAssignment.objects.filter(user=user).delete()
    settings, _ = DTSettings.objects.get_or_create(user=user)
    settings.last_broadcast_message = ""
    settings.save()
    create_mockup_data(user)
    return JsonResponse({'success': True, 'message': 'Data reset to mockup'})
