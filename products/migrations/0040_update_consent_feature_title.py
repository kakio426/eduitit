from django.db import migrations


def forwards(apps, schema_editor):
    Product = apps.get_model("products", "Product")
    ProductFeature = apps.get_model("products", "ProductFeature")
    product = Product.objects.filter(title="동의서는 나에게 맡겨").first()
    if not product:
        return

    old_title = "학부모 3단계 위저드"
    new_title = "학부모 동의 링크(확인→서명→완료)"
    old_desc = "본인확인 → 동의/비동의+손서명 → 완료"
    new_desc = "본인확인 → 동의/비동의 + 손서명 → 완료"

    feature = ProductFeature.objects.filter(product=product, title=old_title).first()
    if feature:
        feature.title = new_title
        feature.description = new_desc
        feature.save(update_fields=["title", "description"])
        return

    feature = ProductFeature.objects.filter(product=product, title=new_title).first()
    if feature:
        feature.description = new_desc
        feature.save(update_fields=["description"])
        return

    ProductFeature.objects.create(
        product=product,
        icon="fa-solid fa-mobile-screen-button",
        title=new_title,
        description=new_desc,
    )


def backwards(apps, schema_editor):
    Product = apps.get_model("products", "Product")
    ProductFeature = apps.get_model("products", "ProductFeature")
    product = Product.objects.filter(title="동의서는 나에게 맡겨").first()
    if not product:
        return

    old_title = "학부모 3단계 위저드"
    new_title = "학부모 동의 링크(확인→서명→완료)"
    old_desc = "본인확인 → 동의/비동의+손서명 → 완료"

    feature = ProductFeature.objects.filter(product=product, title=new_title).first()
    if feature:
        feature.title = old_title
        feature.description = old_desc
        feature.save(update_fields=["title", "description"])


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0039_backfill_happy_seed_launch_route"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
