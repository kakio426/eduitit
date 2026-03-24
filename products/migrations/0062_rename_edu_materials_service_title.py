from django.db import migrations


NEW_TITLE = "AI 수업자료 메이커"
LEGACY_TITLES = ("교육 자료실",)
LAUNCH_ROUTE = "edu_materials:main"
NEW_MANUAL_TITLE = "AI 수업자료 메이커 사용 가이드"


def _iter_target_products(Product):
    seen_ids = set()
    querysets = [
        Product.objects.filter(launch_route_name=LAUNCH_ROUTE).order_by("id"),
        Product.objects.filter(title=NEW_TITLE).order_by("id"),
        Product.objects.filter(title__in=LEGACY_TITLES).order_by("id"),
    ]
    for queryset in querysets:
        for product in queryset:
            if product.id in seen_ids:
                continue
            seen_ids.add(product.id)
            yield product


def forward(apps, schema_editor):
    Product = apps.get_model("products", "Product")
    ServiceManual = apps.get_model("products", "ServiceManual")

    primary_product = Product.objects.filter(launch_route_name=LAUNCH_ROUTE).order_by("id").first()
    if not primary_product:
        primary_product = Product.objects.filter(title=NEW_TITLE).order_by("id").first()
    if not primary_product:
        primary_product = Product.objects.filter(title__in=LEGACY_TITLES).order_by("id").first()

    for product in _iter_target_products(Product):
        update_fields = []

        if not primary_product:
            primary_product = product

        if product.id == primary_product.id:
            if product.title != NEW_TITLE:
                product.title = NEW_TITLE
                update_fields.append("title")
            if product.launch_route_name != LAUNCH_ROUTE:
                product.launch_route_name = LAUNCH_ROUTE
                update_fields.append("launch_route_name")
        else:
            if product.is_active:
                product.is_active = False
                update_fields.append("is_active")

        if update_fields:
            product.save(update_fields=list(dict.fromkeys(update_fields)))

    if not primary_product:
        return

    manual = ServiceManual.objects.filter(product=primary_product).first()
    if not manual:
        return

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
        ("products", "0061_standardize_fortune_service_title"),
    ]

    operations = [
        migrations.RunPython(forward, migrations.RunPython.noop),
    ]
