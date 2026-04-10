from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.dispatch import receiver
from django.db.models.signals import post_delete, pre_save
from django.conf import settings
from django.db.models import Q
from django.utils import timezone
import logging

from .teacher_activity import ACTIVITY_CATEGORY_DAILY_LOGIN, award_teacher_activity

logger = logging.getLogger(__name__)
auth_logger = logging.getLogger("core.auth_security")

def should_cleanup():
    """Cloudinary 설정 여부 확인"""
    return getattr(settings, 'USE_CLOUDINARY', False)

@receiver(post_delete)
def delete_file_on_delete(sender, instance, **kwargs):
    """모델 삭제 시 관련 파일 삭제"""
    if not should_cleanup():
        return
    
    # FileField를 찾아 삭제
    for field in instance._meta.fields:
        if isinstance(field, models.FileField):
            file = getattr(instance, field.name)
            if file:
                try:
                    # storage.delete()는 실제 클라우드/로컬 저장소의 파일을 삭제함
                    file.storage.delete(file.name)
                    logger.info(f"[Cleanup] Deleted file {file.name} from storage on {sender.__name__} deletion.")
                except Exception as e:
                    logger.error(f"[Cleanup] Failed to delete file {file.name} on {sender.__name__} deletion: {e}")

    # GeneratedArticle.images (JSONField) 처리
    if sender.__name__ == 'GeneratedArticle' and hasattr(instance, 'images') and instance.images:
        try:
            import cloudinary.uploader
            for image_url in instance.images:
                if 'cloudinary.com' in image_url:
                    # URL에서 public_id 추출 시도 (간단하게)
                    # 예: https://res.cloudinary.com/cloud_name/image/upload/v12345/folder/public_id.jpg
                    # 실제로는 더 정교한 파싱이 필요할 수 있으나, 여기선 destroy 호출 시도
                    # public_id는 보통 'folder/public_id' 형태임
                    parts = image_url.split('/')
                    if 'upload' in parts:
                        idx = parts.index('upload')
                        # 'v12345/' 이후의 부분들을 합치고 확장자 제거
                        public_id_with_ext = '/'.join(parts[idx+2:])
                        public_id = public_id_with_ext.rsplit('.', 1)[0]
                        cloudinary.uploader.destroy(public_id)
                        logger.info(f"[Cleanup] Deleted Cloudinary image {public_id} from JSONField.")
        except Exception as e:
            logger.error(f"[Cleanup] Failed to cleanup JSONField images: {e}")

@receiver(pre_save)
def delete_file_on_change(sender, instance, **kwargs):
    """파일 필드 수정 시 이전 파일 삭제"""
    if not should_cleanup() or not instance.pk:
        return

    try:
        old_instance = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return

    for field in instance._meta.fields:
        if isinstance(field, models.FileField):
            old_file = getattr(old_instance, field.name)
            new_file = getattr(instance, field.name)
            
            if old_file and old_file.name and old_file != new_file:
                try:
                    old_file.storage.delete(old_file.name)
                    logger.info(f"[Cleanup] Deleted old file {old_file.name} from storage on {sender.__name__} update.")
                except Exception as e:
                    logger.error(f"[Cleanup] Failed to delete old file {old_file.name} on {sender.__name__} update: {e}")


def _client_ip(request):
    if request is None:
        return ""
    forwarded_for = (request.META.get("HTTP_X_FORWARDED_FOR") or "").strip()
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return (request.META.get("REMOTE_ADDR") or "").strip()


def _login_identifier(credentials):
    credentials = credentials or {}
    for key in ("login", "username", "email"):
        value = str(credentials.get(key) or "").strip()
        if value:
            return value
    return ""


def _looks_like_staff_login(identifier):
    if not identifier:
        return False
    User = get_user_model()
    return User.objects.filter(
        Q(username__iexact=identifier) | Q(email__iexact=identifier),
        is_staff=True,
    ).exists()


@receiver(user_logged_in)
def log_staff_login_success(sender, request, user, **kwargs):
    if not getattr(user, "is_staff", False):
        try:
            award_teacher_activity(
                user,
                category=ACTIVITY_CATEGORY_DAILY_LOGIN,
                source_key="login",
                occurred_at=timezone.now(),
                related_object_type="auth.login",
                related_object_id=str(getattr(user, "id", "")),
                metadata={"path": getattr(request, "path", "")},
            )
        except Exception:
            logger.exception(
                "teacher activity daily_login award failed user_id=%s path=%s",
                getattr(user, "id", ""),
                getattr(request, "path", ""),
            )
        return

    auth_logger.info(
        "staff login success username=%s user_id=%s ip=%s path=%s",
        getattr(user, "username", ""),
        getattr(user, "id", ""),
        _client_ip(request),
        getattr(request, "path", ""),
    )
    try:
        award_teacher_activity(
            user,
            category=ACTIVITY_CATEGORY_DAILY_LOGIN,
            source_key="login",
            occurred_at=timezone.now(),
            related_object_type="auth.login",
            related_object_id=str(getattr(user, "id", "")),
            metadata={"path": getattr(request, "path", "")},
        )
    except Exception:
        logger.exception(
            "teacher activity daily_login award failed user_id=%s path=%s",
            getattr(user, "id", ""),
            getattr(request, "path", ""),
        )


@receiver(user_login_failed)
def log_staff_login_failure(sender, credentials, request, **kwargs):
    identifier = _login_identifier(credentials)
    if not _looks_like_staff_login(identifier):
        return

    auth_logger.warning(
        "staff login failed identifier=%s ip=%s path=%s",
        identifier,
        _client_ip(request),
        getattr(request, "path", ""),
    )
