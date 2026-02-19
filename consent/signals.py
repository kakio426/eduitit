from django.db import transaction
from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver

from core.file_cleanup import cleanup_replaced_file, delete_field_file

from .models import SignatureDocument, SignatureRecipient, SignatureRequest


@receiver(pre_save, sender=SignatureDocument)
def cleanup_replaced_original_file(sender, instance, **kwargs):
    cleanup_replaced_file(
        sender,
        instance,
        "original_file",
        reason="consent.signaturedocument.replace",
    )


@receiver(pre_save, sender=SignatureRequest)
def cleanup_replaced_merged_pdf(sender, instance, **kwargs):
    cleanup_replaced_file(
        sender,
        instance,
        "merged_pdf",
        reason="consent.signaturerequest.replace_merged_pdf",
    )


@receiver(pre_save, sender=SignatureRecipient)
def cleanup_replaced_signed_pdf(sender, instance, **kwargs):
    cleanup_replaced_file(
        sender,
        instance,
        "signed_pdf",
        reason="consent.signaturerecipient.replace_signed_pdf",
    )


@receiver(post_delete, sender=SignatureRecipient)
def cleanup_signed_pdf_on_delete(sender, instance, **kwargs):
    delete_field_file(
        instance.signed_pdf,
        reason="consent.signaturerecipient.delete",
    )


@receiver(post_delete, sender=SignatureRequest)
def cleanup_request_files_and_orphan_document(sender, instance, **kwargs):
    delete_field_file(
        instance.merged_pdf,
        reason="consent.signaturerequest.delete",
    )

    document_id = instance.document_id
    if not document_id:
        return

    def _delete_orphan_document():
        still_referenced = SignatureRequest.objects.filter(document_id=document_id).exists()
        if still_referenced:
            return
        doc = SignatureDocument.objects.filter(id=document_id).first()
        if doc:
            doc.delete()

    transaction.on_commit(_delete_orphan_document)


@receiver(post_delete, sender=SignatureDocument)
def cleanup_original_file_on_delete(sender, instance, **kwargs):
    delete_field_file(
        instance.original_file,
        reason="consent.signaturedocument.delete",
    )
