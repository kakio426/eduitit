from __future__ import annotations

from django.conf import settings
from django.core.files.storage import FileSystemStorage


def schoolprograms_document_storage():
    if not getattr(settings, "USE_CLOUDINARY", False):
        return FileSystemStorage()

    try:
        from cloudinary_storage.storage import RawMediaCloudinaryStorage

        return RawMediaCloudinaryStorage()
    except Exception:
        return FileSystemStorage()
