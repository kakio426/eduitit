from django.core.management.base import BaseCommand
from django.db import transaction

from doccollab.models import DocRoom
from doccollab.services import DOC_GROUP_NAME
from products.models import ManualSection, Product, ProductFeature, ServiceManual
from version_manager.models import Document, DocumentGroup


SERVICE_TITLE = "잇티한글"
LEGACY_SERVICE_TITLE = "함께문서실"
LAUNCH_ROUTE = "doccollab:main"
MANUAL_TITLE = "잇티한글 사용 가이드"
MANUAL_DESCRIPTION = "HWP 또는 HWPX를 열고 온라인에서 수정하고 HWP로 저장하는 빠른 시작입니다."


def _unique_document_base_name(group, desired_name, *, exclude_id=None):
    base = str(desired_name or "").strip()[:200] or "문서"
    candidate = base
    suffix = 2
    queryset = Document.objects.filter(group=group)
    if exclude_id is not None:
        queryset = queryset.exclude(id=exclude_id)
    while queryset.filter(base_name=candidate).exists():
        suffix_text = f" ({suffix})"
        candidate = f"{base[: max(1, 200 - len(suffix_text))]}{suffix_text}"
        suffix += 1
    return candidate


def ensure_document_group(stdout):
    current_group = DocumentGroup.objects.filter(name=DOC_GROUP_NAME).order_by("id").first()
    legacy_group = DocumentGroup.objects.filter(name=LEGACY_SERVICE_TITLE).order_by("id").first()

    if legacy_group and current_group is None:
        legacy_group.name = DOC_GROUP_NAME
        legacy_group.slug = ""
        legacy_group.save()
        stdout.write("[OK] Renamed legacy doccollab document group.")
        return legacy_group

    if current_group and legacy_group and current_group.id != legacy_group.id:
        mirrored_documents = (
            Document.objects.filter(group=legacy_group, doccollab_room__isnull=False)
            .select_related("group")
            .order_by("id")
        )
        for document in mirrored_documents:
            if Document.objects.filter(group=current_group, base_name=document.base_name).exclude(id=document.id).exists():
                document.base_name = _unique_document_base_name(current_group, document.base_name, exclude_id=document.id)
            document.group = current_group
            document.save(update_fields=["group", "base_name"])
        if not legacy_group.documents.exists():
            legacy_group.delete()
            stdout.write("[OK] Merged legacy doccollab document group.")
        return current_group

    if current_group is None:
        current_group = DocumentGroup.objects.create(name=DOC_GROUP_NAME)
        stdout.write("[OK] Created doccollab document group.")
    return current_group


class Command(BaseCommand):
    help = "Ensure doccollab product and manual exist in database"

    @transaction.atomic
    def handle(self, *args, **options):
        ensure_document_group(self.stdout)

        defaults = {
            "lead_text": "HWP와 HWPX 문서를 열고 온라인에서 바로 고칩니다.",
            "description": (
                "잇티한글은 HWP와 HWPX 문서를 데스크톱 Chrome에서 열어 바로 수정하고, "
                "필요할 때 공유하고, 저장본과 배포본을 관리하는 온라인 편집 공간입니다."
            ),
            "price": 0.00,
            "is_active": True,
            "is_featured": False,
            "is_guest_allowed": False,
            "icon": "📝",
            "color_theme": "green",
            "card_size": "small",
            "display_order": 25,
            "service_type": "work",
            "external_url": "",
            "launch_route_name": LAUNCH_ROUTE,
            "solve_text": "HWP를 바로 고칩니다",
            "result_text": "저장본과 배포본",
            "time_text": "5분 안팎",
        }
        product = Product.objects.filter(launch_route_name=LAUNCH_ROUTE).order_by("id").first()
        if product is None:
            product = Product.objects.create(title=SERVICE_TITLE, **defaults)
            self.stdout.write(self.style.SUCCESS("[OK] Created doccollab product."))
        else:
            changed = []
            if product.title != SERVICE_TITLE:
                product.title = SERVICE_TITLE
                changed.append("title")
            for field, value in defaults.items():
                if getattr(product, field) != value:
                    setattr(product, field, value)
                    changed.append(field)
            if changed:
                product.save(update_fields=changed)
                self.stdout.write(self.style.SUCCESS(f"[OK] Updated doccollab fields: {', '.join(changed)}"))

        Product.objects.filter(title__in={LEGACY_SERVICE_TITLE, "HWP 문서실"}).exclude(id=product.id).delete()

        features = [
            {
                "icon": "📂",
                "title": "파일 열기",
                "description": "HWP와 HWPX를 올리면 바로 편집 화면으로 들어갑니다.",
            },
            {
                "icon": "✍️",
                "title": "온라인 수정",
                "description": "데스크톱 Chrome에서 문서를 바로 고치고 필요할 때 공유합니다.",
            },
            {
                "icon": "💾",
                "title": "저장과 배포본",
                "description": "저장본을 HWP로 쌓고 필요한 시점에 배포본을 따로 지정합니다.",
            },
        ]
        feature_titles = {item["title"] for item in features}
        for item in features:
            feature, _created = ProductFeature.objects.get_or_create(
                product=product,
                title=item["title"],
                defaults={"icon": item["icon"], "description": item["description"]},
            )
            changed = []
            if feature.icon != item["icon"]:
                feature.icon = item["icon"]
                changed.append("icon")
            if feature.description != item["description"]:
                feature.description = item["description"]
                changed.append("description")
            if changed:
                feature.save(update_fields=changed)
        ProductFeature.objects.filter(product=product).exclude(title__in=feature_titles).delete()

        manual, _created = ServiceManual.objects.get_or_create(
            product=product,
            defaults={
                "title": MANUAL_TITLE,
                "description": MANUAL_DESCRIPTION,
                "is_published": True,
            },
        )
        manual_changed = []
        if manual.title != MANUAL_TITLE:
            manual.title = MANUAL_TITLE
            manual_changed.append("title")
        if manual.description != MANUAL_DESCRIPTION:
            manual.description = MANUAL_DESCRIPTION
            manual_changed.append("description")
        if not manual.is_published:
            manual.is_published = True
            manual_changed.append("is_published")
        if manual_changed:
            manual.save(update_fields=manual_changed)

        sections = [
            {
                "title": "열기",
                "content": "HWP 또는 HWPX 파일을 올리면 편집 화면이 바로 열립니다. 원본은 그대로 남고 저장본은 따로 쌓입니다.",
                "layout_type": "text_only",
                "display_order": 1,
                "badge_text": "Step 1",
            },
            {
                "title": "수정",
                "content": "데스크톱 Chrome에서 문서를 바로 고치고, 필요하면 다른 선생님과 공유합니다.",
                "layout_type": "text_only",
                "display_order": 2,
                "badge_text": "Step 2",
            },
            {
                "title": "저장",
                "content": "저장본을 HWP로 남기고, 필요한 시점에 배포본으로 지정해 내려받습니다.",
                "layout_type": "text_only",
                "display_order": 3,
                "badge_text": "Step 3",
            },
        ]
        section_titles = {item["title"] for item in sections}
        for item in sections:
            section, _created = ManualSection.objects.get_or_create(
                manual=manual,
                title=item["title"],
                defaults=item,
            )
            changed = []
            for field in ("content", "layout_type", "display_order", "badge_text"):
                if getattr(section, field) != item[field]:
                    setattr(section, field, item[field])
                    changed.append(field)
            if changed:
                section.save(update_fields=changed)
        manual.sections.exclude(title__in=section_titles).delete()

        for room in DocRoom.objects.select_related("mirrored_document__group").exclude(mirrored_document__isnull=True):
            document = room.mirrored_document
            if document and document.group.name == LEGACY_SERVICE_TITLE:
                target_group = DocumentGroup.objects.get(name=DOC_GROUP_NAME)
                if Document.objects.filter(group=target_group, base_name=document.base_name).exclude(id=document.id).exists():
                    document.base_name = _unique_document_base_name(target_group, document.base_name, exclude_id=document.id)
                document.group = target_group
                document.save(update_fields=["group", "base_name"])

        legacy_group = DocumentGroup.objects.filter(name=LEGACY_SERVICE_TITLE).first()
        if legacy_group and not legacy_group.documents.exists():
            legacy_group.delete()

        self.stdout.write(self.style.SUCCESS("[OK] doccollab service ensured."))
