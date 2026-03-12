import json
from unittest.mock import AsyncMock, patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from fortune.models import Branch, FortunePseudonymousCache, FortuneResult, Stem

User = get_user_model()


class IntegrationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='password')
        self.other_user = User.objects.create_user(username='otheruser', password='password')
        self.form_data = {
            'mode': 'teacher',
            'name': '홍길동',
            'gender': 'male',
            'birth_year': '1990',
            'birth_month': '5',
            'birth_day': '5',
            'birth_hour': '14',
            'birth_minute': '30',
            'calendar_type': 'solar',
        }
        self.chart_context = self._build_chart_context()

    def _build_chart_context(self):
        stems = {
            '甲': Stem.objects.create(name='Gap', character='甲', polarity='yang', element='wood'),
            '乙': Stem.objects.create(name='Eul', character='乙', polarity='yin', element='wood'),
            '丙': Stem.objects.create(name='Byung', character='丙', polarity='yang', element='fire'),
            '丁': Stem.objects.create(name='Jung', character='丁', polarity='yin', element='fire'),
        }
        branches = {
            '子': Branch.objects.create(name='Ja', character='子', polarity='yang', element='water'),
            '丑': Branch.objects.create(name='Chuk', character='丑', polarity='yin', element='earth'),
            '寅': Branch.objects.create(name='In', character='寅', polarity='yang', element='wood'),
            '卯': Branch.objects.create(name='Myo', character='卯', polarity='yin', element='wood'),
        }
        return {
            'year': {'stem': stems['甲'], 'branch': branches['子']},
            'month': {'stem': stems['乙'], 'branch': branches['丑']},
            'day': {'stem': stems['丙'], 'branch': branches['寅']},
            'hour': {'stem': stems['丁'], 'branch': branches['卯']},
        }

    def test_same_user_reuses_pseudonymous_cache(self):
        self.assertTrue(self.client.login(username='testuser', password='password'))
        ai_mock = AsyncMock(return_value='요약: 1990년 5월 5일 14시 기준 분석 결과')

        with patch('fortune.views._check_saju_ratelimit', new=AsyncMock(return_value=False)), \
             patch('fortune.views.get_chart_context', return_value=self.chart_context), \
             patch('fortune.views.get_prompt', return_value='PROMPT'), \
             patch('fortune.views._collect_ai_response_async', new=ai_mock):
            first = self.client.post(reverse('fortune:saju_api'), self.form_data)
            second = self.client.post(reverse('fortune:saju_api'), self.form_data)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(ai_mock.await_count, 1)
        cache_entry = FortunePseudonymousCache.objects.get(user=self.user, purpose='full')
        self.assertEqual(len(cache_entry.fingerprint), 64)
        self.assertIn('[비공개]', cache_entry.result_text)
        self.assertNotIn('1990년 5월 5일 14시', cache_entry.result_text)

    def test_different_users_do_not_share_same_birth_cache(self):
        ai_mock = AsyncMock(return_value='공통 입력이지만 사용자별로 따로 캐시되어야 합니다.')

        with patch('fortune.views._check_saju_ratelimit', new=AsyncMock(return_value=False)), \
             patch('fortune.views.get_chart_context', return_value=self.chart_context), \
             patch('fortune.views.get_prompt', return_value='PROMPT'), \
             patch('fortune.views._collect_ai_response_async', new=ai_mock):
            self.assertTrue(self.client.login(username='testuser', password='password'))
            first = self.client.post(reverse('fortune:saju_api'), self.form_data)
            self.client.logout()
            self.assertTrue(self.client.login(username='otheruser', password='password'))
            second = self.client.post(reverse('fortune:saju_api'), self.form_data)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(ai_mock.await_count, 2)
        self.assertEqual(FortunePseudonymousCache.objects.filter(purpose='full').count(), 2)

    def test_save_fortune_api_scrubs_and_stores_without_natal_chart(self):
        self.assertTrue(self.client.login(username='testuser', password='password'))

        response = self.client.post(
            reverse('fortune:save_fortune_api'),
            data=json.dumps({
                'mode': 'teacher',
                'result_text': '생일: 1990년 5월 5일 14시\n사주: 甲子 乙丑 丙寅 丁卯\n요약만 남겨주세요.',
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        saved = FortuneResult.objects.get(user=self.user)
        self.assertEqual(saved.mode, 'teacher')
        self.assertEqual(saved.result_text, '요약만 남겨주세요.')
