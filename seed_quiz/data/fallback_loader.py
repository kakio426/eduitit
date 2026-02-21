import json
import random
from pathlib import Path

DATA_FILE = Path(__file__).parent / "fallback_quizzes_v1.json"

FALLBACK_SOURCE_BY_TOPIC = {
    "orthography": "korean",
    "spacing": "korean",
    "vocabulary": "korean",
    "proverb": "korean",
    "idiom": "korean",
    "sino_idiom": "korean",
    "hanja_word": "korean",
    "main_sentence": "korean",
    "sentence_order": "korean",
    "topic_title": "korean",
    "fact_opinion": "social",
    "eng_vocab": "english",
    "eng_sentence": "english",
    "eng_cloze": "english",
    "arithmetic": "math",
    "pattern": "math",
    "fraction_decimal": "math",
    "time_calendar": "math",
    "unit_conversion": "math",
    "safety_common": "general",
}


def load_fallback_bank(preset_type: str, grade: int) -> dict:
    with open(DATA_FILE, encoding="utf-8") as f:
        bank = json.load(f)

    quizzes = bank.get("quizzes", {})
    source_type = FALLBACK_SOURCE_BY_TOPIC.get(preset_type, preset_type)

    # preset_type → grade 세트 탐색
    sets = quizzes.get(source_type, {}).get(str(grade), [])

    # 빈 배열이면 general로 fallback
    if not sets:
        sets = quizzes.get("general", {}).get(str(grade), [])

    # general도 없으면 어떤 학년이든 첫 번째 세트
    if not sets:
        for g in ["3", "4", "5", "6"]:
            sets = quizzes.get("general", {}).get(g, [])
            if sets:
                break

    if not sets:
        raise FileNotFoundError(
            f"폴백 퀴즈를 찾을 수 없습니다. preset={preset_type}, source={source_type}, grade={grade}"
        )

    return random.choice(sets)
