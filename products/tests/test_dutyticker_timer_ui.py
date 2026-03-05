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
        self.assertContains(response, 'id="timerAddMinuteBtn"')
        self.assertContains(response, 'id="timerPreset5Btn"')
        self.assertContains(response, 'id="timerPreset10Btn"')
        self.assertContains(response, 'id="timerCustomApplyBtn"')
        self.assertContains(response, 'id="timerResetBtn"')
        self.assertContains(response, 'id="roleResetAssignmentsBtn"')
        self.assertContains(response, 'window.dtApp.resetRoleAssignments()')
        self.assertNotContains(response, 'id="roleRotateNowBtn"')
        self.assertContains(response, 'title="별빛 추첨기"')
        self.assertContains(response, reverse('ppobgi:main'))
        self.assertContains(response, 'id="mainMissionTitle" contenteditable="true"')
        self.assertContains(response, 'id="mainMissionDesc" contenteditable="true"')
        self.assertContains(response, 'window.dtApp.changeMissionFontSize(-1)')
        self.assertContains(response, 'id="missionFontSizeLabel"')
        self.assertContains(response, 'id="missionQuickSaveBtn"')
        self.assertContains(response, 'id="missionQuickApplyBtn"')
        self.assertContains(response, 'id="randomDrawName"')
        self.assertContains(response, 'id="randomDrawBtn"')
        self.assertContains(response, 'id="randomDrawResetBtn"')
        self.assertContains(response, 'window.dtApp.drawRandomStudent()')
        self.assertContains(response, 'window.dtApp.resetRandomPicker()')
        self.assertContains(response, 'id="bgmControls"')
        self.assertContains(response, 'id="bgmToggleBtn"')
        self.assertContains(response, 'id="bgmLoopModeBtn"')
        self.assertContains(response, 'id="bgmTrackRail"')
        self.assertContains(response, 'id="bgmVolumeRange"')
        self.assertContains(response, 'id="bgmVolumeValue"')
        self.assertContains(response, 'window.dtBgmTracks = {')
        self.assertNotContains(response, '천리 길도 한 걸음부터')

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
        self.assertIn("bindButtonAction('timerPreset5Btn'", script)
        self.assertIn('this.timerMaxSeconds = 300;', script)
        self.assertIn('this.timerSeconds = 300;', script)
        self.assertIn('syncRandomPickerStudents()', script)
        self.assertIn('renderRandomPicker()', script)
        self.assertIn('drawRandomStudent()', script)
        self.assertIn('resetRandomPicker()', script)
        self.assertIn('resetRoleAssignments()', script)
        self.assertIn("this.getApiUrl('resetAssignmentsUrl'", script)
        self.assertIn('dt-bgm-state-v1', script)
        self.assertIn('bgmVolumePercent', script)
        self.assertIn('setupBgm()', script)
        self.assertIn('setBgmVolumePercent(', script)
        self.assertIn('toggleBgmLoopMode()', script)
        self.assertIn('renderBgmTrackRail()', script)
        self.assertIn('nextBgmTrack(', script)
        self.assertIn('prevBgmTrack(', script)
        self.assertIn('setupInlineMissionEditor()', script)
        self.assertIn('saveInlineMissionEdit()', script)
        self.assertIn('changeMissionFontSize(', script)
        self.assertIn("this.missionFontSizeOrder = ['xxs', 'xs', 'sm', 'md', 'lg', 'xl', 'xxl'];", script)
        self.assertIn('dt-mission-quick-phrase-v1', script)
        self.assertIn('restoreMissionQuickPhrase()', script)
        self.assertIn('applyMissionQuickPhrase()', script)
        self.assertIn('다음 교시 10분 전부터 표시됩니다', script)

