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
def add_student(request):
    names = request.POST.get('names', '').split(',')
    # Bulk add support (comma separated)
    current_count = DTStudent.objects.filter(user=request.user).count()
    
    for name in names:
        name = name.strip()
        if name:
            current_count += 1
            DTStudent.objects.create(user=request.user, name=name, number=current_count)
            
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
