from django.db import migrations


TITLE_ROUTE_MAP = {
    "쌤BTI": "ssambti:main",
    "두뇌 풀가동! 교실 체스": "chess:index",
    "두뇌 풀가동! 교실 장기": "janggi:index",
    "우리반 캐릭터 친구 찾기": "studentmbti:landing",
    "AI 도구 가이드": "tool_guide",
    "AI 프롬프트 레시피": "prompt_lab",
    "간편 수합": "collect:landing",
    "교사 백과사전": "encyclopedia:landing",
    "학교 예약 시스템": "reservations:dashboard_landing",
    "최신본 센터": "version_manager:document_list",
    "최종최최종은 이제그만": "version_manager:document_list",
    "동의서는 나에게 맡겨": "consent:dashboard",
    "🐎 온라인 윷놀이": "yut_game",
    "DutyTicker": "dutyticker",
}


def backfill_launch_route_names(apps, schema_editor):
    Product = apps.get_model("products", "Product")
    for title, route_name in TITLE_ROUTE_MAP.items():
        Product.objects.filter(title=title, launch_route_name="").update(launch_route_name=route_name)


def rollback_launch_route_names(apps, schema_editor):
    Product = apps.get_model("products", "Product")
    Product.objects.filter(title__in=TITLE_ROUTE_MAP.keys(), launch_route_name__in=TITLE_ROUTE_MAP.values()).update(
        launch_route_name=""
    )


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0037_product_launch_route_name"),
    ]

    operations = [
        migrations.RunPython(backfill_launch_route_names, rollback_launch_route_names),
    ]
