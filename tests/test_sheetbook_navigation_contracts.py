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
        self.assertIn("이 표를 학급 달력에 반영", calendar_tab)
        self.assertIn("학급 달력 전체 화면 열기", calendar_tab)
        self.assertIn("이 날짜에 일정 바로 넣기", calendar_tab)
        self.assertIn("달력 연결 설정", calendar_tab)
        self.assertIn("연결 저장", calendar_tab)
        self.assertIn("휴대폰에서는 일정 확인과 직접 일정 넣기는 가능해요.", calendar_tab)
        self.assertIn("disabled aria-disabled=\"true\"", calendar_tab)

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

    def test_grid_editor_surfaces_teacher_workflow_and_button_meaning(self):
        grid_editor = self._read("sheetbook/templates/sheetbook/_grid_editor.html")

        self.assertIn("이 화면에서 가장 많이 하는 일", grid_editor)
        self.assertIn("진한 버튼은 바로 만들기, 테두리 버튼은 다음 화면 열기입니다.", grid_editor)
        self.assertIn("진한 버튼: 바로 만들기", grid_editor)
        self.assertIn("테두리 버튼: 다음 화면 열기", grid_editor)
        self.assertIn('data-action-group="immediate"', grid_editor)
        self.assertIn('data-action-group="followup"', grid_editor)
        self.assertIn("지금 할 수 있는 일", grid_editor)
        self.assertIn("태블릿이나 PC에서 이어서 할 일", grid_editor)
        self.assertIn("휴대폰에서는 범위 확인까지만 할 수 있어요.", grid_editor)
        self.assertIn("자주 보는 화면", grid_editor)
        self.assertIn("이 화면으로 보기", grid_editor)
        self.assertIn("다시 전체 보기", grid_editor)
        self.assertIn("배부 체크 바로 만들기", grid_editor)
        self.assertIn("방금 만든 결과 다시 보기", grid_editor)
        self.assertIn("이전 결과 더보기", grid_editor)
