from django.test import SimpleTestCase

from bamboo.utils.prompts import FEW_SHOT_MESSAGES, SYSTEM_PROMPT, build_messages
from bamboo.utils.validator import validate_fable_output


class BambooPromptSmokeTest(SimpleTestCase):
    def test_messages_include_few_shots_and_masked_input(self):
        messages = build_messages("[●●●] 때문에 화난다.")

        self.assertGreaterEqual(len(messages), 6)
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(FEW_SHOT_MESSAGES[0]["role"], "user")
        self.assertIn("[●●●] 때문에 화난다.", messages[-1]["content"])

    def test_system_prompt_uses_indirect_satire_without_targeting_regions(self):
        self.assertIn("충청도식 완곡어법", SYSTEM_PROMPT)
        self.assertIn("능청스럽게 돌려 말", SYSTEM_PROMPT)
        self.assertIn("실제 지역명이나 지역 사람을 소재로 삼지 않는다", SYSTEM_PROMPT)

    def test_fixture_output_passes_validator_without_llm(self):
        fixture = """## 제목: <시끄러운 까마귀의 빈 둥지 우화>

        어느 깊은 숲에 작은 잎사귀 하나에도 북을 치는 까마귀가 있었습니다.
        까마귀는 자기 둥지가 흔들린다며 밤마다 달빛을 깨웠고, 묵묵한 부엉이는 졸린 눈으로 가지를 살폈습니다.
        하지만 숲의 버섯들은 그 소리가 클수록 알맹이는 깃털 한 올뿐이라는 걸 알아챘습니다.
        부엉이는 더 단단한 가지에 앉아 필요한 말만 남겼고, 까마귀의 메아리는 스스로에게 되돌아갔습니다.
        새벽이 오자 숲은 조용히 숨을 골랐고, 부엉이의 눈빛은 다시 맑아졌습니다.

        > 숲의 속삭임: 너는 충분히 차분히 버텼어요. 이제 숨을 돌려도 됩니다."""

        self.assertTrue(validate_fable_output(fixture, raw_input="학부모 민원이 힘들다.").is_valid)
