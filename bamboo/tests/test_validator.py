from django.test import SimpleTestCase

from bamboo.utils.validator import extract_fable_title, validate_fable_output, validate_fable_title


SAFE_FABLE = """## 제목: <허세 공작새의 빈 깃털 우화>

어느 깊은 숲에 남의 둥지에서 가져온 잎사귀를 자기 깃털처럼 펼치는 공작새가 있었습니다.
부지런한 다람쥐는 밤새 모은 도토리를 조용히 바구니에 담았지만, 공작새는 회의 나무 위에서 날개만 크게 흔들었습니다.
숲의 친구들은 처음엔 번쩍이는 깃털에 눈을 빼앗겼지만, 곧 그 깃털 사이로 텅 빈 바람만 새는 걸 들었습니다.
다람쥐는 다음 바구니에 더 단단한 매듭을 묶었고, 도토리 길은 누가 봐도 다람쥐의 발자국으로 반짝였습니다.
공작새는 끝까지 우쭐댔지만, 숲은 빈 깃털보다 묵직한 도토리 소리를 더 오래 기억했습니다.

> 숲의 속삭임: 네가 한 일은 사라지지 않아요. 조용한 발자국도 숲에는 남습니다."""


class BambooValidatorTest(SimpleTestCase):
    def test_accepts_animal_fable(self):
        result = validate_fable_output(SAFE_FABLE, raw_input="관리자가 내 공을 가져갔다.")

        self.assertTrue(result.is_valid)
        self.assertEqual(extract_fable_title(SAFE_FABLE), "허세 공작새의 빈 깃털 우화")

    def test_rejects_school_name(self):
        result = validate_fable_output(
            SAFE_FABLE + "\n서울새싹초등학교에서 있었던 일입니다.",
            raw_input="서울새싹초등학교 관리자 때문에 힘들다.",
            redacted_values=("서울새싹초등학교",),
        )

        self.assertFalse(result.is_valid)
        self.assertIn("school_pattern", result.reasons)

    def test_rejects_person_title_pattern(self):
        result = validate_fable_output(SAFE_FABLE + "\n김철수 선생님이 떠올랐습니다.")

        self.assertFalse(result.is_valid)
        self.assertIn("person_pattern", result.reasons)

    def test_rejects_threat_words(self):
        result = validate_fable_output(SAFE_FABLE.replace("더 오래 기억했습니다", "죽이고 싶다고 외쳤습니다"))

        self.assertFalse(result.is_valid)
        self.assertIn("threat_pattern", result.reasons)

    def test_rejects_unsafe_title(self):
        result = validate_fable_title("김철수 선생님의 참교육 우화")

        self.assertFalse(result.is_valid)
        self.assertIn("person_pattern", result.reasons)
