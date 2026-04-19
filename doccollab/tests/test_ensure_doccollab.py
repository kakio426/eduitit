from django.core.management import call_command
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from django.test import TestCase

from doccollab.services import DOC_GROUP_NAME, create_room_from_upload
from products.models import Product, ServiceManual
from version_manager.models import Document, DocumentGroup

User = get_user_model()


class EnsureDoccollabCommandTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="doc-owner", password="pw123456")

    def test_command_creates_product_manual_and_features(self):
        call_command("ensure_doccollab")

        product = Product.objects.get(title="잇티한글")
        manual = ServiceManual.objects.get(product=product)

        self.assertEqual(product.launch_route_name, "doccollab:main")
        self.assertEqual(product.service_type, "work")
        self.assertTrue(product.is_active)
        self.assertIn("온라인에서 바로 고칩니다", product.lead_text)
        self.assertTrue(manual.is_published)
        self.assertEqual(manual.title, "잇티한글 사용 가이드")
        self.assertIn("온라인에서 수정", manual.description)
        self.assertCountEqual(
            list(product.features.values_list("title", flat=True)),
            ["파일 열기", "온라인 수정", "저장과 배포본"],
        )
        self.assertCountEqual(
            list(manual.sections.values_list("title", flat=True)),
            ["열기", "수정", "저장"],
        )

    def test_command_renames_legacy_document_group_when_new_group_is_missing(self):
        legacy_group = DocumentGroup.objects.create(name="함께문서실")

        call_command("ensure_doccollab")

        legacy_group.refresh_from_db()
        self.assertEqual(legacy_group.name, DOC_GROUP_NAME)
        self.assertTrue(DocumentGroup.objects.filter(name=DOC_GROUP_NAME).exists())

    def test_command_merges_legacy_document_group_and_renames_conflicts(self):
        legacy_group = DocumentGroup.objects.create(name="함께문서실")
        room, _revision = create_room_from_upload(
            user=self.owner,
            title="기존 문서",
            uploaded_file=SimpleUploadedFile("legacy.hwpx", b"legacy bytes", content_type="application/octet-stream"),
        )
        current_group = DocumentGroup.objects.get(name=DOC_GROUP_NAME)
        current_doc = Document.objects.create(group=current_group, base_name="가정통신문")
        legacy_doc = room.mirrored_document
        legacy_doc.base_name = "가정통신문"
        legacy_doc.group = legacy_group
        legacy_doc.save(update_fields=["base_name", "group"])

        call_command("ensure_doccollab")

        current_doc.refresh_from_db()
        legacy_doc.refresh_from_db()
        self.assertEqual(current_doc.group, current_group)
        self.assertEqual(legacy_doc.group, current_group)
        self.assertEqual(legacy_doc.base_name, "가정통신문 (2)")
        self.assertFalse(DocumentGroup.objects.filter(name="함께문서실").exists())
