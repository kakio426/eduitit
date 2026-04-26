from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.conf import settings
from django.test import RequestFactory, TestCase

from core.home_agent_registry import (
    get_home_agent_service_definition,
    get_home_agent_service_definitions,
    resolve_home_agent_conversation_actions,
    resolve_home_agent_starter_items,
    resolve_home_agent_ui_options,
)
from core.home_agent_service_bridge import (
    HOME_AGENT_EXECUTE_ADAPTERS,
    HOME_AGENT_PREVIEW_ADAPTERS,
)
from reservations.models import School, SchoolConfig, SpecialRoom


User = get_user_model()


class HomeAgentRegistryTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username='agentregistry', password='pw12345!')

    def _request(self):
        request = self.factory.get('/')
        request.user = self.user
        return request

    def test_service_definitions_expose_required_contract_fields(self):
        definitions = get_home_agent_service_definitions()

        self.assertEqual(len(definitions), 7)
        for definition in definitions:
            self.assertTrue(definition.key)
            self.assertTrue(definition.label)
            self.assertTrue(definition.renderer_key)
            self.assertTrue(definition.adapter_key)
            self.assertTrue(definition.starter_provider_key)
            self.assertTrue(definition.messenger_flow_key)
            self.assertIsInstance(definition.copy, dict)
            self.assertIsInstance(definition.messenger_capabilities, dict)
            self.assertIsInstance(definition.messenger_ui, dict)
            self.assertIsInstance(definition.links, dict)
            self.assertIsInstance(definition.capabilities, dict)
            self.assertIsInstance(resolve_home_agent_starter_items(definition), list)

    def test_service_preview_and_execute_modes_are_backed_by_adapter_registries(self):
        for definition in get_home_agent_service_definitions():
            if definition.preview_strategy == 'service':
                self.assertIn(definition.adapter_key, HOME_AGENT_PREVIEW_ADAPTERS)
            if definition.capabilities.get('execute'):
                self.assertIn(definition.adapter_key, HOME_AGENT_EXECUTE_ADAPTERS)

    def test_reservation_starter_items_use_school_data_and_disambiguate_duplicate_room_names(self):
        school_one = School.objects.create(name='한빛초', owner=self.user)
        school_two = School.objects.create(name='가람초', owner=self.user)
        SchoolConfig.objects.get_or_create(school=school_one)
        SchoolConfig.objects.get_or_create(school=school_two)
        SpecialRoom.objects.create(school=school_one, name='과학실')
        SpecialRoom.objects.create(school=school_two, name='과학실')
        SpecialRoom.objects.create(school=school_one, name='음악실')

        definition = get_home_agent_service_definition('reservation')
        starter_items = resolve_home_agent_starter_items(definition, request=self._request())
        labels = [item['label'] for item in starter_items]
        texts = [item['text'] for item in starter_items]

        self.assertIn('한빛초 과학실', labels)
        self.assertIn('가람초 과학실', labels)
        self.assertIn('음악실', labels)
        self.assertTrue(all('예약해줘' in text for text in texts))

        ui_options = resolve_home_agent_ui_options(definition, request=self._request())
        self.assertIn('room_names', ui_options)
        self.assertIn('과학실', ui_options['room_names'])
        self.assertIn('음악실', ui_options['room_names'])
        self.assertIn('school_names', ui_options)
        self.assertIn('한빛초', ui_options['school_names'])
        self.assertIn('가람초', ui_options['school_names'])

    def test_teacher_law_provider_supplies_quick_questions_and_ui_options(self):
        definition = get_home_agent_service_definition('teacher-law')

        starter_items = resolve_home_agent_starter_items(definition, request=self._request())
        ui_options = resolve_home_agent_ui_options(definition, request=self._request())

        self.assertTrue(starter_items)
        self.assertTrue(all(item['text'] for item in starter_items))
        self.assertIn('incident_options', ui_options)
        self.assertIn('legal_goal_options', ui_options)
        self.assertIn('scene_options', ui_options)
        self.assertIn('counterpart_options', ui_options)

    def test_notice_provider_includes_server_daily_recommendation_action(self):
        definition = get_home_agent_service_definition('notice')

        starter_items = resolve_home_agent_starter_items(definition, request=self._request())

        self.assertTrue(starter_items)
        self.assertEqual(starter_items[0]["label"], "오늘 추천")
        self.assertEqual(starter_items[0]["action"], "daily_notice_recommendation")
        self.assertEqual(starter_items[0]["endpoint"], "/noticegen/daily-recommendation/")

    def test_notice_daily_recommendation_js_has_failure_feedback(self):
        script_path = Path(settings.BASE_DIR) / 'core/static/core/js/home_authenticated_v6.js'
        script = script_path.read_text(encoding='utf-8')

        self.assertIn('오늘 추천을 불러오지 못했습니다.', script)

    def test_conversation_actions_are_resolved_from_registry_contract(self):
        shared_actions = resolve_home_agent_conversation_actions('shared')
        dm_actions = resolve_home_agent_conversation_actions('dm')
        notice_actions = resolve_home_agent_conversation_actions('notice')

        self.assertEqual([item['mode_key'] for item in shared_actions], ['tts', 'message-save', 'quickdrop'])
        self.assertEqual([item['mode_key'] for item in dm_actions], ['schedule', 'teacher-law', 'reservation', 'quickdrop'])
        self.assertEqual([item['mode_key'] for item in notice_actions], ['notice', 'quickdrop', 'message-save'])
