import json
import re

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from core.models import UserProfile
from edu_materials.models import EduMaterial
from products.models import ManualSection, Product, ProductFeature, ServiceManual


CURRICULUM_LAB_OWNER_USERNAME = "eduitit_curriculum_lab"
CURRICULUM_LAB_OWNER_NICKNAME = "에듀잇티 수업연구소"


CURRICULUM_LAB_SPECS = [
    {
        "title": "분모가 달라도 같은 크기 실험실",
        "subject": "MATH",
        "grade": "초등학교 3~4학년",
        "unit_title": "분수",
        "material_type": EduMaterial.MaterialType.EXPLORATION,
        "summary": "막대 길이를 직접 바꾸며 동치분수와 크기 비교를 확인합니다.",
        "tags": ["분수", "동치분수", "크기 비교", "수 감각", "2022개정"],
        "mode": "fraction",
        "question": "분모가 커지면 언제 조각 하나는 작아지고, 전체 크기는 그대로일까요?",
        "controls": [
            {"id": "a_num", "label": "위 분자", "min": 1, "max": 12, "value": 2},
            {"id": "a_den", "label": "위 분모", "min": 2, "max": 12, "value": 4},
            {"id": "b_num", "label": "아래 분자", "min": 1, "max": 12, "value": 3},
            {"id": "b_den", "label": "아래 분모", "min": 2, "max": 12, "value": 6},
        ],
    },
    {
        "title": "둘레와 넓이 분리판",
        "subject": "MATH",
        "grade": "초등학교 3~4학년",
        "unit_title": "도형의 측정",
        "material_type": EduMaterial.MaterialType.TOOL,
        "summary": "가로와 세로를 바꾸며 둘레와 넓이가 다르게 변하는 순간을 봅니다.",
        "tags": ["둘레", "넓이", "직사각형", "측정", "2022개정"],
        "mode": "area",
        "question": "넓이가 같아도 둘레가 달라지는 직사각형을 만들 수 있을까요?",
        "controls": [
            {"id": "width", "label": "가로 칸", "min": 1, "max": 10, "value": 5},
            {"id": "height", "label": "세로 칸", "min": 1, "max": 8, "value": 3},
        ],
    },
    {
        "title": "각도 감각 돌림판",
        "subject": "MATH",
        "grade": "초등학교 3~4학년",
        "unit_title": "각도",
        "material_type": EduMaterial.MaterialType.PRACTICE,
        "summary": "선을 돌리며 예각, 직각, 둔각의 경계를 직관적으로 익힙니다.",
        "tags": ["각도", "예각", "직각", "둔각", "2022개정"],
        "mode": "angle",
        "question": "89도와 91도는 눈으로 비슷해 보여도 왜 다른 이름으로 부를까요?",
        "controls": [
            {"id": "angle", "label": "각도", "min": 0, "max": 180, "value": 65},
        ],
    },
    {
        "title": "소수 자리값 줌 렌즈",
        "subject": "MATH",
        "grade": "초등학교 5~6학년",
        "unit_title": "소수의 계산",
        "material_type": EduMaterial.MaterialType.EXPLORATION,
        "summary": "소수 각 자리의 크기를 확대해 보며 자리값을 분리합니다.",
        "tags": ["소수", "자리값", "십분의 일", "백분의 일", "2022개정"],
        "mode": "decimal",
        "question": "0.4와 0.04는 숫자 4가 같아도 왜 크기가 다를까요?",
        "controls": [
            {"id": "ones", "label": "일의 자리", "min": 0, "max": 3, "value": 1},
            {"id": "tenths", "label": "소수 첫째 자리", "min": 0, "max": 9, "value": 4},
            {"id": "hundredths", "label": "소수 둘째 자리", "min": 0, "max": 9, "value": 6},
        ],
    },
    {
        "title": "직육면체 부피 큐브 쌓기",
        "subject": "MATH",
        "grade": "초등학교 5~6학년",
        "unit_title": "입체도형의 부피",
        "material_type": EduMaterial.MaterialType.TOOL,
        "summary": "가로, 세로, 높이를 조절해 단위 정육면체 개수를 확인합니다.",
        "tags": ["부피", "직육면체", "단위정육면체", "공간 감각", "2022개정"],
        "mode": "volume",
        "question": "바닥 한 층의 개수와 층수가 만나면 왜 부피가 될까요?",
        "controls": [
            {"id": "length", "label": "가로", "min": 1, "max": 6, "value": 4},
            {"id": "depth", "label": "세로", "min": 1, "max": 5, "value": 3},
            {"id": "height", "label": "높이", "min": 1, "max": 5, "value": 2},
        ],
    },
    {
        "title": "온도에 따른 물의 상태 변화",
        "subject": "SCIENCE",
        "grade": "초등학교 3~4학년",
        "unit_title": "물질의 상태",
        "material_type": EduMaterial.MaterialType.EXPLORATION,
        "summary": "온도 슬라이더로 얼음, 물, 수증기 입자의 움직임을 비교합니다.",
        "tags": ["상태 변화", "물", "온도", "입자 모형", "2022개정"],
        "mode": "state",
        "question": "모양이 바뀌어도 물질이 사라진 것이 아니라는 점을 어떻게 확인할까요?",
        "controls": [
            {"id": "temp", "label": "온도", "min": -20, "max": 120, "value": 20},
        ],
    },
    {
        "title": "그림자 길이 조절 실험",
        "subject": "SCIENCE",
        "grade": "초등학교 3~4학년",
        "unit_title": "빛과 그림자",
        "material_type": EduMaterial.MaterialType.EXPLORATION,
        "summary": "빛의 높이와 물체 높이를 움직이며 그림자 길이 변화를 봅니다.",
        "tags": ["빛", "그림자", "태양 고도", "관찰", "2022개정"],
        "mode": "shadow",
        "question": "빛이 낮게 비칠 때 그림자가 길어지는 까닭은 무엇일까요?",
        "controls": [
            {"id": "sun", "label": "빛의 높이", "min": 15, "max": 80, "value": 35},
            {"id": "object", "label": "물체 높이", "min": 40, "max": 130, "value": 90},
        ],
    },
    {
        "title": "자석 힘 방향 탐험대",
        "subject": "SCIENCE",
        "grade": "초등학교 3~4학년",
        "unit_title": "자석의 이용",
        "material_type": EduMaterial.MaterialType.GAME,
        "summary": "오른쪽 자석을 직접 끌고 극을 바꾸며 끌어당김과 밀어냄을 확인합니다.",
        "tags": ["자석", "극", "힘", "거리", "2022개정"],
        "mode": "magnet",
        "question": "같은 극과 다른 극은 왜 서로 다른 방향으로 힘을 줄까요?",
        "controls": [
            {"id": "distance", "label": "자석 사이 거리", "min": 30, "max": 300, "value": 120},
            {"id": "flip", "label": "오른쪽 왼쪽 끝 극", "min": 0, "max": 1, "value": 0},
        ],
    },
    {
        "title": "전기 회로 불 켜기",
        "subject": "SCIENCE",
        "grade": "초등학교 5~6학년",
        "unit_title": "전기의 이용",
        "material_type": EduMaterial.MaterialType.TOOL,
        "summary": "전지 수와 스위치 상태를 바꾸며 닫힌 회로 조건을 확인합니다.",
        "tags": ["전기 회로", "전지", "스위치", "전구", "2022개정"],
        "mode": "circuit",
        "question": "전구가 켜지려면 전기가 지나가는 길이 어떻게 이어져야 할까요?",
        "controls": [
            {"id": "cells", "label": "전지 수", "min": 1, "max": 3, "value": 1},
            {"id": "switch_on", "label": "스위치", "min": 0, "max": 1, "value": 1},
        ],
    },
    {
        "title": "연소 조건 삼각형",
        "subject": "SCIENCE",
        "grade": "초등학교 5~6학년",
        "unit_title": "연소와 소화",
        "material_type": EduMaterial.MaterialType.EXPLORATION,
        "summary": "산소, 탈 물질, 열 중 하나를 줄이면 불꽃이 어떻게 바뀌는지 봅니다.",
        "tags": ["연소", "소화", "산소", "열", "2022개정"],
        "mode": "combustion",
        "question": "불을 끄는 여러 방법은 결국 어떤 조건을 빼는 일일까요?",
        "controls": [
            {"id": "oxygen", "label": "산소", "min": 0, "max": 100, "value": 80},
            {"id": "fuel", "label": "탈 물질", "min": 0, "max": 100, "value": 85},
            {"id": "heat", "label": "열", "min": 0, "max": 100, "value": 90},
        ],
    },
]


class Command(BaseCommand):
    help = "Ensure edu_materials product and manual exist in database"

    PRODUCT_TITLE = "AI 수업자료 메이커"
    LEGACY_PRODUCT_TITLES = ("교육 자료실",)
    LAUNCH_ROUTE = "edu_materials:main"

    def handle(self, *args, **options):
        defaults = {
            "lead_text": "바이브코딩으로 만든 HTML 수업 자료를 붙여넣거나 파일로 올려 바로 실행합니다.",
            "description": (
                "AI 수업자료 메이커는 바이브코딩 툴에서 만든 HTML 수업 자료를 보관하고, 학생에게 QR과 링크로 바로 열어줄 수 있는 서비스입니다. "
                "교사용 미리보기와 학생 실행 화면을 분리하고, 실행 화면은 sandbox iframe으로 안전하게 분리해 수업 화면을 오염시키지 않습니다."
            ),
            "price": 0.00,
            "is_active": True,
            "is_featured": True,
            "is_guest_allowed": False,
            "icon": "🧩",
            "color_theme": "green",
            "card_size": "small",
            "display_order": 16,
            "service_type": "classroom",
            "external_url": "",
            "launch_route_name": self.LAUNCH_ROUTE,
            "solve_text": "바로 실행할 수 있는 HTML 수업 자료를 쓰고 싶어요",
            "result_text": "학생용 실행 링크와 QR",
            "time_text": "2분",
        }

        product = Product.objects.filter(launch_route_name=self.LAUNCH_ROUTE).order_by("id").first()
        if not product:
            product = Product.objects.filter(title__in=(self.PRODUCT_TITLE, *self.LEGACY_PRODUCT_TITLES)).order_by("id").first()

        if product is None:
            product = Product.objects.create(title=self.PRODUCT_TITLE, **defaults)
            self.stdout.write(self.style.SUCCESS("[ensure_edu_materials] Product created"))
        else:
            changed_fields = []
            for field_name, value in defaults.items():
                if field_name == "is_active":
                    continue
                if getattr(product, field_name) != value:
                    setattr(product, field_name, value)
                    changed_fields.append(field_name)
            if product.title != self.PRODUCT_TITLE:
                product.title = self.PRODUCT_TITLE
                changed_fields.append("title")
            if changed_fields:
                product.save(update_fields=list(dict.fromkeys(changed_fields)))
                self.stdout.write(
                    self.style.SUCCESS(
                        f"[ensure_edu_materials] Product fields updated: {', '.join(dict.fromkeys(changed_fields))}"
                    )
                )

        features = [
            {
                "icon": "🧪",
                "title": "HTML 자료 바로 실행",
                "description": "붙여넣은 코드나 업로드한 HTML 파일을 저장 직후 같은 화면에서 실행해 확인합니다.",
            },
            {
                "icon": "🛡️",
                "title": "Sandbox 학생 화면",
                "description": "학생 실행 화면은 sandbox iframe으로 분리되어 호스트 페이지를 건드리지 않습니다.",
            },
            {
                "icon": "📎",
                "title": "QR 즉시 배포",
                "description": "저장하면 학생 접속 주소와 QR을 바로 보여줘 수업에 즉시 붙일 수 있습니다.",
            },
        ]
        for feature in features:
            ProductFeature.objects.update_or_create(
                product=product,
                title=feature["title"],
                defaults={
                    "icon": feature["icon"],
                    "description": feature["description"],
                },
            )

        manual, _ = ServiceManual.objects.get_or_create(
            product=product,
            defaults={
                "title": "AI 수업자료 메이커 사용 가이드",
                "description": "HTML 자료 올리기부터 학생 공개, 수업 적용까지 빠르게 익히는 안내입니다.",
                "is_published": True,
            },
        )
        manual_changed = []
        if manual.title != "AI 수업자료 메이커 사용 가이드":
            manual.title = "AI 수업자료 메이커 사용 가이드"
            manual_changed.append("title")
        if manual.description != "HTML 자료 올리기부터 학생 공개, 수업 적용까지 빠르게 익히는 안내입니다.":
            manual.description = "HTML 자료 올리기부터 학생 공개, 수업 적용까지 빠르게 익히는 안내입니다."
            manual_changed.append("description")
        if not manual.is_published:
            manual.is_published = True
            manual_changed.append("is_published")
        if manual_changed:
            manual.save(update_fields=manual_changed)

        sections = [
            {
                "title": "시작하기",
                "content": "HTML 코드를 붙여넣거나 `.html` 파일을 올리면 즉시 실행 가능한 교육 자료로 저장됩니다.",
                "display_order": 1,
                "badge_text": "Step 1",
            },
            {
                "title": "교사용 확인",
                "content": "상세 화면에서 sandbox iframe 미리보기로 자료가 의도한 대로 동작하는지 먼저 확인하세요.",
                "display_order": 2,
                "badge_text": "Step 2",
            },
            {
                "title": "학생 공개",
                "content": "자료를 저장하면 학생용 실행 링크와 QR이 바로 준비되어 수업에 곧바로 띄울 수 있습니다.",
                "display_order": 3,
                "badge_text": "Step 3",
            },
        ]
        for section in sections:
            ManualSection.objects.update_or_create(
                manual=manual,
                title=section["title"],
                defaults={
                    "content": section["content"],
                    "display_order": section["display_order"],
                    "badge_text": section["badge_text"],
                },
            )

        created_count, updated_count = ensure_curriculum_lab_materials()
        if created_count or updated_count:
            self.stdout.write(
                self.style.SUCCESS(
                    f"[ensure_edu_materials] Curriculum lab materials synced: created={created_count}, updated={updated_count}"
                )
            )

        self.stdout.write(self.style.SUCCESS("[ensure_edu_materials] Done"))


def ensure_curriculum_lab_materials():
    teacher = _get_curriculum_lab_teacher()
    created_count = 0
    updated_count = 0

    for spec in CURRICULUM_LAB_SPECS:
        html_content = _build_curriculum_lab_html(spec)
        search_text = _build_seed_search_text(spec)
        defaults = {
            "html_content": html_content,
            "input_mode": EduMaterial.INPUT_PASTE,
            "original_filename": "",
            "subject": spec["subject"],
            "grade": spec["grade"],
            "unit_title": spec["unit_title"],
            "material_type": spec["material_type"],
            "tags": list(spec["tags"]),
            "summary": spec["summary"],
            "search_text": search_text,
            "metadata_status": EduMaterial.MetadataStatus.DONE,
            "metadata_source": EduMaterial.MetadataSource.MANUAL,
            "metadata_confidence": 1.0,
            "is_published": True,
        }

        material = EduMaterial.objects.filter(
            teacher=teacher,
            title=spec["title"],
            source_material__isnull=True,
        ).order_by("id").first()
        if material is None:
            EduMaterial.objects.create(teacher=teacher, title=spec["title"], **defaults)
            created_count += 1
            continue

        changed_fields = []
        for field_name, value in defaults.items():
            if getattr(material, field_name) != value:
                setattr(material, field_name, value)
                changed_fields.append(field_name)
        if changed_fields:
            material.save(update_fields=[*changed_fields, "updated_at"])
            updated_count += 1

    return created_count, updated_count


def _get_curriculum_lab_teacher():
    User = get_user_model()
    teacher, _ = User.objects.get_or_create(
        username=CURRICULUM_LAB_OWNER_USERNAME,
        defaults={
            "email": "curriculum-lab@eduitit.site",
            "first_name": "에듀잇티",
            "last_name": "수업연구소",
            "is_active": False,
        },
    )
    if teacher.has_usable_password():
        teacher.set_unusable_password()
        teacher.save(update_fields=["password"])

    profile, _ = UserProfile.objects.get_or_create(user=teacher)
    profile_updates = []
    if profile.nickname != CURRICULUM_LAB_OWNER_NICKNAME:
        profile.nickname = CURRICULUM_LAB_OWNER_NICKNAME
        profile_updates.append("nickname")
    if profile.role != "school":
        profile.role = "school"
        profile_updates.append("role")
    if profile_updates:
        profile.save(update_fields=profile_updates)
    return teacher


def _build_seed_search_text(spec):
    chunks = [
        spec["title"],
        spec["subject"],
        spec["grade"],
        spec["unit_title"],
        spec["summary"],
        spec["question"],
        " ".join(spec["tags"]),
    ]
    return re.sub(r"\s+", " ", " ".join(chunks)).strip()


def _build_teacher_line(spec):
    return f"교사용 한 줄: {spec['title']} - 슬라이더를 한 가지씩 바꾸며 그림과 수치를 함께 읽습니다."


def _build_learning_questions(spec):
    return [
        spec["question"],
        "슬라이더 하나만 바꾸면 그림과 수치 중 무엇이 먼저 달라지나요?",
        "친구에게 오늘 찾은 규칙을 한 문장으로 설명하면 어떻게 말할 수 있나요?",
    ]


def _build_event_values(spec):
    mode = spec["mode"]
    event_values = {
        "fraction": {"a_num": 1, "a_den": 2, "b_num": 2, "b_den": 4},
        "area": {"width": 8, "height": 3},
        "angle": {"angle": 90},
        "decimal": {"ones": 0, "tenths": 0, "hundredths": 4},
        "volume": {"length": 4, "depth": 3, "height": 3},
        "state": {"temp": 100},
        "shadow": {"sun": 20, "object": 120},
        "magnet": {"distance": 55, "flip": 0},
        "circuit": {"cells": 2, "switch_on": 1},
        "combustion": {"oxygen": 20, "fuel": 85, "heat": 90},
    }
    return event_values.get(mode, {})


def _build_curriculum_lab_html(spec):
    config_json = json.dumps(
        {
            "title": spec["title"],
            "subject": "수학" if spec["subject"] == "MATH" else "과학",
            "grade": spec["grade"],
            "unitTitle": spec["unit_title"],
            "summary": spec["summary"],
            "question": spec["question"],
            "mode": spec["mode"],
            "controls": spec["controls"],
            "teacherLine": _build_teacher_line(spec),
            "questions": _build_learning_questions(spec),
            "eventValues": _build_event_values(spec),
        },
        ensure_ascii=False,
    )
    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{spec["title"]}</title>
<style>
:root {{
  color-scheme: light;
  --ink: #102033;
  --muted: #5f6f83;
  --line: #d7e1ec;
  --panel: #ffffff;
  --soft: #f4f8fb;
  --accent: #0f9f76;
  --accent-2: #2563eb;
  --warn: #e0811b;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  min-height: 100vh;
  font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background: linear-gradient(180deg, #f8fbff 0%, #eef8f2 100%);
  color: var(--ink);
}}
.app {{
  width: min(1180px, calc(100vw - 24px));
  margin: 0 auto;
  padding: 18px 0 24px;
}}
.top {{
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 12px;
  align-items: end;
  margin-bottom: 14px;
}}
.eyebrow {{
  margin: 0 0 6px;
  color: var(--accent);
  font-size: 12px;
  font-weight: 900;
  letter-spacing: .14em;
}}
h1 {{
  margin: 0;
  font-size: clamp(24px, 4vw, 46px);
  line-height: 1.08;
  letter-spacing: 0;
}}
.badge {{
  display: inline-flex;
  gap: 6px;
  align-items: center;
  border: 1px solid #c9dfd8;
  border-radius: 999px;
  background: #fff;
  padding: 8px 12px;
  color: #146b54;
  font-size: 13px;
  font-weight: 800;
  white-space: nowrap;
}}
.layout {{
  display: grid;
  grid-template-columns: minmax(0, 1fr) 320px;
  gap: 14px;
}}
.stage, .side, .question {{
  border: 1px solid var(--line);
  border-radius: 8px;
  background: rgba(255,255,255,.95);
  box-shadow: 0 16px 42px rgba(16, 32, 51, .08);
}}
.stage {{
  min-height: 520px;
  padding: 16px;
  overflow: hidden;
}}
.side {{
  padding: 14px;
}}
.question {{
  grid-column: 1 / -1;
  padding: 14px 16px;
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 12px;
  align-items: center;
}}
.question p, .side p {{
  margin: 0;
  color: var(--muted);
  font-size: 15px;
  line-height: 1.5;
}}
.teacher-line {{
  margin-top: 10px;
  border-left: 4px solid var(--accent);
  border-radius: 8px;
  background: #f0fbf7;
  padding: 10px 11px;
  color: #0e5f49;
  font-size: 14px;
  font-weight: 850;
  line-height: 1.45;
}}
.readout {{
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 14px;
}}
.metric {{
  min-height: 78px;
  border: 1px solid #dbe7f2;
  border-radius: 8px;
  background: #f9fcff;
  padding: 11px;
}}
.metric b {{
  display: block;
  font-size: 24px;
  line-height: 1.1;
  color: var(--accent-2);
}}
.metric span {{
  color: var(--muted);
  font-size: 12px;
  font-weight: 800;
}}
.control {{
  border-top: 1px solid #e3ebf3;
  padding-top: 12px;
  margin-top: 12px;
}}
.control:first-of-type {{
  border-top: 0;
  padding-top: 0;
  margin-top: 0;
}}
.control-row {{
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  margin-bottom: 8px;
  font-weight: 850;
}}
.control-row output {{
  min-width: 44px;
  border-radius: 999px;
  background: #eaf7f2;
  color: #09644d;
  padding: 5px 9px;
  text-align: center;
  font-variant-numeric: tabular-nums;
}}
input[type=range] {{
  width: 100%;
  accent-color: var(--accent);
}}
.tool-row {{
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  margin-top: 14px;
}}
.toggle-help, .action-button {{
  border: 0;
  border-radius: 8px;
  background: var(--ink);
  color: #fff;
  padding: 10px 14px;
  font-weight: 900;
  cursor: pointer;
}}
.action-button.secondary {{
  background: #eaf4ff;
  color: #164677;
}}
.speed-control {{
  display: grid;
  gap: 8px;
  margin-top: 12px;
  border-radius: 8px;
  background: #f8fafc;
  padding: 10px;
  color: var(--muted);
  font-size: 13px;
  font-weight: 850;
}}
.speed-control span {{
  color: var(--accent-2);
}}
.learning-questions {{
  margin: 8px 0 0;
  padding-left: 20px;
  color: var(--ink);
  font-size: 15px;
  font-weight: 750;
  line-height: 1.55;
}}
.learning-questions li + li {{
  margin-top: 5px;
}}
.hint {{
  margin-top: 12px;
  border-radius: 8px;
  background: #fff7ed;
  border: 1px solid #fed7aa;
  padding: 11px;
  color: #7c3f08;
  font-weight: 750;
  line-height: 1.55;
}}
.hint[hidden] {{ display: none; }}
svg {{
  display: block;
  width: 100%;
  height: 410px;
  border-radius: 8px;
  background: #f8fbff;
}}
.caption {{
  margin-top: 12px;
  color: var(--muted);
  font-size: 15px;
  font-weight: 750;
  line-height: 1.55;
}}
@media (max-width: 860px) {{
  .top, .layout, .question {{
    grid-template-columns: 1fr;
  }}
  .readout {{
    grid-template-columns: 1fr;
  }}
  .stage {{
    min-height: auto;
  }}
  svg {{
    height: 340px;
  }}
  .badge, .toggle-help, .action-button {{
    justify-self: start;
  }}
  .tool-row {{
    grid-template-columns: 1fr;
  }}
}}
</style>
</head>
<body>
<main class="app">
  <section class="top">
    <div>
      <p class="eyebrow">2022 개정 · {("수학" if spec["subject"] == "MATH" else "과학")} · {spec["grade"]}</p>
      <h1>{spec["title"]}</h1>
    </div>
    <div class="badge">{spec["unit_title"]}</div>
  </section>
  <section class="layout">
    <div class="stage">
      <div class="readout" id="metrics"></div>
      <svg id="visual" viewBox="0 0 900 430" role="img" aria-label="조작 결과 시각화"></svg>
      <div class="caption" id="caption"></div>
    </div>
    <aside class="side">
      <p>{spec["summary"]}</p>
      <div class="teacher-line" id="teacherLine"></div>
      <div id="controls"></div>
      <div class="tool-row">
        <button class="action-button" type="button" id="playButton">재생</button>
        <button class="action-button secondary" type="button" id="resetButton">초기화</button>
        <button class="action-button secondary" type="button" id="eventButton">핵심 장면</button>
      </div>
      <label class="speed-control">
        <span id="speedLabel">배속 1x</span>
        <input type="range" id="speedRange" min="1" max="4" value="1" step="1">
      </label>
      <div class="hint" id="hint" hidden></div>
    </aside>
    <div class="question">
      <div>
        <p>{spec["question"]}</p>
        <ol class="learning-questions" id="learningQuestions"></ol>
      </div>
      <button class="toggle-help" type="button" id="helpButton">생각 힌트</button>
    </div>
  </section>
</main>
<script>
const config = {config_json};
const initialState = Object.fromEntries(config.controls.map((control) => [control.id, Number(control.value)]));
const state = {{...initialState}};
const svg = document.getElementById("visual");
const metrics = document.getElementById("metrics");
const caption = document.getElementById("caption");
const controlsRoot = document.getElementById("controls");
const teacherLine = document.getElementById("teacherLine");
const learningQuestions = document.getElementById("learningQuestions");
const hint = document.getElementById("hint");
const helpButton = document.getElementById("helpButton");
const playButton = document.getElementById("playButton");
const resetButton = document.getElementById("resetButton");
const eventButton = document.getElementById("eventButton");
const speedRange = document.getElementById("speedRange");
const speedLabel = document.getElementById("speedLabel");
let isPlaying = false;
let lastTick = 0;
let rafId = null;
let dragTarget = null;
let dragOffsetX = 0;

const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
const round = (value, digits = 2) => Number(value).toFixed(digits).replace(/\\.0+$/, "").replace(/(\\.\\d*?)0+$/, "$1");
const svgNode = (tag, attrs = {{}}, text = "") => {{
  const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
  Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, value));
  if (text) node.textContent = text;
  return node;
}};
const clearSvg = () => {{
  while (svg.firstChild) svg.removeChild(svg.firstChild);
}};
const setMetrics = (items) => {{
  metrics.innerHTML = items.map((item) => `<div class="metric"><span>${{item.label}}</span><b>${{item.value}}</b></div>`).join("");
}};
const color = (name) => ({{
  green: "#15a87f", blue: "#2563eb", sky: "#7dd3fc", amber: "#f59e0b",
  red: "#ef4444", slate: "#334155", soft: "#eaf4ff", purple: "#7c3aed"
}}[name]);

function drawText(x, y, text, size = 20, fill = "#102033", weight = 800) {{
  svg.appendChild(svgNode("text", {{x, y, "font-size": size, fill, "font-weight": weight, "font-family": "system-ui, sans-serif"}}, text));
}}

function formatControlValue(control, value) {{
  if (config.mode === "magnet" && control.id === "flip") return Number(value) === 0 ? "N" : "S";
  return value;
}}

function renderLessonText() {{
  teacherLine.textContent = config.teacherLine;
  learningQuestions.innerHTML = config.questions.map((question) => `<li>${{question}}</li>`).join("");
}}

function renderControls() {{
  controlsRoot.innerHTML = "";
  config.controls.forEach((control) => {{
    const wrap = document.createElement("label");
    wrap.className = "control";
    const outputId = `out-${{control.id}}`;
    wrap.innerHTML = `
      <div class="control-row">
        <span>${{control.label}}</span>
        <output id="${{outputId}}">${{formatControlValue(control, state[control.id])}}</output>
      </div>
      <input type="range" data-control-id="${{control.id}}" min="${{control.min}}" max="${{control.max}}" value="${{state[control.id]}}" step="${{control.step || 1}}">
    `;
    const range = wrap.querySelector("input");
    const output = wrap.querySelector("output");
    range.addEventListener("input", () => {{
      state[control.id] = Number(range.value);
      output.value = formatControlValue(control, state[control.id]);
      output.textContent = formatControlValue(control, state[control.id]);
      render();
    }});
    controlsRoot.appendChild(wrap);
  }});
}}

function syncControlValues() {{
  controlsRoot.querySelectorAll("input[data-control-id]").forEach((range) => {{
    const id = range.dataset.controlId;
    const control = config.controls.find((item) => item.id === id);
    const output = range.closest(".control").querySelector("output");
    range.value = state[id];
    output.value = formatControlValue(control, state[id]);
    output.textContent = formatControlValue(control, state[id]);
  }});
}}

function getPlaybackControl() {{
  return config.controls.find((control) => control.id !== "flip" && control.id !== "switch_on") || config.controls[0];
}}

function stepSimulation(delta) {{
  const control = getPlaybackControl();
  if (!control) return;
  const speed = Number(speedRange.value || 1);
  const step = Number(control.step || 1);
  const amount = Math.max(step, Math.round(delta / 420) * speed * step);
  let next = Number(state[control.id]) + amount;
  if (next > Number(control.max)) next = Number(control.min);
  state[control.id] = next;
  syncControlValues();
  render();
}}

function animationLoop(timestamp) {{
  if (!isPlaying) return;
  if (!lastTick) lastTick = timestamp;
  const delta = timestamp - lastTick;
  if (delta >= 180) {{
    stepSimulation(delta);
    lastTick = timestamp;
  }}
  rafId = requestAnimationFrame(animationLoop);
}}

function setPlaying(next) {{
  isPlaying = next;
  playButton.textContent = isPlaying ? "일시정지" : "재생";
  if (isPlaying) {{
    lastTick = 0;
    rafId = requestAnimationFrame(animationLoop);
  }} else if (rafId) {{
    cancelAnimationFrame(rafId);
    rafId = null;
  }}
}}

function resetSimulation() {{
  setPlaying(false);
  Object.entries(initialState).forEach(([key, value]) => {{
    state[key] = value;
  }});
  syncControlValues();
  render();
}}

function triggerKeyMoment() {{
  setPlaying(false);
  Object.entries(config.eventValues || {{}}).forEach(([key, value]) => {{
    if (key in state) state[key] = value;
  }});
  syncControlValues();
  render();
}}

function renderFraction() {{
  const aNum = clamp(state.a_num, 1, state.a_den);
  const bNum = clamp(state.b_num, 1, state.b_den);
  state.a_num = aNum;
  state.b_num = bNum;
  const a = aNum / state.a_den;
  const b = bNum / state.b_den;
  setMetrics([
    {{label: "위 분수", value: `${{aNum}}/${{state.a_den}}`}},
    {{label: "아래 분수", value: `${{bNum}}/${{state.b_den}}`}},
    {{label: "크기 차이", value: round(Math.abs(a - b), 2)}},
  ]);
  clearSvg();
  const drawBar = (y, den, num, label, fill) => {{
    const x = 90, width = 720, height = 70;
    svg.appendChild(svgNode("rect", {{x, y, width, height, rx: 12, fill: "#fff", stroke: "#cbd5e1", "stroke-width": 3}}));
    for (let i = 0; i < den; i += 1) {{
      const cell = width / den;
      if (i < num) svg.appendChild(svgNode("rect", {{x: x + i * cell, y, width: cell, height, fill, opacity: .82}}));
      svg.appendChild(svgNode("line", {{x1: x + i * cell, y1: y, x2: x + i * cell, y2: y + height, stroke: "#94a3b8", "stroke-width": 1}}));
    }}
    svg.appendChild(svgNode("rect", {{x, y, width, height, rx: 12, fill: "none", stroke: "#334155", "stroke-width": 3}}));
    drawText(90, y - 18, label, 24);
  }};
  drawBar(120, state.a_den, aNum, `${{aNum}}/${{state.a_den}}`, color("green"));
  drawBar(250, state.b_den, bNum, `${{bNum}}/${{state.b_den}}`, color("blue"));
  const relation = Math.abs(a - b) < .001 ? "같은 크기" : (a > b ? "위가 더 큼" : "아래가 더 큼");
  drawText(370, 70, relation, 32, color(Math.abs(a - b) < .001 ? "green" : "amber"), 950);
  caption.textContent = "분수 막대는 전체 길이가 같습니다. 조각 수가 달라져도 색칠된 길이를 비교하면 크기가 바로 보입니다.";
  return "서로 같은 길이가 되는 분수는 이름은 달라도 같은 양을 나타냅니다.";
}}

function renderArea() {{
  const w = state.width, h = state.height;
  const area = w * h, peri = 2 * (w + h);
  setMetrics([
    {{label: "넓이", value: `${{area}}칸`}},
    {{label: "둘레", value: `${{peri}}칸`}},
    {{label: "가로×세로", value: `${{w}}×${{h}}`}},
  ]);
  clearSvg();
  const size = Math.min(54, 540 / Math.max(w, h));
  const x0 = 120, y0 = 60;
  for (let y = 0; y < h; y += 1) {{
    for (let x = 0; x < w; x += 1) {{
      svg.appendChild(svgNode("rect", {{x: x0 + x * size, y: y0 + y * size, width: size, height: size, fill: "#dff7ef", stroke: "#7cc8b0"}}));
    }}
  }}
  svg.appendChild(svgNode("rect", {{x: x0, y: y0, width: w * size, height: h * size, fill: "none", stroke: color("green"), "stroke-width": 8}}));
  drawText(120, y0 + h * size + 46, `안쪽 칸 ${{area}}개`, 28, color("blue"));
  drawText(120, y0 + h * size + 84, `바깥 테두리 ${{peri}}칸`, 24, color("green"));
  caption.textContent = "넓이는 안쪽을 덮는 칸 수, 둘레는 바깥을 한 바퀴 도는 길이입니다.";
  return "같은 넓이도 길쭉하게 만들면 바깥 테두리가 길어질 수 있습니다.";
}}

function renderAngle() {{
  const deg = state.angle;
  const rad = deg * Math.PI / 180;
  const cx = 450, cy = 300, r = 220;
  const x2 = cx + Math.cos(Math.PI - rad) * r;
  const y2 = cy - Math.sin(Math.PI - rad) * r;
  const kind = deg === 90 ? "직각" : (deg < 90 ? "예각" : "둔각");
  setMetrics([
    {{label: "각도", value: `${{deg}}°`}},
    {{label: "이름", value: kind}},
    {{label: "90°와 차이", value: `${{Math.abs(90 - deg)}}°`}},
  ]);
  clearSvg();
  svg.appendChild(svgNode("line", {{x1: cx, y1: cy, x2: cx - r, y2: cy, stroke: "#334155", "stroke-width": 8, "stroke-linecap": "round"}}));
  svg.appendChild(svgNode("line", {{x1: cx, y1: cy, x2, y2, stroke: color(deg === 90 ? "green" : deg < 90 ? "blue" : "amber"), "stroke-width": 8, "stroke-linecap": "round"}}));
  svg.appendChild(svgNode("circle", {{cx, cy, r: 10, fill: "#102033"}}));
  const arcR = 110;
  const startX = cx - arcR, startY = cy;
  const endX = cx + Math.cos(Math.PI - rad) * arcR;
  const endY = cy - Math.sin(Math.PI - rad) * arcR;
  svg.appendChild(svgNode("path", {{d: `M ${{startX}} ${{startY}} A ${{arcR}} ${{arcR}} 0 ${{deg > 180 ? 1 : 0}} 1 ${{endX}} ${{endY}}`, fill: "none", stroke: "#ef9f2d", "stroke-width": 5}}));
  drawText(386, 178, `${{deg}}°`, 36, color("amber"), 950);
  drawText(386, 90, kind, 34, color(kind === "직각" ? "green" : "blue"), 950);
  caption.textContent = "각도는 두 선이 벌어진 정도입니다. 90도를 기준으로 예각, 직각, 둔각이 갈립니다.";
  return "90도보다 작으면 예각, 같으면 직각, 크면 둔각입니다.";
}}

function renderDecimal() {{
  const value = state.ones + state.tenths / 10 + state.hundredths / 100;
  setMetrics([
    {{label: "소수", value: round(value, 2)}},
    {{label: "분해", value: `${{state.ones}} + ${{state.tenths}}/10 + ${{state.hundredths}}/100`}},
    {{label: "백분의 일", value: `${{Math.round(value * 100)}}개`}},
  ]);
  clearSvg();
  const parts = [
    {{label: "일", count: state.ones, size: 110, x: 80, y: 90, fill: "#bfdbfe"}},
    {{label: "십분의 일", count: state.tenths, size: 38, x: 410, y: 90, fill: "#bbf7d0"}},
    {{label: "백분의 일", count: state.hundredths, size: 18, x: 410, y: 255, fill: "#fed7aa"}},
  ];
  parts.forEach((part) => {{
    drawText(part.x, part.y - 24, `${{part.label}} ${{part.count}}개`, 22, "#334155");
    for (let i = 0; i < part.count; i += 1) {{
      const x = part.x + (i % 10) * (part.size + 4);
      const y = part.y + Math.floor(i / 10) * (part.size + 4);
      svg.appendChild(svgNode("rect", {{x, y, width: part.size, height: part.size, rx: 5, fill: part.fill, stroke: "#64748b"}}));
    }}
  }});
  drawText(80, 370, `같은 4라도 자리가 바뀌면 4, 0.4, 0.04처럼 크기가 달라집니다.`, 24, color("slate"));
  caption.textContent = "소수점은 자리의 단위를 바꿉니다. 오른쪽으로 갈수록 한 칸의 크기가 10분의 1이 됩니다.";
  return "숫자만 보지 말고 자리 이름을 함께 읽으면 소수의 크기가 분명해집니다.";
}}

function renderVolume() {{
  const l = state.length, d = state.depth, h = state.height;
  const volume = l * d * h;
  const base = l * d;
  setMetrics([
    {{label: "부피", value: `${{volume}}개`}},
    {{label: "한 층", value: `${{base}}개`}},
    {{label: "층수", value: `${{h}}층`}},
  ]);
  clearSvg();
  drawText(70, 64, `${{l}} × ${{d}} × ${{h}} = ${{volume}}`, 42, color("purple"), 950);
  drawText(70, 106, `바닥 한 층 ${{l}}×${{d}} = ${{base}}개, 그 층을 ${{h}}번 쌓기`, 23, color("slate"), 850);

  const cell = Math.min(38, Math.floor(250 / Math.max(l, d)));
  const floorX = 86, floorY = 150;
  svg.appendChild(svgNode("rect", {{x: floorX - 12, y: floorY - 36, width: l * cell + 24, height: d * cell + 70, rx: 14, fill: "#f8fafc", stroke: "#dbe4ef", "stroke-width": 3}}));
  drawText(floorX, floorY - 12, "바닥 한 층", 24, color("blue"), 950);
  for (let row = 0; row < d; row += 1) {{
    for (let col = 0; col < l; col += 1) {{
      svg.appendChild(svgNode("rect", {{
        x: floorX + col * cell,
        y: floorY + row * cell,
        width: cell - 3,
        height: cell - 3,
        rx: 5,
        fill: "#dbeafe",
        stroke: "#2563eb",
        "stroke-width": 2,
      }}));
    }}
  }}
  drawText(floorX, floorY + d * cell + 38, `${{base}}개`, 28, color("blue"), 950);

  const stackX = 476, stackBaseY = 326;
  const slabW = 58 + l * 32;
  const slabD = 26 + d * 10;
  const slabH = 24;
  const layerRise = 33;
  const drawSlab = (index) => {{
    const x = stackX;
    const y = stackBaseY - index * layerRise;
    const fillTop = index % 2 === 0 ? "#ddd6fe" : "#ede9fe";
    svg.appendChild(svgNode("polygon", {{
      points: `${{x}},${{y}} ${{x + slabW}},${{y - slabD}} ${{x + slabW + slabD}},${{y}} ${{x + slabD}},${{y + slabD}}`,
      fill: fillTop,
      stroke: "#7c3aed",
      "stroke-width": 3,
    }}));
    svg.appendChild(svgNode("polygon", {{
      points: `${{x + slabD}},${{y + slabD}} ${{x + slabW + slabD}},${{y}} ${{x + slabW + slabD}},${{y + slabH}} ${{x + slabD}},${{y + slabD + slabH}}`,
      fill: "#c4b5fd",
      stroke: "#7c3aed",
      "stroke-width": 3,
    }}));
    svg.appendChild(svgNode("polygon", {{
      points: `${{x}},${{y}} ${{x + slabD}},${{y + slabD}} ${{x + slabD}},${{y + slabD + slabH}} ${{x}},${{y + slabH}}`,
      fill: "#a78bfa",
      stroke: "#7c3aed",
      "stroke-width": 3,
    }}));
    drawText(x + slabW + slabD + 16, y + 15, `${{index + 1}}층`, 18, color("purple"), 850);
  }};
  for (let z = 0; z < h; z += 1) drawSlab(z);
  drawText(520, 88, "층으로 쌓기", 28, color("purple"), 950);
  drawText(520, 122, `${{base}}개짜리 한 층 × ${{h}}층`, 23, color("slate"), 850);
  caption.textContent = "왼쪽에서 바닥 한 층의 단위 정육면체 수를 세고, 오른쪽에서 그 층이 몇 번 쌓였는지 확인합니다.";
  return "부피는 바닥 한 층의 개수에 층수를 곱하면 됩니다.";
}}

function renderState() {{
  const temp = state.temp;
  const phase = temp < 0 ? "고체" : (temp < 100 ? "액체" : "기체");
  const speed = temp < 0 ? "느림" : (temp < 100 ? "중간" : "빠름");
  setMetrics([
    {{label: "온도", value: `${{temp}}°C`}},
    {{label: "상태", value: phase}},
    {{label: "움직임", value: speed}},
  ]);
  clearSvg();
  const baseY = 285;
  svg.appendChild(svgNode("rect", {{x: 250, y: 90, width: 400, height: 260, rx: 22, fill: "#eff6ff", stroke: "#93c5fd", "stroke-width": 4}}));
  const count = 30;
  for (let i = 0; i < count; i += 1) {{
    const row = Math.floor(i / 6), col = i % 6;
    let x = 300 + col * 58;
    let y = 135 + row * 40;
    if (phase === "액체") {{ x += Math.sin(i + temp) * 16; y += Math.cos(i * 2 + temp) * 10 + 38; }}
    if (phase === "기체") {{ x = 285 + ((i * 73 + temp * 3) % 330); y = 105 + ((i * 47 + temp * 5) % 210); }}
    svg.appendChild(svgNode("circle", {{cx: x, cy: y, r: phase === "기체" ? 9 : 13, fill: phase === "고체" ? "#93c5fd" : phase === "액체" ? "#38bdf8" : "#fbbf24", stroke: "#334155"}}));
  }}
  drawText(110, 380, phase === "고체" ? "입자가 제자리 가까이 있습니다." : phase === "액체" ? "입자가 서로 붙어 흐릅니다." : "입자가 멀리 퍼져 빠르게 움직입니다.", 25, color("slate"));
  caption.textContent = "온도가 달라지면 입자의 움직임이 달라지고, 눈에 보이는 상태도 바뀝니다.";
  return "상태가 바뀌어도 물 입자 자체가 사라진 것은 아닙니다.";
}}

function renderShadow() {{
  const sun = state.sun, object = state.object;
  const length = Math.round(object * (90 - sun) / 24);
  setMetrics([
    {{label: "빛의 높이", value: `${{sun}}°`}},
    {{label: "물체 높이", value: object}},
    {{label: "그림자", value: length}},
  ]);
  clearSvg();
  const groundY = 335, objX = 520;
  const sunX = 130, sunY = 300 - sun * 2.6;
  svg.appendChild(svgNode("line", {{x1: 60, y1: groundY, x2: 840, y2: groundY, stroke: "#94a3b8", "stroke-width": 5}}));
  svg.appendChild(svgNode("circle", {{cx: sunX, cy: sunY, r: 34, fill: "#fde047", stroke: "#eab308", "stroke-width": 4}}));
  svg.appendChild(svgNode("rect", {{x: objX, y: groundY - object, width: 42, height: object, rx: 8, fill: "#64748b"}}));
  svg.appendChild(svgNode("polygon", {{points: `${{objX + 42}},${{groundY}} ${{objX + 42 + length}},${{groundY}} ${{objX + 42}},${{groundY - 18}}`, fill: "#475569", opacity: .45}}));
  svg.appendChild(svgNode("line", {{x1: sunX, y1: sunY, x2: objX + 42, y2: groundY - object, stroke: "#f59e0b", "stroke-width": 4, "stroke-dasharray": "8 8"}}));
  drawText(90, 70, "빛은 곧게 나아갑니다", 28, color("amber"), 950);
  caption.textContent = "빛이 낮은 곳에서 비스듬히 오면 물체 뒤쪽으로 막히는 구간이 길어집니다.";
  return "그림자는 빛이 물체에 막혀 생긴 어두운 자리입니다.";
}}

function getMagnetDistanceControl() {{
  return config.controls.find((control) => control.id === "distance");
}}

function getMagnetLayout() {{
  return {{leftX: 130, y: 158, width: 150, height: 86}};
}}

function svgClientX(event) {{
  const rect = svg.getBoundingClientRect();
  return (event.clientX - rect.left) * (900 / rect.width);
}}

function setMagnetDistanceFromPointer(event) {{
  const control = getMagnetDistanceControl();
  const layout = getMagnetLayout();
  const rawGap = Math.round(svgClientX(event) - dragOffsetX - (layout.leftX + layout.width));
  state.distance = clamp(rawGap, Number(control.min), Number(control.max));
  syncControlValues();
  render();
}}

function beginMagnetDrag(event) {{
  if (config.mode !== "magnet") return;
  setPlaying(false);
  dragTarget = "right-magnet";
  const layout = getMagnetLayout();
  const control = getMagnetDistanceControl();
  const gap = clamp(state.distance, Number(control.min), Number(control.max));
  dragOffsetX = svgClientX(event) - (layout.leftX + layout.width + gap);
  if (svg.setPointerCapture) svg.setPointerCapture(event.pointerId);
  setMagnetDistanceFromPointer(event);
  event.preventDefault();
}}

function handleMagnetDragMove(event) {{
  if (dragTarget !== "right-magnet") return;
  setMagnetDistanceFromPointer(event);
  event.preventDefault();
}}

function endMagnetDrag(event) {{
  if (dragTarget !== "right-magnet") return;
  dragTarget = null;
  dragOffsetX = 0;
  if (svg.releasePointerCapture) {{
    try {{ svg.releasePointerCapture(event.pointerId); }} catch (error) {{}}
  }}
}}

function renderMagnet() {{
  const control = getMagnetDistanceControl();
  const gap = clamp(state.distance, Number(control.min), Number(control.max));
  state.distance = gap;
  const rightFacingPole = state.flip === 0 ? "N" : "S";
  const leftFacingPole = "S";
  const attracts = leftFacingPole !== rightFacingPole;
  const force = Math.max(1, Math.round(900 / Math.max(gap, 30)));
  setMetrics([
    {{label: "마주 보는 극", value: `${{leftFacingPole}}-${{rightFacingPole}}`}},
    {{label: "힘 방향", value: attracts ? "끌어당김" : "밀어냄"}},
    {{label: "힘 느낌", value: force}},
  ]);
  clearSvg();
  const layout = getMagnetLayout();
  const leftX = layout.leftX, y = layout.y, w = layout.width, h = layout.height;
  const rightX = leftX + w + gap;
  const centerGap = leftX + w + gap / 2;
  const poleFill = (pole) => pole === "N" ? "#ef4444" : "#2563eb";
  const drawMagnet = (x, leftPole, rightPole, draggable = false) => {{
    const group = svgNode("g", {{
      "data-drag-target": draggable ? "right-magnet" : "fixed-magnet",
      tabindex: draggable ? "0" : "-1",
      role: draggable ? "slider" : "img",
      "aria-label": draggable ? "오른쪽 자석을 좌우로 끌어 거리 조절" : "왼쪽 기준 자석",
    }});
    if (draggable) {{
      group.style.cursor = "grab";
      group.addEventListener("pointerdown", beginMagnetDrag);
    }}
    group.appendChild(svgNode("rect", {{x, y: y - 18, width: w, height: h + 36, rx: 14, fill: "transparent"}}));
    group.appendChild(svgNode("rect", {{x, y, width: w / 2, height: h, rx: 12, fill: poleFill(leftPole)}}));
    group.appendChild(svgNode("rect", {{x: x + w / 2, y, width: w / 2, height: h, rx: 12, fill: poleFill(rightPole)}}));
    group.appendChild(svgNode("line", {{x1: x + w / 2, y1: y, x2: x + w / 2, y2: y + h, stroke: "#fff", "stroke-width": 3, opacity: .85}}));
    group.appendChild(svgNode("rect", {{x, y, width: w, height: h, rx: 12, fill: "none", stroke: "#102033", "stroke-width": 4}}));
    group.appendChild(svgNode("text", {{x: x + 31, y: y + 54, "font-size": 34, fill: "#fff", "font-weight": 950, "font-family": "system-ui, sans-serif"}}, leftPole));
    group.appendChild(svgNode("text", {{x: x + 106, y: y + 54, "font-size": 34, fill: "#fff", "font-weight": 950, "font-family": "system-ui, sans-serif"}}, rightPole));
    svg.appendChild(group);
  }};
  drawMagnet(leftX, "N", "S", false);
  drawMagnet(rightX, rightFacingPole, rightFacingPole === "N" ? "S" : "N", true);
  svg.appendChild(svgNode("line", {{x1: leftX + w, y1: y + h + 40, x2: rightX, y2: y + h + 40, stroke: "#64748b", "stroke-width": 4, "stroke-dasharray": "8 8"}}));
  svg.appendChild(svgNode("line", {{x1: leftX + w, y1: y + h + 28, x2: leftX + w, y2: y + h + 52, stroke: "#64748b", "stroke-width": 4}}));
  svg.appendChild(svgNode("line", {{x1: rightX, y1: y + h + 28, x2: rightX, y2: y + h + 52, stroke: "#64748b", "stroke-width": 4}}));
  drawText(centerGap - 50, y + h + 82, `${{gap}} 거리`, 22, color("slate"), 850);
  drawText(290, 96, `마주 보는 극 ${{leftFacingPole}}-${{rightFacingPole}}`, 30, color("slate"), 950);
  drawText(342, 320, attracts ? "서로 끌어당김" : "서로 밀어냄", 38, attracts ? color("green") : color("red"), 950);
  drawText(390, 134, attracts ? "→   ←" : "←   →", 46, attracts ? color("green") : color("red"), 950);
  drawText(rightX + 6, y - 28, "직접 드래그", 20, color("amber"), 950);
  caption.textContent = "오른쪽 자석을 직접 끌어 거리를 바꾸고, 오른쪽 왼쪽 끝 극을 N/S로 바꿔 보세요.";
  return attracts ? "다른 극끼리는 서로 끌어당깁니다." : "같은 극끼리는 서로 밀어냅니다.";
}}

function renderCircuit() {{
  const cells = state.cells, closed = state.switch_on === 1;
  const bright = closed ? cells : 0;
  setMetrics([
    {{label: "전지", value: `${{cells}}개`}},
    {{label: "회로", value: closed ? "닫힘" : "열림"}},
    {{label: "밝기", value: bright}},
  ]);
  clearSvg();
  svg.appendChild(svgNode("rect", {{x: 170, y: 115, width: 560, height: 210, rx: 28, fill: "none", stroke: closed ? color("green") : "#cbd5e1", "stroke-width": 10, "stroke-dasharray": closed ? "" : "18 14"}}));
  for (let i = 0; i < cells; i += 1) {{
    svg.appendChild(svgNode("rect", {{x: 230 + i * 54, y: 86, width: 28, height: 58, fill: "#fef3c7", stroke: "#92400e", "stroke-width": 3}}));
    drawText(234 + i * 54, 122, "+", 22, "#92400e", 950);
  }}
  svg.appendChild(svgNode("circle", {{cx: 610, cy: 220, r: 58, fill: closed ? `rgba(250, 204, 21, ${{0.35 + cells * .18}})` : "#f8fafc", stroke: "#334155", "stroke-width": 5}}));
  svg.appendChild(svgNode("path", {{d: "M585 236 Q610 180 635 236", fill: "none", stroke: closed ? "#f59e0b" : "#94a3b8", "stroke-width": 6}}));
  svg.appendChild(svgNode("line", {{x1: 430, y1: 325, x2: closed ? 515 : 485, y2: closed ? 325 : 285, stroke: "#334155", "stroke-width": 9, "stroke-linecap": "round"}}));
  drawText(390, 378, closed ? "길이 이어져 전구가 켜집니다." : "길이 끊겨 전구가 꺼집니다.", 26, closed ? color("green") : color("red"), 950);
  caption.textContent = "전기는 끊기지 않은 길을 따라 흐릅니다. 스위치는 그 길을 열고 닫는 장치입니다.";
  return "전구가 켜지려면 전지, 전선, 전구가 한 바퀴로 이어져야 합니다.";
}}

function renderCombustion() {{
  const oxygen = state.oxygen, fuel = state.fuel, heat = state.heat;
  const fire = Math.min(oxygen, fuel, heat);
  setMetrics([
    {{label: "산소", value: oxygen}},
    {{label: "탈 물질", value: fuel}},
    {{label: "열", value: heat}},
  ]);
  clearSvg();
  const points = "450,70 250,330 650,330";
  svg.appendChild(svgNode("polygon", {{points, fill: fire > 45 ? "#fff7ed" : "#f8fafc", stroke: fire > 45 ? "#fb923c" : "#cbd5e1", "stroke-width": 7}}));
  drawText(418, 58, "열", 28, heat > 40 ? color("red") : "#94a3b8", 950);
  drawText(178, 350, "산소", 28, oxygen > 40 ? color("blue") : "#94a3b8", 950);
  drawText(660, 350, "탈 물질", 28, fuel > 40 ? color("green") : "#94a3b8", 950);
  const flameHeight = Math.max(0, fire * 2);
  if (fire > 20) {{
    svg.appendChild(svgNode("path", {{d: `M450 ${{320 - flameHeight}} C390 ${{250 - flameHeight/2}} 435 210 450 130 C510 210 530 250 450 ${{320 - flameHeight}}`, fill: "#f97316", opacity: .9}}));
    svg.appendChild(svgNode("path", {{d: `M450 ${{315 - flameHeight*.65}} C420 ${{265 - flameHeight*.35}} 445 230 450 180 C485 230 500 265 450 ${{315 - flameHeight*.65}}`, fill: "#fde047", opacity: .9}}));
  }}
  drawText(330, 390, fire > 45 ? "세 조건이 모두 충분해 불꽃이 유지됩니다." : "조건 하나가 부족해 불꽃이 약해집니다.", 24, fire > 45 ? color("green") : color("red"), 950);
  caption.textContent = "연소에는 산소, 탈 물질, 충분한 열이 함께 필요합니다.";
  return "소화는 세 조건 중 하나 이상을 줄이거나 끊는 일입니다.";
}}

function render() {{
  let help = "";
  if (config.mode === "fraction") help = renderFraction();
  if (config.mode === "area") help = renderArea();
  if (config.mode === "angle") help = renderAngle();
  if (config.mode === "decimal") help = renderDecimal();
  if (config.mode === "volume") help = renderVolume();
  if (config.mode === "state") help = renderState();
  if (config.mode === "shadow") help = renderShadow();
  if (config.mode === "magnet") help = renderMagnet();
  if (config.mode === "circuit") help = renderCircuit();
  if (config.mode === "combustion") help = renderCombustion();
  hint.textContent = help;
}}

helpButton.addEventListener("click", () => {{
  hint.hidden = !hint.hidden;
}});
playButton.addEventListener("click", () => setPlaying(!isPlaying));
resetButton.addEventListener("click", resetSimulation);
eventButton.addEventListener("click", triggerKeyMoment);
speedRange.addEventListener("input", () => {{
  speedLabel.textContent = `배속 ${{speedRange.value}}x`;
}});
svg.addEventListener("pointermove", handleMagnetDragMove);
svg.addEventListener("pointerup", endMagnetDrag);
svg.addEventListener("pointercancel", endMagnetDrag);
window.addEventListener("pointermove", handleMagnetDragMove);
window.addEventListener("pointerup", endMagnetDrag);
window.addEventListener("pointercancel", endMagnetDrag);
renderLessonText();
renderControls();
render();
</script>
</body>
</html>"""
