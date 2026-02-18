from django.db import migrations
from django.db.models import Q


def remove_services(apps, schema_editor):
    Product = apps.get_model('products', 'Product')
    target_titles = [
        '궁금해? 패들릿 봇',
        '패들릿 봇',
        '학교폭력 사안 처리 비서',
        '학교폭력 상담 AI',
    ]
    (
        Product.objects.filter(
            Q(title__in=target_titles)
            | Q(title__icontains='패들릿')
            | Q(title__icontains='학교폭력')
        )
        .delete()
    )


class Migration(migrations.Migration):
    dependencies = [
        ('products', '0035_update_collect_solve_text'),
    ]

    operations = [
        migrations.RunPython(remove_services, migrations.RunPython.noop),
    ]

