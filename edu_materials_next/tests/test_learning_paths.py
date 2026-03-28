from django.test import SimpleTestCase

from edu_materials_next.learning_paths import TOPIC_PLACEHOLDER, build_ai_prompt, get_mission, get_starter


class EduMaterialsNextPromptTests(SimpleTestCase):
    def test_prompt_is_html_first_and_cdn_safe_by_default(self):
        prompt = build_ai_prompt(
            "태양계 행성의 자전과 공전",
            starter=get_starter("planet-lab"),
            mission=get_mission("vibe-basics"),
        )

        self.assertIn("최종 산출물의 중심은 반드시 HTML입니다.", prompt)
        self.assertIn("<!DOCTYPE html>", prompt)
        self.assertIn("기본 원칙은 CDN 없이 작동하는 순수 HTML, CSS, 바닐라 JavaScript입니다.", prompt)
        self.assertIn("Tailwind CDN, 외부 폰트, 외부 이미지, 외부 오디오, npm import, ES module CDN import는 사용하지 않습니다.", prompt)

    def test_prompt_includes_material_type_and_starter_specific_rules(self):
        prompt = build_ai_prompt(
            "분수의 크기 비교",
            starter=get_starter("fraction-balance"),
            mission=get_mission("quick-practice"),
        )

        self.assertIn("연습형 자료", prompt)
        self.assertIn("즉시 피드백", prompt)
        self.assertIn("두 분수를 나란히 비교할 수 있는 시각 영역", prompt)
        self.assertIn("분수 막대나 도형", prompt)

    def test_prompt_template_keeps_topic_placeholder_when_topic_is_blank(self):
        prompt = build_ai_prompt(
            "",
            starter=get_starter("debate-canvas"),
            mission=get_mission("discussion-flow"),
        )

        self.assertIn(TOPIC_PLACEHOLDER, prompt)
        self.assertIn("발표형 자료", prompt)
        self.assertIn("코드블록 없이 <!DOCTYPE html>부터 끝까지 이어서 작성합니다.", prompt)
