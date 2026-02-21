from django.db import migrations


NEW_TITLE = "한글문서 AI야 읽어줘"
OLD_TITLES = ("한글 문서 톡톡", "HWPX 문서 AI 대화")

NEW_MANUAL_TITLE = "한글문서 AI야 읽어줘 사용 가이드"
NEW_MANUAL_DESCRIPTION = "한글(HWPX) 파일 업로드부터 문서 기반 대화까지 빠르게 시작하는 방법입니다."


def rename_hwpxchat_service(apps, schema_editor):
    Product = apps.get_model("products", "Product")
    ProductFeature = apps.get_model("products", "ProductFeature")
    ServiceManual = apps.get_model("products", "ServiceManual")

    product = Product.objects.filter(title=NEW_TITLE).first()
    if not product:
        for old_title in OLD_TITLES:
            legacy_product = Product.objects.filter(title=old_title).first()
            if not legacy_product:
                continue

            legacy_product.title = NEW_TITLE
            update_fields = ["title"]
            if not legacy_product.launch_route_name:
                legacy_product.launch_route_name = "hwpxchat:main"
                update_fields.append("launch_route_name")
            legacy_product.save(update_fields=update_fields)
            product = legacy_product
            break

    if not product:
        product = Product.objects.filter(launch_route_name="hwpxchat:main").first()

    if not product:
        return

    feature_map = {
        "HWPX 직접 파싱": (
            "문서 그대로 읽기",
            "HWPX 내부 XML을 직접 읽어 문서 내용을 놓치지 않습니다.",
        ),
        "표 자동 Markdown 변환": (
            "표도 깔끔하게 이해",
            "표를 Markdown 형식으로 변환해 AI가 구조를 잘 이해하게 만듭니다.",
        ),
        "문서 기반 AI 대화": (
            "질문하면 바로 답변",
            "문서 근거 중심으로 Gemini/Claude가 답변을 제공합니다.",
        ),
    }
    for old_title, (new_title, new_desc) in feature_map.items():
        feature = ProductFeature.objects.filter(product=product, title=old_title).first()
        if feature:
            feature.title = new_title
            feature.description = new_desc
            feature.save(update_fields=["title", "description"])

    manual = ServiceManual.objects.filter(product=product).first()
    if manual:
        update_fields = []
        if manual.title != NEW_MANUAL_TITLE:
            manual.title = NEW_MANUAL_TITLE
            update_fields.append("title")
        if manual.description != NEW_MANUAL_DESCRIPTION:
            manual.description = NEW_MANUAL_DESCRIPTION
            update_fields.append("description")
        if not manual.is_published:
            manual.is_published = True
            update_fields.append("is_published")
        if update_fields:
            manual.save(update_fields=update_fields)


def revert_hwpxchat_service_title(apps, schema_editor):
    Product = apps.get_model("products", "Product")
    product = Product.objects.filter(title=NEW_TITLE).first()
    if product:
        product.title = "HWPX 문서 AI 대화"
        product.save(update_fields=["title"])


class Migration(migrations.Migration):
    dependencies = [
        ("products", "0042_add_hwpxchat_service"),
    ]

    operations = [
        migrations.RunPython(rename_hwpxchat_service, revert_hwpxchat_service_title),
    ]
