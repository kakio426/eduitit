from django.db import migrations


NEW_TITLE = "선생님 사주"
LEGACY_TITLES = ("토닥토닥 선생님 운세", "교사 사주")
NEW_MANUAL_TITLE = "선생님 사주 이용방법"

OLD_CARD_COPY = {
    "solve_text": ("", "오늘의 운세를 가볍게 확인해요"),
    "result_text": ("", "운세 카드"),
    "time_text": ("", "1분"),
}
NEW_CARD_COPY = {
    "solve_text": "선생님 맞춤 사주를 확인해요",
    "result_text": "사주 분석 리포트",
    "time_text": "3분",
}


def _iter_target_products(Product):
    seen_ids = set()
    for title in (NEW_TITLE, *LEGACY_TITLES):
        for product in Product.objects.filter(title=title).order_by("id"):
            if product.id in seen_ids:
                continue
            seen_ids.add(product.id)
            yield product


def forward(apps, schema_editor):
    Product = apps.get_model("products", "Product")
    ServiceManual = apps.get_model("products", "ServiceManual")

    primary_product = Product.objects.filter(title=NEW_TITLE).order_by("id").first()
    for product in _iter_target_products(Product):
        update_fields = []

        if not primary_product:
            primary_product = product

        if product.id == primary_product.id:
            if product.title != NEW_TITLE:
                product.title = NEW_TITLE
                update_fields.append("title")
        else:
            if product.is_active:
                product.is_active = False
                update_fields.append("is_active")

        if product.launch_route_name != "fortune:saju":
            product.launch_route_name = "fortune:saju"
            update_fields.append("launch_route_name")
        if (product.external_url or "").startswith("/"):
            product.external_url = ""
            update_fields.append("external_url")

        if product.id == primary_product.id:
            for field, legacy_values in OLD_CARD_COPY.items():
                current_value = (getattr(product, field, "") or "").strip()
                if current_value in legacy_values:
                    setattr(product, field, NEW_CARD_COPY[field])
                    update_fields.append(field)

        if update_fields:
            product.save(update_fields=list(dict.fromkeys(update_fields)))

    if not primary_product:
        return

    manual = ServiceManual.objects.filter(product=primary_product).first()
    if manual:
        manual_update_fields = []
        if manual.title != NEW_MANUAL_TITLE:
            manual.title = NEW_MANUAL_TITLE
            manual_update_fields.append("title")
        if not manual.is_published:
            manual.is_published = True
            manual_update_fields.append("is_published")
        if manual_update_fields:
            manual.save(update_fields=manual_update_fields)


class Migration(migrations.Migration):
    dependencies = [
        ("products", "0060_dtsettings_tts_enabled_dtsettings_tts_minutes_before_and_more"),
    ]

    operations = [
        migrations.RunPython(forward, migrations.RunPython.noop),
    ]
