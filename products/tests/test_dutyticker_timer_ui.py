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
        self.assertContains(response, 'id="mainMissionTitle" contenteditable="true"')
        self.assertContains(response, 'id="mainMissionDesc" contenteditable="true"')
        self.assertContains(response, 'window.dtApp.changeMissionFontSize(-1)')
        self.assertContains(response, 'id="missionFontSizeLabel"')
        self.assertContains(response, 'id="randomDrawName"')
        self.assertContains(response, 'id="randomDrawBtn"')
        self.assertContains(response, 'id="randomDrawResetBtn"')
        self.assertContains(response, 'window.dtApp.drawRandomStudent()')
        self.assertContains(response, 'window.dtApp.resetRandomPicker()')
        self.assertContains(response, 'id="bgmControls"')
        self.assertContains(response, 'id="bgmToggleBtn"')
        self.assertContains(response, 'id="bgmLoopModeBtn"')
        self.assertContains(response, 'id="bgmTrackPanelBtn"')
        self.assertContains(response, 'id="bgmTrackRail"')
        self.assertContains(response, 'window.dtBgmTracks = {')
        self.assertContains(response, 'podcast-smooth-jazz-instrumental-music-225674.mp3')
        self.assertNotContains(response, 'jazz_soft_loop.wav')
        self.assertNotContains(response, '천리 길도 한 걸음부터')
        self.assertNotContains(response, '알림사항 없음')
        self.assertNotContains(response, '클릭해서 아이들에게 전달할 공지사항이나 준비물을 입력하세요.')

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
        self.assertIn('syncRandomPickerStudents()', script)
        self.assertIn('renderRandomPicker()', script)
        self.assertIn('drawRandomStudent()', script)
        self.assertIn('resetRandomPicker()', script)
        self.assertIn('dt-bgm-state-v1', script)
        self.assertIn('setupBgm()', script)
        self.assertIn('toggleBgmLoopMode()', script)
        self.assertIn('toggleBgmTrackPanel(', script)
        self.assertIn('renderBgmTrackRail()', script)
        self.assertIn('nextBgmTrack(', script)
        self.assertIn('prevBgmTrack(', script)
        self.assertIn('setupInlineMissionEditor()', script)
        self.assertIn('saveInlineMissionEdit()', script)
        self.assertIn('changeMissionFontSize(', script)
