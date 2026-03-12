import json
from unittest.mock import patch

from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from fortune.models import FortuneResult
from fortune.views_chat import _select_prior_general_results

User = get_user_model()


def _stringify_streaming_response(response):
    async def collect():
        chunks = []
        async for chunk in response.streaming_content:
            chunks.append(chunk.decode() if isinstance(chunk, bytes) else chunk)
        return "".join(chunks)

    return async_to_sync(collect)()


class TestChatViews(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='password',
            email='test@example.com',
        )
        self.assertTrue(self.client.login(username='testuser', password='password'))
        self.create_url = reverse('fortune:create_chat_session')
        self.send_url = reverse('fortune:send_chat_message')
        self.save_url = reverse('fortune:save_chat_to_history')
        self.working_context = {
            'display_name': '테스트선생님',
            'gender': 'female',
            'mode': 'teacher',
            'day_master': {'char': '丙', 'element': 'fire'},
            'natal_chart': {
                'year': {'stem': '甲', 'branch': '子'},
                'month': {'stem': '乙', 'branch': '丑'},
                'day': {'stem': '丙', 'branch': '寅'},
                'hour': {'stem': '丁', 'branch': '卯'},
            },
        }

    def test_create_session_returns_gone_for_removed_profile_flow(self):
        response = self.client.post(self.create_url, {'profile_id': 1}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

        self.assertEqual(response.status_code, 410)
        self.assertIn('저장 프로필 기반 채팅은 종료되었습니다', response.json()['error'])

    def test_send_message_requires_working_context(self):
        response = self.client.post(
            self.send_url,
            {'message': '안녕하세요'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], 'WORKING_CONTEXT_REQUIRED')

    @patch('fortune.views_chat.is_ratelimited', return_value=False)
    def test_send_message_streams_response_without_db_chat_session(self, _mock_ratelimit):
        async def fake_stream(system_prompt, history, user_message):
            self.assertIn('User Label: 선생님', system_prompt)
            self.assertNotIn('테스트선생님', system_prompt)
            self.assertEqual(history, [])
            self.assertEqual(user_message, '안녕하세요')
            yield {'html': '<p>첫 답변</p>', 'plain': '첫 답변'}
            yield {'html': '<p>두 번째</p>', 'plain': '두 번째'}

        with patch('fortune.views_chat.get_ai_response_stream', new=fake_stream):
            response = self.client.post(
                self.send_url,
                {
                    'message': '안녕하세요',
                    'working_context_json': json.dumps(self.working_context, ensure_ascii=False),
                    'history_json': json.dumps([], ensure_ascii=False),
                },
                HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            )
            content = _stringify_streaming_response(response)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.streaming)
        self.assertIn('<p>첫 답변</p>', content)
        self.assertIn('window.FortuneChat.recordExchange', content)
        self.assertEqual(FortuneResult.objects.count(), 0)

    def test_send_message_returns_limit_notice_after_ten_turns(self):
        history = [{'role': 'user', 'content': f'질문 {idx}'} for idx in range(10)]

        response = self.client.post(
            self.send_url,
            {
                'message': '추가 질문',
                'working_context_json': json.dumps(self.working_context, ensure_ascii=False),
                'history_json': json.dumps(history, ensure_ascii=False),
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '오늘 상담 한도를 모두 사용했습니다')

    def test_save_chat_scrubs_birth_like_text_and_stores_result_only(self):
        history = [
            {'role': 'user', 'content': '제 생일은 1990-01-01 13:00인가요?'},
            {'role': 'assistant', 'content': '생일: 1990년 1월 1일 13시 기준으로 보입니다.'},
        ]

        response = self.client.post(
            self.save_url,
            {
                'working_context_json': json.dumps(self.working_context, ensure_ascii=False),
                'history_json': json.dumps(history, ensure_ascii=False),
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        saved = FortuneResult.objects.get(user=self.user)
        self.assertIn('[비공개]', saved.result_text)
        self.assertNotIn('1990-01-01', saved.result_text)
        self.assertNotIn('1990년 1월 1일 13시', saved.result_text)
        self.assertNotIn('테스트선생님', saved.result_text)

    def test_select_prior_general_results_returns_latest_general_only(self):
        FortuneResult.objects.create(
            user=self.user,
            mode='teacher',
            result_text='teacher result should not be included',
        )
        older = FortuneResult.objects.create(
            user=self.user,
            mode='general',
            result_text='older general result',
        )
        newer = FortuneResult.objects.create(
            user=self.user,
            mode='general',
            result_text='newer general result',
        )

        results = _select_prior_general_results(self.user, limit=2)

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]['id'], newer.id)
        self.assertEqual(results[1]['id'], older.id)
