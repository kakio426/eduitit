from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.urls import reverse
from django.http import HttpResponseBadRequest, HttpResponse, HttpResponseForbidden
from products.models import Product
from .models import TextbookMaterial, AiUsage

SERVICE_ROUTE = 'textbooks:main'
SERVICE_TITLE = '교육 자료실'

def _get_service(request):
    """Product 캐싱 및 반환"""
    service = (
        Product.objects.filter(launch_route_name=SERVICE_ROUTE).first()
        or Product.objects.filter(title=SERVICE_TITLE).first()
    )
    is_premium = request.user.is_authenticated and request.user.owned_products.filter(product=service).exists()
    return service, is_premium

@login_required
def main_view(request):
    """
    교사 대시보드 메인 뷰.
    새로운 자료 세션을 생성하거나 이전 자료들을 볼 수 있습니다.
    """
    service, is_premium = _get_service(request)
    materials = TextbookMaterial.objects.filter(teacher=request.user)

    context = {
        'service': service,
        'title': service.title if service else SERVICE_TITLE,
        'is_premium': is_premium,
        'materials': materials,
        'ai_usage': AiUsage.get_todays_usage(request.user),
    }
    return render(request, 'textbooks/main.html', context)

@login_required
def generate_material(request):
    """
    자료 생성/편집 화면 (HTMX 또는 일반 폼)
    """
    if request.method == "POST":
        subject = request.POST.get("subject")
        grade = request.POST.get("grade")
        unit_title = request.POST.get("unit_title")
        content = request.POST.get("content", "")
        
        if not subject or not unit_title:
             return HttpResponseBadRequest("과목과 단원명은 필수입니다.")
        
        # 새로운 세션 생성
        material = TextbookMaterial.objects.create(
            teacher=request.user,
            subject=subject,
            grade=grade,
            unit_title=unit_title,
            title=f"{unit_title} 수업 자료",
            content=content,
        )
        
        # HX-Request 이면 partial 영역 갱신, 아니면 디테일 페이지로 리다이렉트
        if request.headers.get('HX-Request') == 'true':
            return render(request, 'textbooks/partials/material_detail.html', {'material': material})
        
        return redirect('textbooks:detail', pk=material.id)

    # GET 요청 시 폼 렌더링
    return render(request, 'textbooks/partials/generate_form.html')

@login_required
def material_detail(request, pk):
    """
    개별 자료 세션 상세 및 배포 관리
    """
    service, is_premium = _get_service(request)
    material = get_object_or_404(TextbookMaterial, id=pk, teacher=request.user)
    
    # 퍼블리시 및 공유 핸들링
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "publish":
            material.is_published = True
            material.save()
        elif action == "unpublish":
            material.is_published = False
            material.save()
        elif action == "share":
            material.is_shared = True
            material.save()
        elif action == "unshare":
            material.is_shared = False
            material.save()
        elif action == "delete":
            material.delete()
            return redirect('textbooks:main')
            
        if request.headers.get('HX-Request') == 'true':
             return render(request, 'textbooks/partials/material_actions.html', {'material': material})
        return redirect('textbooks:detail', pk=material.id)

    context = {
        'service': service,
        'title': service.title if service else SERVICE_TITLE,
        'is_premium': is_premium,
        'material': material,
        'student_url': request.build_absolute_uri(reverse('textbooks:student_view', args=[material.id]))
    }
    return render(request, 'textbooks/detail.html', context)


def student_view(request, pk):
    """
    학생 화면 (Guest Flow)
    로그인 없이 세션 ID(UUID)만으로 접근
    """
    material = get_object_or_404(TextbookMaterial, id=pk)
    
    if not material.is_published:
        # 비공개 상태일 때 처리
        return HttpResponseForbidden("현재 열람이 중지된 자료입니다. 선생님께 문의하세요.")
        
    context = {
        'material': material,
    }
    return render(request, 'textbooks/student_view.html', context)


def raw_content(request, pk):
    """
    학생 화면 iframe에서 사용하는 원본 HTML 제공 뷰
    """
    material = get_object_or_404(TextbookMaterial, id=pk)
    
    # 교사는 자신의 자료를 볼 수 있고, 학생은 published 상태여야 볼 수 있음
    if not material.is_published and not (request.user.is_authenticated and material.teacher == request.user):
        return HttpResponseForbidden("현재 열람이 중지된 자료입니다.")
        
    return HttpResponse(material.content)

@login_required
def shared_library(request):
    """
    다른 교사들이 공유한 교육 자료실 게시판
    """
    service, is_premium = _get_service(request)
    subject_filter = request.GET.get('subject', '')
    
    materials = TextbookMaterial.objects.filter(is_shared=True)
    if subject_filter:
        materials = materials.filter(subject=subject_filter)
        
    context = {
        'service': service,
        'title': '공유 자료실',
        'is_premium': is_premium,
        'materials': materials.order_by('-created_at'),
        'current_subject': subject_filter,
        'subjects': TextbookMaterial.SUBJECT_CHOICES,
    }
    return render(request, 'textbooks/shared_library.html', context)

@login_required
def toggle_like(request, pk):
    """
    자료 추천 토글 (HTMX)
    """
    material = get_object_or_404(TextbookMaterial, id=pk, is_shared=True)
    if request.user in material.likes.all():
        material.likes.remove(request.user)
    else:
        material.likes.add(request.user)
        
    return render(request, 'textbooks/partials/like_button.html', {'material': material})


@login_required
@require_POST
def fork_material(request, pk):
    """지정된 공유 자료를 내 자료실로 복사해옵니다."""
    original_m = get_object_or_404(TextbookMaterial, id=pk)
    
    # 내 자료로 새로 복사 (pk 날리고 save하면 새로 생성됨)
    forked_m = TextbookMaterial.objects.create(
        teacher=request.user,
        subject=original_m.subject,
        grade=original_m.grade,
        unit_title=original_m.unit_title,
        title=f"[복사본] {original_m.title}",
        content=original_m.content,
        is_published=False,  # 일단 비공개(미배포) 상태로 복구
        is_shared=True       # 자동 공유 정책에 따름
    )
    
    return redirect('textbooks:detail', pk=forked_m.id)

