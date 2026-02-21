from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import UserProfile
from seed_quiz.models import SQQuizBank, SQQuizBankItem
from seed_quiz.services.bank import (
    _normalize_source_text,
    _source_hash,
    generate_bank_from_context_ai,
)

User = get_user_model()


def _make_teacher(username):
    teacher = User.objects.create_user(
        username=username,
        password="pw",
        email=f"{username}@test.com",
    )
    UserProfile.objects.update_or_create(
        user=teacher,
        defaults={"nickname": username, "role": "school"},
    )
    return teacher


class BankServiceTest(TestCase):
    def setUp(self):
        self.teacher = _make_teacher("bank_teacher")

    def test_rag_cache_hit_without_api_key(self):
        source_text = "오늘 수업에서 다룬 지문 핵심 문장입니다. 아이들이 이해하기 쉽게 정리했습니다."
        source_hash = _source_hash(_normalize_source_text(source_text))

        bank = SQQuizBank.objects.create(
            title="[RAG] 3학년 general 맞춤 세트",
            preset_type="general",
            grade=3,
            source="ai",
            source_hash=source_hash,
            created_by=self.teacher,
            quality_status="approved",
            is_active=True,
        )
        SQQuizBankItem.objects.create(
            bank=bank,
            order_no=1,
            question_text="질문 1",
            choices=["A", "B", "C", "D"],
            correct_index=1,
            explanation="해설",
            difficulty="easy",
        )
        SQQuizBankItem.objects.create(
            bank=bank,
            order_no=2,
            question_text="질문 2",
            choices=["A", "B", "C", "D"],
            correct_index=2,
            explanation="해설",
            difficulty="easy",
        )
        SQQuizBankItem.objects.create(
            bank=bank,
            order_no=3,
            question_text="질문 3",
            choices=["A", "B", "C", "D"],
            correct_index=3,
            explanation="해설",
            difficulty="easy",
        )

        with patch.dict("os.environ", {}, clear=True):
            result_bank, cached = generate_bank_from_context_ai(
                preset_type="general",
                grade=3,
                source_text=source_text,
                created_by=self.teacher,
            )

        self.assertTrue(cached)
        self.assertEqual(result_bank.id, bank.id)

    def test_rag_cache_miss_requires_api_key(self):
        source_text = "캐시가 없는 새로운 지문입니다. 이 경우 API 키가 없으면 실패해야 합니다."
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(RuntimeError):
                generate_bank_from_context_ai(
                    preset_type="general",
                    grade=3,
                    source_text=source_text,
                    created_by=self.teacher,
                )
