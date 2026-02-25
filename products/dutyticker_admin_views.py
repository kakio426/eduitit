from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from .models import DTStudent, DTRole, DTSettings, DTRoleAssignment

@login_required
def admin_dashboard(request):
    user = request.user
    students = DTStudent.objects.filter(user=user)
    roles = DTRole.objects.filter(user=user)
    settings, _ = DTSettings.objects.get_or_create(user=user)
    
    return render(request, 'products/dutyticker/admin_dashboard.html', {
        'students': students,
        'roles': roles,
        'settings': settings
    })


@login_required
@require_http_methods(["POST"])
def update_rotation_settings(request):
    settings, _ = DTSettings.objects.get_or_create(user=request.user)
    selected_mode = (request.POST.get("rotation_mode") or "").strip()
    valid_modes = {choice[0] for choice in DTSettings.ROTATION_MODE_CHOICES}

    if selected_mode in valid_modes:
        settings.rotation_mode = selected_mode
        settings.auto_rotation = selected_mode.startswith("auto_")
        if settings.auto_rotation:
            settings.rotation_frequency = "daily"
        else:
            settings.last_rotation_date = None
        settings.save(update_fields=["rotation_mode", "auto_rotation", "rotation_frequency", "last_rotation_date"])

    return redirect('dt_admin_dashboard')

@login_required
@require_http_methods(["POST"])
def add_student(request):
    names = request.POST.get('names', '').split(',')
    # Bulk add support (comma separated)
    current_count = DTStudent.objects.filter(user=request.user).count()
    
    new_students = []
    for name in names:
        name = name.strip()
        if name:
            current_count += 1
            new_students.append(DTStudent(user=request.user, name=name, number=current_count))
    
    if new_students:
        DTStudent.objects.bulk_create(new_students)
            
    return redirect('dt_admin_dashboard')

@login_required
def delete_student(request, pk):
    student = get_object_or_404(DTStudent, pk=pk, user=request.user)
    student.delete()
    return redirect('dt_admin_dashboard')

@login_required
@require_http_methods(["POST"])
def add_role(request):
    name = request.POST.get('name')
    time_slot = request.POST.get('time_slot')
    description = request.POST.get('description', '')
    
    if name and time_slot:
        role = DTRole.objects.create(
            user=request.user,
            name=name,
            time_slot=time_slot,
            description=description
        )
        # Auto-create assignment entry if needed
        DTRoleAssignment.objects.create(user=request.user, role=role)
        
    return redirect('dt_admin_dashboard')

@login_required
def delete_role(request, pk):
    role = get_object_or_404(DTRole, pk=pk, user=request.user)
    role.delete()
    return redirect('dt_admin_dashboard')


@login_required
def print_sheet(request):
    user = request.user
    roles = list(DTRole.objects.filter(user=user).order_by('time_slot', 'id'))
    assignments_qs = (
        DTRoleAssignment.objects
        .filter(user=user, role__in=roles)
        .select_related('role', 'student')
        .order_by('role_id', '-date', '-id')
    )

    assignment_by_role_id = {}
    for assignment in assignments_qs:
        if assignment.role_id not in assignment_by_role_id:
            assignment_by_role_id[assignment.role_id] = assignment

    rows = []
    for idx, role in enumerate(roles, start=1):
        assignment = assignment_by_role_id.get(role.id)
        rows.append({
            'index': idx,
            'role_name': role.name,
            'time_slot': role.time_slot or '-',
            'student_name': assignment.student.name if assignment and assignment.student else '미배정',
            'description': role.description or '-',
        })

    return render(request, 'products/dutyticker/print_sheet.html', {
        'rows': rows,
        'row_count': len(rows),
        'row_count_safe': max(len(rows), 1),
    })
