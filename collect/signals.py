from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver

from core.file_cleanup import cleanup_replaced_file, delete_field_file

from .models import CollectionRequest, Submission


@receiver(pre_save, sender=CollectionRequest)
def cleanup_replaced_template_file(sender, instance, **kwargs):
    cleanup_replaced_file(
        sender,
        instance,
        "template_file",
        reason="collect.collectionrequest.replace_template_file",
    )


@receiver(pre_save, sender=Submission)
def cleanup_replaced_submission_file(sender, instance, **kwargs):
    cleanup_replaced_file(
        sender,
        instance,
        "file",
        reason="collect.submission.replace_file",
    )


@receiver(post_delete, sender=CollectionRequest)
def cleanup_template_file_on_delete(sender, instance, **kwargs):
    delete_field_file(
        instance.template_file,
        reason="collect.collectionrequest.delete",
    )


@receiver(post_delete, sender=Submission)
def cleanup_submission_file_on_delete(sender, instance, **kwargs):
    delete_field_file(
        instance.file,
        reason="collect.submission.delete",
    )
