from django.db import migrations


TITLE_TO_ROUTE = {
    "Insight Library": "insights:list",
    "선생님 사주": "fortune:saju",
    "반짝반짝 우리반 알림판": "dutyticker",
    "왁자지껄 교실 윷놀이": "yut_game",
    "토닥토닥 선생님 운세": "fortune:saju",
    "가뿐하게 서명 톡": "signatures:list",
    "몽글몽글 미술 수업": "artclass:setup",
    "글솜씨 뚝딱! 소식지": "autoarticle:create",
    "동물 장기": "fairy_games:play_dobutsu",
    "커넥트 포": "fairy_games:play_cfour",
    "이솔레이션": "fairy_games:play_isolation",
    "아택스": "fairy_games:play_ataxx",
    "브레이크스루": "fairy_games:play_breakthrough",
    "AI 도구 가이드": "tool_guide",
    "AI 프롬프트 레시피": "prompt_lab",
}

INTERNAL_PATH_TITLES = tuple(TITLE_TO_ROUTE.keys())


def normalize_internal_launch_metadata(apps, schema_editor):
    Product = apps.get_model("products", "Product")

    for title, route_name in TITLE_TO_ROUTE.items():
        Product.objects.filter(title=title).update(launch_route_name=route_name)

    Product.objects.filter(
        title__in=INTERNAL_PATH_TITLES,
        external_url__startswith="/",
    ).update(external_url="")


class Migration(migrations.Migration):
    dependencies = [
        ("products", "0046_update_artclass_manual_for_gemini_mode"),
    ]

    operations = [
        migrations.RunPython(normalize_internal_launch_metadata, migrations.RunPython.noop),
    ]
