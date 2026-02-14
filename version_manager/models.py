from pathlib import Path
import secrets

from django.conf import settings
from django.db import models
from django.core.files.storage import default_storage
from django.utils import timezone
from django.utils.text import slugify


def _normalize_base_name(value: str) -> str:
    normalized = slugify(value).replace('-', '_')
    return normalized or 'document'


def _normalize_path_slug(value: str, fallback: str) -> str:
    slug = slugify(value)
    return slug or fallback


def document_version_upload_to(instance: "DocumentVersion", filename: str) -> str:
    today = timezone.localdate()
    ext = Path(filename).suffix.lower()
    doc_base = _normalize_base_name(instance.document.base_name)
    group_slug = _normalize_path_slug(instance.document.group.slug, 'group')
    version_token = f"v{instance.version:02d}"
    stored_name = f"{today:%Y-%m-%d}_{doc_base}_{version_token}{ext}"
    return f"documents/{group_slug}/{today:%Y}/{today:%m}/{stored_name}"


def get_raw_storage():
    if getattr(settings, 'USE_CLOUDINARY', False):
        try:
            from cloudinary_storage.storage import RawMediaCloudinaryStorage
            return RawMediaCloudinaryStorage()
        except (ImportError, Exception):
            return default_storage
    return default_storage


class DocumentGroup(models.Model):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True, blank=True)

    class Meta:
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name, allow_unicode=True) or 'group'
            candidate = base_slug
            index = 1
            while DocumentGroup.objects.exclude(pk=self.pk).filter(slug=candidate).exists():
                index += 1
                candidate = f"{base_slug}-{index}"
            self.slug = candidate
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Document(models.Model):
    base_name = models.CharField(max_length=200)
    group = models.ForeignKey(DocumentGroup, on_delete=models.PROTECT, related_name='documents')
    published_version = models.ForeignKey(
        'DocumentVersion',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='published_for_documents',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        constraints = [
            models.UniqueConstraint(fields=['group', 'base_name'], name='uniq_document_group_name'),
        ]

    @property
    def latest_version(self):
        return self.versions.order_by('-version').first()

    def __str__(self):
        return self.base_name


class DocumentProtectedPhrase(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='protected_phrases')
    phrase = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_protected_phrases',
    )

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['document', 'phrase'], name='uniq_document_protected_phrase'),
        ]

    def __str__(self):
        return f"{self.document.base_name} - {self.phrase}"


class DocumentShareLink(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='share_links')
    token = models.CharField(max_length=64, unique=True, editable=False)
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_document_share_links',
    )

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_urlsafe(24)
        super().save(*args, **kwargs)

    def is_valid(self):
        if not self.is_active:
            return False
        if self.expires_at and self.expires_at <= timezone.now():
            return False
        return True

    def __str__(self):
        return f"{self.document.base_name} share link"


class DocumentVersion(models.Model):
    STATUS_DRAFT = 'draft'
    STATUS_REVIEW = 'review'
    STATUS_PUBLISHED = 'published'
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_REVIEW, 'Review'),
        (STATUS_PUBLISHED, 'Published'),
    ]

    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='versions')
    version = models.PositiveIntegerField()
    upload = models.FileField(upload_to=document_version_upload_to, storage=get_raw_storage)
    original_filename = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    uploaded_by_name = models.CharField(max_length=80, blank=True)
    extracted_text = models.TextField(blank=True)
    diff_summary = models.TextField(blank=True)
    diff_supported = models.BooleanField(default=False)
    diff_error = models.CharField(max_length=255, blank=True)
    missing_protected_phrases = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='uploaded_document_versions',
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ['-version']
        constraints = [
            models.UniqueConstraint(fields=['document', 'version'], name='uniq_document_version_number'),
        ]

    def save(self, *args, **kwargs):
        if self.upload and not self.original_filename:
            self.original_filename = Path(self.upload.name).name
        if self.uploaded_by and not self.uploaded_by_name:
            self.uploaded_by_name = self.uploaded_by.get_username()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.document.base_name} v{self.version:02d}"
