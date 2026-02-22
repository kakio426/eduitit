from pathlib import Path

from django.conf import settings
from django.test import Client, TestCase
from django.urls import reverse


class DutyTickerTimerUiTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_dutyticker_page_renders_minute_step_timer_controls(self):
        response = self.client.get(reverse('dutyticker'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'products/dutyticker/main.html')

        self.assertContains(response, 'id="customTimerMinutesInput"')
        self.assertContains(response, 'max="999"')
        self.assertContains(response, 'step="1"')
        self.assertContains(response, 'id="mainTimerDisplay" type="button"')
        self.assertContains(response, 'window.dtApp.addTimerMinutes(1)')
        self.assertContains(response, 'window.dtApp.applyCustomTimerMinutes()')
        self.assertContains(response, 'window.dtApp.setTimerMode(300, true)')
        self.assertContains(response, 'title="별빛 추첨기"')
        self.assertContains(response, reverse('ppobgi:main'))

    def test_timer_script_contains_safety_and_restore_methods(self):
        script_path = Path(settings.BASE_DIR) / 'products' / 'static' / 'products' / 'dutyticker' / 'js' / 'dutyticker.js'
        script = script_path.read_text(encoding='utf-8')

        self.assertIn('escapeHtml(value)', script)
        self.assertIn('timerStorageKey', script)
        self.assertIn('normalizeTimerSeconds(', script)
        self.assertIn('saveTimerState()', script)
        self.assertIn('restoreTimerState()', script)
        self.assertIn('Math.min(999', script)
        self.assertIn("display.setAttribute('aria-pressed'", script)
