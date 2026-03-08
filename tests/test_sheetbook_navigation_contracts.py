from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from core.models import UserProfile
from sheetbook.models import SheetTab, Sheetbook


User = get_user_model()


class SheetbookNavigationRegressionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="sheetbook_nav_teacher",
            password="pw123456",
            email="sheetbook_nav_teacher@example.com",
        )
        UserProfile.objects.update_or_create(
            user=self.user,
            defaults={"nickname": "동선교사", "role": "school"},
        )
        self.client.force_login(self.user)

    @override_settings(SHEETBOOK_ENABLED=True)
    def test_detail_back_link_uses_preserved_index_context(self):
        sheetbook = Sheetbook.objects.create(owner=self.user, title="컨텍스트 수첩")
        SheetTab.objects.create(sheetbook=sheetbook, name="일정", tab_type=SheetTab.TYPE_GRID, sort_order=1)

        response = self.client.get(
            reverse("sheetbook:detail", kwargs={"pk": sheetbook.pk}),
            data={
                "source": "workspace_home",
                "index_status": "archived",
                "index_q": "운영",
                "index_page": "2",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'href="{reverse("sheetbook:index")}?q=%EC%9A%B4%EC%98%81&amp;source=workspace_home&amp;status=archived&amp;page=2"',
        )

    @override_settings(SHEETBOOK_ENABLED=True)
    def test_detail_remembers_recent_sheetbook_in_session(self):
        sheetbook = Sheetbook.objects.create(owner=self.user, title="최근 수첩")
        SheetTab.objects.create(sheetbook=sheetbook, name="일정", tab_type=SheetTab.TYPE_GRID, sort_order=1)

        response = self.client.get(reverse("sheetbook:detail", kwargs={"pk": sheetbook.pk}))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.session.get("sheetbook_recent_sheetbook_id"), sheetbook.id)


class SheetbookUiContractTests(SimpleTestCase):
    def _read(self, relative_path: str) -> str:
        return (Path(settings.BASE_DIR) / relative_path).read_text(encoding="utf-8")

    def test_followup_actions_open_next_screen_contract(self):
        detail = self._read("sheetbook/templates/sheetbook/detail.html")
        grid_editor = self._read("sheetbook/templates/sheetbook/_grid_editor.html")

        self.assertIn('function shouldOpenResultPage(action, invocation)', detail)
        self.assertIn('["consent", "signature", "notice"].includes(action)', detail)
        self.assertIn('동의서 화면 열기', detail)
        self.assertIn('서명 요청 화면 열기', detail)
        self.assertIn('안내문 화면 열기', detail)
        self.assertIn('동의서 화면 열기', grid_editor)
        self.assertIn('서명 요청 화면 열기', grid_editor)
        self.assertIn('안내문 화면 열기', grid_editor)
        self.assertIn('state.previewReturnFocusEl', detail)
        self.assertIn('window.requestAnimationFrame(() => {', detail)

    def test_sheetbook_calendar_links_use_primary_calendar_route(self):
        calendar_tab = self._read("sheetbook/templates/sheetbook/_calendar_tab.html")
        sheetbook_views = self._read("sheetbook/views.py")

        self.assertIn("classcalendar:main", calendar_tab)
        self.assertNotIn("classcalendar:legacy_main", calendar_tab)
        self.assertIn('"result_url": reverse("classcalendar:main")', sheetbook_views)
        self.assertIn("이 표를 달력에 반영", calendar_tab)
        self.assertIn("설정", calendar_tab)
        self.assertNotIn("달력 단독 화면", calendar_tab)
        self.assertNotIn("달력 전체 화면 열기", calendar_tab)
        self.assertIn("sheetbook-calendar-surface", calendar_tab)
        self.assertIn('{% include "classcalendar/_calendar_app.html" %}', calendar_tab)
        self.assertNotIn("달력 연결 설정", calendar_tab)
        self.assertIn("저장", calendar_tab)
        self.assertNotIn("수첩으로 돌아올 때", calendar_tab)
        self.assertIn("sheetbook-calendar-message-btn", calendar_tab)
        self.assertIn("메시지 붙여넣기", calendar_tab)
        self.assertIn("sheetbook-calendar-create-btn", calendar_tab)
        self.assertIn("새 일정", calendar_tab)
        self.assertIn("sheetbook-calendar-sync-summary", calendar_tab)
        self.assertNotIn("휴대폰에서는 일정 확인과 일정 1건 추가만 할 수 있어요.", calendar_tab)
        self.assertIn("disabled aria-disabled=\"true\"", calendar_tab)
        self.assertIn('currentStatus.includes("불러오는 중")', self._read("sheetbook/templates/sheetbook/detail.html"))

    def test_calendar_admin_tools_are_secondary_and_collapsed(self):
        calendar_app = self._read("classcalendar/templates/classcalendar/_calendar_app.html")

        self.assertIn('data-calendar-admin-tools="1"', calendar_app)
        self.assertIn("공유·협업·연동", calendar_app)
        self.assertNotIn("링크를 아는 사람은 로그인 없이 읽기 전용으로 달력을 볼 수 있습니다.", calendar_app)
        self.assertNotIn("협업자는 가입시 적었던 이메일로만 추가할 수 있습니다.", calendar_app)
        self.assertIn("가입 이메일", calendar_app)

    def test_action_layer_contract_allows_single_cell_selection(self):
        detail = self._read("sheetbook/templates/sheetbook/detail.html")
        grid_editor = self._read("sheetbook/templates/sheetbook/_grid_editor.html")

        self.assertIn("if (!bounds || bounds.count <= 0)", detail)
        self.assertIn("buildSelectionRangeText(bounds)", detail)
        self.assertIn("칸 선택", detail)
        self.assertIn("els.actionLayer.classList.remove(\"hidden\")", detail)
        self.assertIn('role="dialog"', grid_editor)
        self.assertIn('aria-modal="true"', grid_editor)
        self.assertIn('aria-live="polite"', grid_editor)

    def test_grid_editor_prioritizes_compact_toolbar_and_removes_button_legend(self):
        grid_editor = self._read("sheetbook/templates/sheetbook/_grid_editor.html")

        self.assertNotIn("이 화면에서 가장 많이 하는 일", grid_editor)
        self.assertNotIn("진한 버튼은 바로 만들기, 테두리 버튼은 다음 화면 열기입니다.", grid_editor)
        self.assertNotIn("진한 버튼: 바로 만들기", grid_editor)
        self.assertNotIn("테두리 버튼: 다음 화면 열기", grid_editor)
        self.assertIn('data-action-group="immediate"', grid_editor)
        self.assertIn('data-action-group="followup"', grid_editor)
        self.assertNotIn("지금 할 수 있는 일", grid_editor)
        self.assertNotIn("태블릿이나 PC에서 이어서 할 일", grid_editor)
        self.assertNotIn("휴대폰에서는 범위 실행 대신 칸 수정과 줄/항목 정리까지만 할 수 있어요.", grid_editor)
        self.assertNotIn("휴대폰 간단 편집", grid_editor)
        self.assertIn("PC/태블릿에서 실행할 수 있어요.", grid_editor)
        self.assertNotIn("엑셀이나 표 파일을 한 번에 불러오거나 내려받을 수 있어요.", grid_editor)
        self.assertIn("grid-mobile-column-panel", grid_editor)
        self.assertIn("보기 저장", grid_editor)
        self.assertIn("현재 보기 적용", grid_editor)
        self.assertIn("전체 보기", grid_editor)
        self.assertIn("배부 체크 바로 만들기", grid_editor)
        self.assertIn("방금 만든 결과 다시 보기", grid_editor)
        self.assertIn("이전 결과 더보기", grid_editor)
        self.assertIn('id="grid-add-row-btn"', grid_editor)
        self.assertIn('id="grid-add-column-quick-btn"', grid_editor)

    def test_grid_detail_keeps_inline_row_and_column_controls_contract(self):
        detail = self._read("sheetbook/templates/sheetbook/detail.html")

        self.assertIn('data-grid-row-add="1"', detail)
        self.assertIn('data-grid-row-delete="1"', detail)
        self.assertIn('data-grid-column-add-left="1"', detail)
        self.assertIn('data-grid-column-add-right="1"', detail)
        self.assertIn('data-grid-column-delete="1"', detail)
        self.assertIn('data-column-rename-input="${column.id}"', detail)
        self.assertIn('showUndoAction("row"', detail)
        self.assertIn('showUndoAction("column"', detail)
        self.assertIn('restoreLastStructureChange', detail)
        self.assertIn('window.sheetbookCalendarBridge', detail)
        self.assertIn('classcalendar:ready', detail)
        self.assertIn('classcalendar:action-opened', detail)
        self.assertIn('classcalendar:event-saved', detail)

    def test_classcalendar_embedded_view_provides_local_toast_bridge(self):
        main_template = self._read("classcalendar/templates/classcalendar/main.html")
        app_template = self._read("classcalendar/templates/classcalendar/_calendar_app.html")

        self.assertIn('{% include "classcalendar/_calendar_app.html" %}', main_template)
        self.assertIn('id="calendar-toast-root"', app_template)
        self.assertIn('function ensureCalendarToastBridge()', app_template)
        self.assertIn("typeof window.showToast === 'function'", app_template)
        self.assertIn("window.showToast = function(message, tone = 'info')", app_template)
