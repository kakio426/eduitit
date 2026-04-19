from django.db import migrations


PRODUCT_TITLE_MAP = (
    ("doccollab:main", "HWP 문서실", "잇티한글"),
    ("docsign:list", "인쇄 NONO 온라인 사인", "잇티PDF사인"),
    ("signatures:list", "가뿐하게 서명 톡", "잇티하게 서명 톡"),
    ("collect:landing", "간편 수합", "잇티수합"),
    ("reservations:dashboard_landing", "학교 예약 시스템", "잇티예약"),
    ("qrgen:landing", "수업 QR 생성기", "잇티QR"),
    ("infoboard:dashboard", "인포보드", "잇티보드"),
)

LEGACY_TITLE_GROUPS = {
    "doccollab:main": {"HWP 문서실", "함께문서실", "잇티한글"},
    "docsign:list": {"인쇄 NONO 온라인 사인", "잇티PDF사인"},
    "signatures:list": {"연수 서명 관리", "서명 수집", "가뿐하게 서명 톡", "잇티하게 서명 톡"},
    "collect:landing": {"간편 수합", "잇티수합"},
    "reservations:dashboard_landing": {"학교 예약 시스템", "잇티예약"},
    "qrgen:landing": {"수업 QR 생성기", "잇티QR"},
    "infoboard:dashboard": {"인포보드", "잇티보드"},
}


def _manual_title(old_title, new_title):
    if old_title == "인포보드":
        return "인포보드 사용법", "잇티보드 사용법"
    return f"{old_title} 사용 가이드", f"{new_title} 사용 가이드"


def rename_itit_service_titles(apps, schema_editor):
    Product = apps.get_model("products", "Product")
    ServiceManual = apps.get_model("products", "ServiceManual")

    for route_name, old_title, new_title in PRODUCT_TITLE_MAP:
        Product.objects.filter(launch_route_name=route_name).update(title=new_title)
        old_manual_title, new_manual_title = _manual_title(old_title, new_title)
        ServiceManual.objects.filter(product__launch_route_name=route_name).update(title=new_manual_title)
        ServiceManual.objects.filter(product__launch_route_name=route_name, title=old_manual_title).update(
            title=new_manual_title
        )
        canonical = Product.objects.filter(launch_route_name=route_name).order_by("id").first()
        if canonical is not None:
            Product.objects.filter(title__in=LEGACY_TITLE_GROUPS.get(route_name, set())).exclude(id=canonical.id).delete()


def revert_itit_service_titles(apps, schema_editor):
    Product = apps.get_model("products", "Product")
    ServiceManual = apps.get_model("products", "ServiceManual")

    for route_name, old_title, new_title in PRODUCT_TITLE_MAP:
        Product.objects.filter(launch_route_name=route_name).update(title=old_title)
        old_manual_title, new_manual_title = _manual_title(old_title, new_title)
        ServiceManual.objects.filter(product__launch_route_name=route_name).update(title=old_manual_title)
        ServiceManual.objects.filter(product__launch_route_name=route_name, title=new_manual_title).update(
            title=old_manual_title
        )


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0065_remove_legacy_workspace_service"),
    ]

    operations = [
        migrations.RunPython(rename_itit_service_titles, revert_itit_service_titles),
    ]
