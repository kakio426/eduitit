from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver

from core.file_cleanup import cleanup_replaced_file, delete_field_file

from .models import TrainingSessionAttachment


@receiver(pre_save, sender=TrainingSessionAttachment)
def cleanup_replaced_training_attachment(sender, instance, **kwargs):
    cleanup_replaced_file(
        sender,
        instance,
        "file",
        reason="signatures.training_attachment.replace",
    )


@receiver(post_delete, sender=TrainingSessionAttachment)
def cleanup_training_attachment_on_delete(sender, instance, **kwargs):
    delete_field_file(
        instance.file,
        reason="signatures.training_attachment.delete",
    )
