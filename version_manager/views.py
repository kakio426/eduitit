from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.db import transaction
from django.db.models import Max
from django.http import FileResponse, Http404, HttpResponseForbidden
from django.urls import reverse
from django.utils import timezone
from django.shortcuts import get_object_or_404, redirect, render

from .models import Document, DocumentGroup, DocumentProtectedPhrase, DocumentShareLink, DocumentVersion
from .utils import extract_text_from_uploaded, make_diff_summary


@login_required
def document_list_view(request):
    query = (request.GET.get('q') or '').strip()
    group_id = (request.GET.get('group') or '').strip()
    recent = (request.GET.get('recent') or '').strip()

    documents = (
        Document.objects.select_related('group', 'published_version')
        .annotate(latest_uploaded_at=Max('versions__created_at'))
        .order_by('-latest_uploaded_at', '-updated_at')
    )
    groups = DocumentGroup.objects.all()

    if query:
        documents = documents.filter(Q(base_name__icontains=query) | Q(group__name__icontains=query))
    if group_id:
        documents = documents.filter(group_id=group_id)
    if recent in {'7', '30'}:
        since = timezone.now() - timezone.timedelta(days=int(recent))
        documents = documents.filter(updated_at__gte=since)

    return render(
        request,
        'version_manager/document_list.html',
        {'documents': documents, 'groups': groups, 'query': query, 'selected_group': group_id, 'selected_recent': recent},
    )


@login_required
def document_create_view(request):
    groups = DocumentGroup.objects.all()
    if request.method == 'POST':
        base_name = (request.POST.get('base_name') or '').strip()
        group_id = (request.POST.get('group_id') or '').strip()
        new_group_name = (request.POST.get('new_group_name') or '').strip()

        if not base_name:
            messages.error(request, '문서명을 입력해 주세요.')
            return render(request, 'version_manager/document_form.html', {'groups': groups})

        group = None
        if new_group_name:
            group, _ = DocumentGroup.objects.get_or_create(name=new_group_name)
        elif group_id:
            group = DocumentGroup.objects.filter(pk=group_id).first()

        if group is None:
            messages.error(request, '그룹을 선택하거나 새 그룹명을 입력해 주세요.')
            return render(request, 'version_manager/document_form.html', {'groups': groups})

        document, created = Document.objects.get_or_create(
            group=group,
            base_name=base_name,
        )
        if created:
            messages.success(request, '문서 패키지를 생성했습니다.')
        else:
            messages.info(request, '같은 이름의 문서 패키지가 이미 있어 상세 페이지로 이동합니다.')
        return redirect('version_manager:document_detail', document_id=document.id)

    return render(request, 'version_manager/document_form.html', {'groups': groups})


@login_required
def document_detail_view(request, document_id):
    document = get_object_or_404(
        Document.objects.select_related('group', 'published_version'),
        pk=document_id,
    )
    versions = document.versions.select_related('uploaded_by').all()
    latest_version = versions.first()
    phrases = document.protected_phrases.filter(is_active=True)
    share_links = document.share_links.all()
    link_items = []
    for share_link in share_links:
        link_items.append(
            {
                'id': share_link.id,
                'is_active': share_link.is_active,
                'created_at': share_link.created_at,
                'expires_at': share_link.expires_at,
                'is_valid': share_link.is_valid(),
                'url': request.build_absolute_uri(reverse('version_manager:shared_upload', kwargs={'token': share_link.token})),
            }
        )

    return render(
        request,
        'version_manager/document_detail.html',
        {
            'document': document,
            'versions': versions,
            'latest_version': latest_version,
            'published_version': document.published_version,
            'phrases': phrases,
            'share_links': link_items,
        },
    )


def _update_version_analysis(document: Document, version: DocumentVersion):
    current_text, current_status = extract_text_from_uploaded(version.upload)
    version.extracted_text = current_text or ''
    previous = (
        DocumentVersion.objects.filter(document=document)
        .exclude(pk=version.pk)
        .order_by('-version')
        .first()
    )
    previous_text = previous.extracted_text if previous else ''
    diff_summary, supported = make_diff_summary(previous_text, version.extracted_text)
    version.diff_summary = diff_summary
    version.diff_supported = supported
    version.diff_error = '' if supported else current_status

    active_phrases = list(document.protected_phrases.filter(is_active=True).values_list('phrase', flat=True))
    missing = []
    if active_phrases and version.extracted_text:
        for phrase in active_phrases:
            if phrase and phrase not in version.extracted_text:
                missing.append(phrase)
    version.missing_protected_phrases = missing
    version.save(
        update_fields=[
            'extracted_text',
            'diff_summary',
            'diff_supported',
            'diff_error',
            'missing_protected_phrases',
        ]
    )


@login_required
@transaction.atomic
def upload_version_view(request, document_id):
    if request.method != 'POST':
        return redirect('version_manager:document_detail', document_id=document_id)

    document = get_object_or_404(Document.objects.select_related('group'), pk=document_id)
    uploaded_file = request.FILES.get('file')
    if uploaded_file is None:
        messages.error(request, '업로드할 파일을 선택해 주세요.')
        return redirect('version_manager:document_detail', document_id=document_id)

    max_version = (
        DocumentVersion.objects.select_for_update()
        .filter(document=document)
        .aggregate(max_version=Max('version'))
        .get('max_version')
        or 0
    )
    next_version = max_version + 1

    version = DocumentVersion.objects.create(
        document=document,
        version=next_version,
        upload=uploaded_file,
        original_filename=uploaded_file.name,
        status=DocumentVersion.STATUS_DRAFT,
        uploaded_by=request.user,
        uploaded_by_name=request.user.get_username(),
    )
    _update_version_analysis(document, version)

    document.updated_at = version.created_at
    document.save(update_fields=['updated_at'])
    if version.missing_protected_phrases:
        messages.warning(request, f'v{version.version:02d} 업로드 완료. 보호 문구 {len(version.missing_protected_phrases)}건 누락 경고가 있습니다.')
    else:
        messages.success(request, f'v{version.version:02d} 버전이 업로드되었습니다.')
    return redirect('version_manager:document_detail', document_id=document.id)


@login_required
@transaction.atomic
def set_published_view(request, document_id, version_id):
    if request.method != 'POST':
        return redirect('version_manager:document_detail', document_id=document_id)
    if not request.user.is_staff:
        return HttpResponseForbidden('배포본 지정 권한이 없습니다.')

    document = get_object_or_404(Document, pk=document_id)
    version = get_object_or_404(DocumentVersion, pk=version_id, document=document)

    document.versions.filter(status=DocumentVersion.STATUS_PUBLISHED).exclude(pk=version.pk).update(
        status=DocumentVersion.STATUS_REVIEW
    )
    if version.status != DocumentVersion.STATUS_PUBLISHED:
        version.status = DocumentVersion.STATUS_PUBLISHED
        version.save(update_fields=['status'])

    document.published_version = version
    document.save(update_fields=['published_version', 'updated_at'])

    messages.success(request, f'v{version.version:02d}을 공식 배포본으로 지정했습니다.')
    return redirect('version_manager:document_detail', document_id=document.id)


def _download_response(version: DocumentVersion):
    if not version.upload:
        raise Http404('파일이 존재하지 않습니다.')
    try:
        handle = version.upload.open('rb')
    except FileNotFoundError as exc:
        raise Http404('파일을 찾을 수 없습니다.') from exc
    return FileResponse(handle, as_attachment=True, filename=Path(version.upload.name).name)


@login_required
def download_latest_view(request, document_id):
    document = get_object_or_404(Document, pk=document_id)
    version = document.versions.order_by('-version').first()
    if version is None:
        messages.error(request, '다운로드할 최신 버전이 없습니다.')
        return redirect('version_manager:document_detail', document_id=document.id)
    return _download_response(version)


@login_required
def download_published_view(request, document_id):
    document = get_object_or_404(Document.objects.select_related('published_version'), pk=document_id)
    version = document.published_version
    if version is None:
        messages.error(request, '배포본이 아직 지정되지 않았습니다.')
        return redirect('version_manager:document_detail', document_id=document.id)
    return _download_response(version)


@login_required
def download_version_view(request, document_id, version_id):
    document = get_object_or_404(Document, pk=document_id)
    version = get_object_or_404(DocumentVersion, pk=version_id, document=document)
    return _download_response(version)


@transaction.atomic
def delete_version_view(request, document_id, version_id):
    if request.method != 'POST':
        return redirect('version_manager:document_detail', document_id=document_id)

    document = get_object_or_404(Document, pk=document_id)
    version = get_object_or_404(DocumentVersion, pk=version_id, document=document)

    allowed = False
    redirect_to_shared = False

    if request.user.is_authenticated and (request.user.is_staff or version.uploaded_by_id == request.user.id):
        allowed = True
    else:
        token = (request.POST.get('share_token') or '').strip()
        if token:
            share_link = DocumentShareLink.objects.filter(token=token, document=document).first()
            if share_link and share_link.is_valid():
                session_key = f"vm_uploaded_versions_{token}"
                owned_ids = request.session.get(session_key, [])
                if version.id in owned_ids:
                    allowed = True
                    redirect_to_shared = True

    if not allowed:
        return HttpResponseForbidden('본인이 업로드한 버전만 삭제할 수 있습니다.')

    if document.published_version_id == version.id:
        document.published_version = None
        document.save(update_fields=['published_version'])

    if version.upload:
        version.upload.delete(save=False)
    version.delete()
    messages.success(request, '업로드한 버전을 삭제했습니다.')

    if redirect_to_shared:
        return redirect('version_manager:shared_upload', token=token)
    return redirect('version_manager:document_detail', document_id=document.id)


@login_required
@transaction.atomic
def add_protected_phrase_view(request, document_id):
    if request.method != 'POST':
        return redirect('version_manager:document_detail', document_id=document_id)

    document = get_object_or_404(Document, pk=document_id)
    phrase = (request.POST.get('phrase') or '').strip()
    if not phrase:
        messages.error(request, '보호 문구를 입력해 주세요.')
        return redirect('version_manager:document_detail', document_id=document_id)

    phrase_obj, created = DocumentProtectedPhrase.objects.get_or_create(
        document=document,
        phrase=phrase,
        defaults={'created_by': request.user, 'is_active': True},
    )
    if not created and not phrase_obj.is_active:
        phrase_obj.is_active = True
        phrase_obj.save(update_fields=['is_active'])
        messages.success(request, '비활성 보호 문구를 다시 활성화했습니다.')
    elif created:
        messages.success(request, '보호 문구를 등록했습니다.')
    else:
        messages.info(request, '이미 등록된 보호 문구입니다.')
    return redirect('version_manager:document_detail', document_id=document_id)


@login_required
@transaction.atomic
def remove_protected_phrase_view(request, document_id, phrase_id):
    if request.method != 'POST':
        return redirect('version_manager:document_detail', document_id=document_id)
    phrase = get_object_or_404(DocumentProtectedPhrase, pk=phrase_id, document_id=document_id)
    phrase.is_active = False
    phrase.save(update_fields=['is_active'])
    messages.success(request, '보호 문구를 비활성화했습니다.')
    return redirect('version_manager:document_detail', document_id=document_id)


@login_required
@transaction.atomic
def create_share_link_view(request, document_id):
    if request.method != 'POST':
        return redirect('version_manager:document_detail', document_id=document_id)
    document = get_object_or_404(Document, pk=document_id)
    link = DocumentShareLink.objects.create(document=document, created_by=request.user)
    messages.success(request, '공유 링크를 생성했습니다.')
    return redirect('version_manager:document_detail', document_id=document.id)


@login_required
@transaction.atomic
def toggle_share_link_view(request, document_id, link_id):
    if request.method != 'POST':
        return redirect('version_manager:document_detail', document_id=document_id)
    link = get_object_or_404(DocumentShareLink, pk=link_id, document_id=document_id)
    link.is_active = not link.is_active
    link.save(update_fields=['is_active'])
    messages.success(request, '공유 링크 상태를 변경했습니다.')
    return redirect('version_manager:document_detail', document_id=document_id)


@transaction.atomic
def shared_upload_view(request, token):
    share_link = get_object_or_404(DocumentShareLink.objects.select_related('document__group'), token=token)
    if not share_link.is_valid():
        return HttpResponseForbidden('만료되었거나 비활성화된 링크입니다.')

    document = share_link.document
    if request.method == 'POST':
        uploaded_file = request.FILES.get('file')
        uploader_name = (request.POST.get('uploader_name') or '').strip() or '공유업로더'
        if uploaded_file is None:
            messages.error(request, '업로드할 파일을 선택해 주세요.')
            return redirect('version_manager:shared_upload', token=token)

        max_version = (
            DocumentVersion.objects.select_for_update()
            .filter(document=document)
            .aggregate(max_version=Max('version'))
            .get('max_version')
            or 0
        )
        version = DocumentVersion.objects.create(
            document=document,
            version=max_version + 1,
            upload=uploaded_file,
            original_filename=uploaded_file.name,
            status=DocumentVersion.STATUS_DRAFT,
            uploaded_by_name=uploader_name,
        )
        _update_version_analysis(document, version)
        document.updated_at = version.created_at
        document.save(update_fields=['updated_at'])
        session_key = f"vm_uploaded_versions_{token}"
        owned_ids = request.session.get(session_key, [])
        owned_ids.append(version.id)
        request.session[session_key] = owned_ids
        if version.missing_protected_phrases:
            messages.warning(request, f'업로드 완료. 보호 문구 {len(version.missing_protected_phrases)}건 누락 경고가 있습니다.')
        else:
            messages.success(request, f'v{version.version:02d} 업로드 완료')
        return redirect('version_manager:shared_upload', token=token)

    return render(
        request,
        'version_manager/shared_upload.html',
        {
            'document': document,
            'share_link': share_link,
            'latest_version': document.versions.order_by('-version').first(),
        },
    )
