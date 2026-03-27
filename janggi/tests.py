from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase, TestCase
from django.urls import reverse


class JanggiViewTests(TestCase):
    def test_play_ai_mode_uses_clean_ai_copy(self):
        response = self.client.get(reverse("janggi:play"), {"mode": "ai"})

        self.assertContains(response, "AI 장기 대전")
        self.assertContains(response, "브라우저에서 바로 AI가 다음 수를 둡니다.")
        self.assertContains(response, "브라우저에서 바로 AI가 응수하므로 같은 화면에서 자연스럽게 이어집니다.")
        self.assertContains(response, 'id="turnIndicator"', html=False)
        self.assertContains(response, "지금 둘 차례")
        self.assertContains(response, 'id="turnRedSide"', html=False)
        self.assertContains(response, 'id="turnBlueSide"', html=False)
        self.assertNotContains(response, "로컬 AI")

    def test_index_ai_card_does_not_call_out_local_ai(self):
        response = self.client.get(reverse("janggi:index"))

        self.assertContains(response, "로컬 대전과 AI 대전을 한 화면에서 바로 시작합니다.")
        self.assertContains(response, "브라우저에서 바로 AI가 수를 계산해 자연스럽게 대전을 이어 갑니다.")
        self.assertNotContains(response, "로컬 AI")


class JanggiStaticScriptTests(SimpleTestCase):
    def test_board_script_renders_piece_markup_and_silences_ai_mode_toast(self):
        script_path = Path(settings.BASE_DIR) / "janggi" / "static" / "janggi" / "js" / "janggi_board.js"
        script = script_path.read_text(encoding="utf-8")

        self.assertIn("piece-side-badge", script)
        self.assertIn("piece-glyph", script)
        self.assertIn("piece-name", script)
        self.assertIn("updateTurnUI()", script)
        self.assertIn("turn-ended", script)
        self.assertIn("turnRedSide", script)
        self.assertIn("applyLocalAiMove();", script)
        self.assertNotIn("현재 모드는 로컬 AI로 진행됩니다.", script)
