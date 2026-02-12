from django.db import models
from django.dispatch import receiver
from django.db.models.signals import post_delete, pre_save
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

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
