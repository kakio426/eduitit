import os
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from core.home_agent_runtime import generate_home_agent_preview, resolve_home_agent_provider


class HomeAgentRuntimeTest(SimpleTestCase):
    @patch.dict(
        os.environ,
        {
            'HOME_AGENT_LLM_PROVIDER': 'deepseek',
            'HOME_AGENT_LLM_FALLBACK_PROVIDER': 'openclaw',
            'OPENCLAW_BASE_URL': 'http://127.0.0.1:11434',
        },
        clear=True,
    )
    def test_resolve_home_agent_provider_falls_back_to_openclaw(self):
        config = resolve_home_agent_provider()

        self.assertEqual(config.provider, 'openclaw')
        self.assertEqual(config.base_url, 'http://127.0.0.1:11434/v1')
        self.assertEqual(config.api_key, 'openclaw-local')

    @patch('core.home_agent_runtime.OpenAI')
    @patch.dict(
        os.environ,
        {
            'HOME_AGENT_LLM_PROVIDER': 'deepseek',
            'MASTER_DEEPSEEK_API_KEY': 'deepseek-test-key',
        },
        clear=True,
    )
    def test_generate_home_agent_preview_uses_deepseek_json_preview(self, mock_openai):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content=(
                        '{"title":"알림장 초안","summary":"준비물과 시간을 먼저 정리했습니다.",'
                        '"sections":[{"title":"핵심","items":["준비물 안내","시간 변경"]}],'
                        '"note":"보내기 전에 말투만 확인하면 됩니다."}'
                    )
                )
            )
        ]
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client

        result = generate_home_agent_preview(
            mode_key='notice',
            text='내일 준비물은 색연필입니다. 하교는 10분 늦습니다.',
            selected_date_label='4월 15일',
            context={
                'service_key': 'noticegen',
                'workflow_keys': ['daily_notice_flow'],
                'tacit_rule_keys': ['notice_priority_order'],
                'context_questions': ['준비물 누락 학생이 있는가'],
            },
        )

        self.assertEqual(result['provider'], 'deepseek')
        self.assertEqual(result['model'], 'deepseek-chat')
        self.assertEqual(result['preview']['badge'], '알림장')
        self.assertEqual(result['preview']['title'], '알림장 초안')
        self.assertEqual(result['preview']['sections'][0]['title'], '핵심')

        mock_openai.assert_called_once_with(
            api_key='deepseek-test-key',
            base_url='https://api.deepseek.com',
            timeout=35.0,
        )
        create_call = mock_client.chat.completions.create.call_args
        self.assertEqual(create_call.kwargs['response_format'], {'type': 'json_object'})
        self.assertIn('daily_notice_flow', create_call.kwargs['messages'][1]['content'])
        self.assertIn('notice_priority_order', create_call.kwargs['messages'][1]['content'])

    @patch('core.home_agent_runtime.OpenAI')
    @patch.dict(
        os.environ,
        {
            'HOME_AGENT_LLM_PROVIDER': 'deepseek',
            'HOME_AGENT_LLM_FALLBACK_PROVIDER': 'openclaw',
            'MASTER_DEEPSEEK_API_KEY': 'deepseek-test-key',
            'OPENCLAW_BASE_URL': 'http://127.0.0.1:11434',
            'OPENCLAW_MODEL': 'openclaw-local-model',
        },
        clear=True,
    )
    def test_generate_home_agent_preview_falls_back_to_openclaw_when_deepseek_call_fails(self, mock_openai):
        deepseek_client_first = MagicMock()
        deepseek_client_first.chat.completions.create.side_effect = RuntimeError('deepseek boom')

        deepseek_client_second = MagicMock()
        deepseek_client_second.chat.completions.create.side_effect = RuntimeError('deepseek boom')

        openclaw_client = MagicMock()
        openclaw_response = MagicMock()
        openclaw_response.choices = [
            MagicMock(
                message=MagicMock(
                    content=(
                        '{"title":"예약 요청 후보","summary":"과학실 예약 초안을 정리했습니다.",'
                        '"sections":[{"title":"예약 값","items":["4월 22일 3교시 과학실"]}],'
                        '"note":"예약 저장 전 시간과 장소를 다시 확인하세요."}'
                    )
                )
            )
        ]
        openclaw_client.chat.completions.create.return_value = openclaw_response
        mock_openai.side_effect = [deepseek_client_first, deepseek_client_second, openclaw_client]

        result = generate_home_agent_preview(
            mode_key='reservation',
            text='4월 22일 3교시 과학실 예약',
        )

        self.assertEqual(result['provider'], 'openclaw')
        self.assertEqual(result['model'], 'openclaw-local-model')
        self.assertEqual(result['preview']['title'], '예약 요청 후보')
        self.assertEqual(mock_openai.call_count, 3)
        self.assertEqual(
            mock_openai.call_args_list[2].kwargs,
            {
                'api_key': 'openclaw-local',
                'base_url': 'http://127.0.0.1:11434/v1',
                'timeout': 35.0,
            },
        )
