from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
import json
from .models import DTStudent, DTRole, DTRoleAssignment, DTSchedule, DTSettings

@login_required
def get_dutyticker_data(request):
    user = request.user
    
    # Ensure settings exist
    settings, created = DTSettings.objects.get_or_create(user=user)
    
    # Fetch Data
    students = list(DTStudent.objects.filter(user=user, is_active=True).values('id', 'name', 'number'))
    roles = list(DTRole.objects.filter(user=user).values('id', 'name', 'description', 'time_slot', 'icon', 'color'))
    
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
        
    # Get Schedule (Simple list for now, maybe filter by day later if needed, but JS handles filtering usually? 
    # Actually, JS expects 'todaySchedule'. Let's return all and filter in JS or filter here by today.)
    # Let's filter by today's weekday for efficiency? Or return full weekly structure?
    # Existing mock data structure was: { 1: [...], 2: [...] }
    # Let's return full weekly schedule so the frontend can handle day switching if needed?
    # Or just return today's. Let's return full structure relative to weekday.
    
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
            'rotation_frequency': settings.rotation_frequency
        }
    })

@login_required
@require_http_methods(["POST"])
@csrf_exempt # For simplicity in this context, but better to use CSRF token in JS
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
        # Logic: Find existing assignment for this role and update it
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
    Or shuffle?
    Let's implement a simple 'Shift' Logic.
    """
    user = request.user
    
    # Get all active students
    students = list(DTStudent.objects.filter(user=user, is_active=True).order_by('number'))
    if not students:
        return JsonResponse({'success': False, 'error': 'No students'})
        
    # Get all assignments
    assignments = list(DTRoleAssignment.objects.filter(user=user))
    
    # Simple Shift Logic: 
    # Current student index -> next index
    # We need to map current students to indices
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
                # Student might have been deleted or inactive?
                pass
                
    return JsonResponse({'success': True, 'message': 'Rotated successfully'})
