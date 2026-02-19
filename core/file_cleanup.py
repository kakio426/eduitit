import logging

from django.db import transaction


logger = logging.getLogger(__name__)


def schedule_storage_delete(storage, name, *, reason=""):
    """Delete a storage object after transaction commit."""
    if not storage or not name:
        return

    def _delete():
        try:
            storage.delete(name)
        except Exception:
            logger.exception("[file-cleanup] delete failed reason=%s name=%s", reason, name)

    transaction.on_commit(_delete)


def delete_field_file(field_file, *, reason=""):
    """Schedule deletion for a Django FieldFile."""
    if not field_file:
        return
    name = getattr(field_file, "name", "") or ""
    storage = getattr(field_file, "storage", None)
    if not name or storage is None:
        return
    schedule_storage_delete(storage, name, reason=reason)


def cleanup_replaced_file(sender, instance, field_name, *, reason=""):
    """
    If a file field value changed on update, schedule deletion for old file.
    Call from pre_save signal.
    """
    if not getattr(instance, "pk", None):
        return

    previous = sender.objects.filter(pk=instance.pk).only(field_name).first()
    if not previous:
        return

    old_field = getattr(previous, field_name, None)
    new_field = getattr(instance, field_name, None)
    old_name = getattr(old_field, "name", "") or ""
    new_name = getattr(new_field, "name", "") or ""

    if old_name and old_name != new_name:
        delete_field_file(old_field, reason=reason)
