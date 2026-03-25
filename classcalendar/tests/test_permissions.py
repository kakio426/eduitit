from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from classcalendar.models import CalendarEvent, CalendarMessageCapture, CalendarTask, EventPageBlock
from core.models import UserProfile
from happy_seed.models import HSClassroom
from products.models import Product

User = get_user_model()


class PermissionTest(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(username="teacher", password="pw", email="teacher@example.com")
        self.other_teacher = User.objects.create_user(username="other", password="pw", email="other@example.com")
        self.classroom = HSClassroom.objects.create(
            name="Test Class",
            teacher=self.teacher,
            slug="test-class-123",
        )
        self.client_teacher = Client()
        self.client_teacher.force_login(self.teacher)
        UserProfile.objects.update_or_create(
            user=self.teacher,
            defaults={"nickname": "teacher", "role": "school"},
        )
        session = self.client_teacher.session
        session["active_classroom_source"] = "hs"
        session["active_classroom_id"] = str(self.classroom.id)
        session.save()

    def _create_event(self, title="기존 일정", author=None):
        owner = author or self.teacher
        return CalendarEvent.objects.create(
            title=title,
            classroom=self.classroom,
            author=owner,
            start_time="2026-03-01T10:00:00Z",
            end_time="2026-03-01T11:00:00Z",
            color="indigo",
            visibility=CalendarEvent.VISIBILITY_TEACHER,
        )

    def _create_task(self, title="기존 할 일", author=None):
        owner = author or self.teacher
        return CalendarTask.objects.create(
            title=title,
            classroom=self.classroom,
            author=owner,
            due_at="2026-03-01T10:00:00Z",
            has_time=True,
        )

    def test_teacher_can_create_event(self):
        response = self.client_teacher.post(
            reverse("classcalendar:api_create_event"),
            {
                "title": "Test Event",
                "start_time": "2026-03-01T10:00",
                "end_time": "2026-03-01T11:00",
                "visibility": "class_readonly",
                "color": "indigo",
            },
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["status"], "success")
        event = CalendarEvent.objects.filter(title="Test Event", author=self.teacher).first()
        self.assertIsNotNone(event)
        self.assertEqual(event.visibility, CalendarEvent.VISIBILITY_TEACHER)

    def test_teacher_can_create_event_with_note(self):
        response = self.client_teacher.post(
            reverse("classcalendar:api_create_event"),
            {
                "title": "메모 일정",
                "note": "실험 키트 챙기기\n학생 역할 분배",
                "start_time": "2026-03-02T09:00",
                "end_time": "2026-03-02T10:00",
                "color": "indigo",
            },
        )
        self.assertEqual(response.status_code, 201)
        event = CalendarEvent.objects.filter(title="메모 일정", author=self.teacher).first()
        self.assertIsNotNone(event)
        text_block = event.blocks.filter(block_type="text").first()
        self.assertIsNotNone(text_block)
        self.assertEqual(text_block.content.get("text"), "실험 키트 챙기기\n학생 역할 분배")

    @override_settings(
        FEATURE_MESSAGE_CAPTURE_ENABLED=True,
        FEATURE_MESSAGE_CAPTURE_ITEM_TYPES=True,
    )
    def test_main_view_keeps_calendar_surface_minimal(self):
        response = self.client_teacher.get(reverse("calendar_main"), follow=True)
        content = response.content.decode("utf-8")

        self.assertNotIn("월간 캘린더", content)
        self.assertIn('data-classcalendar-main-view="true"', content)
        self.assertIn('data-classcalendar-embed-mode="home"', content)
        self.assertIn('data-classcalendar-day-modal="true"', content)
        self.assertIn("surfaceAllowsManage: true", content)
        self.assertIn("새 일정", content)
        self.assertIn("오늘", content)
        self.assertIn('x-text="currentMonthText"', content)
        self.assertNotIn("날짜를 누르면 그날 일정과 할 일을 한 화면에서 바로 확인할 수 있습니다.", content)
        self.assertNotIn("열면 바로 수정과 삭제까지 이어집니다.", content)
        self.assertNotIn("이번 범위에서는 조회만 지원합니다.", content)
        self.assertNotIn("안내문에서 일정 찾기", content)
        self.assertNotIn("오늘 메모", content)
        self.assertNotIn("다시 볼 메모", content)
        self.assertNotIn("놓치지 않을 메시지", content)
        self.assertNotIn('x-text="currentMonthSummaryText"', content)
        self.assertNotIn("이날의 항목", content)
        self.assertNotIn('selectedDateSummaryText()', content)
        self.assertNotIn("openMessageHub($event, 'capture', { resetCapture: true })", content)
        self.assertNotIn("안내문이나 메모를 넣으면 날짜 후보를 찾아 저장하고, 나중에 다시 꺼내 볼 수 있습니다.", content)
        self.assertNotIn('<p class="classcalendar-meta-label font-semibold text-slate-500">선택한 날짜</p>', content)

    def test_main_view_day_modal_can_show_connected_items(self):
        response = self.client_teacher.get(reverse("calendar_main"), follow=True)
        content = response.content.decode("utf-8")

        self.assertIn("연결 항목", content)
        self.assertIn("getSelectedDateDirectHubCount()", content)
        self.assertIn("getSelectedDateDirectHubItems()", content)
        self.assertIn("openSelectedDateHubItem(item, $event)", content)

    def test_main_view_day_modal_shows_item_level_status_signals(self):
        response = self.client_teacher.get(reverse("calendar_main"), follow=True)
        content = response.content.decode("utf-8")

        self.assertIn("getEventStatusText(event)", content)
        self.assertIn("getEventStatusBadgeClass(event)", content)
        self.assertIn("getTaskStatusBadgeClass(task)", content)
        self.assertIn("getTaskTitleClass(task)", content)
        self.assertIn("지난 일정", content)
        self.assertIn("기한 지남", content)

    def test_center_view_renders_page_mode_with_agenda_search(self):
        response = self.client_teacher.get(reverse("classcalendar:center"))
        content = response.content.decode("utf-8")
        center_shell = content.split('data-classcalendar-center="true"', 1)[1]
        center_header = center_shell.split('data-classcalendar-agenda-panel="true"', 1)[0]
        agenda_panel = center_shell.split('data-classcalendar-agenda-panel="true"', 1)[1].split(
            'x-show="detailModalOpen"', 1
        )[0]

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["calendar_embed_mode"], "page")
        self.assertEqual(response.context["calendar_center_url"], reverse("classcalendar:center"))
        self.assertIn('data-classcalendar-center="true"', content)
        self.assertIn('data-classcalendar-agenda-panel="true"', content)
        self.assertIn('id="calendar-search"', content)
        self.assertIn("교사용 일정 센터", content)
        self.assertIn("월간 보기와 일정 목록을 한 화면에서 확인하세요.", content)
        self.assertIn("getAgendaScopeHelperText()", agenda_panel)
        self.assertIn("@click.prevent.stop=\"setAgendaScope('today')\"", agenda_panel)
        self.assertIn("@click.prevent.stop=\"setAgendaScope('week')\"", agenda_panel)
        self.assertIn("@click.prevent.stop=\"setAgendaScope('month')\"", agenda_panel)
        self.assertIn("@click.prevent.stop=\"setAgendaScope('upcoming')\"", agenda_panel)
        self.assertIn("@input.debounce.150ms=\"rebuildAgendaSections()\"", agenda_panel)
        self.assertIn("x-if=\"agendaDateSections.length === 0\"", agenda_panel)
        self.assertIn("x-for=\"section in agendaDateSections\"", agenda_panel)
        self.assertIn("agendaDateSections: []", content)
        self.assertIn("rebuildAgendaSections()", content)
        self.assertNotIn("classcalendar-center-kpi-card", center_header)
        self.assertNotIn("보이는 전체 항목", center_header)
        self.assertNotIn("이번 달 개인 할 일", center_header)
        self.assertNotIn("setAgendaKindFilter(", content)
        self.assertNotIn("agendaKindFilter:", content)
        self.assertNotIn("메모 있음", agenda_panel)
        self.assertNotIn("할 일만", agenda_panel)
        self.assertNotIn("x-text=\"`${section.items.length}건`\"", agenda_panel)
        self.assertNotIn("getAgendaItemStatusText(item)", agenda_panel)
        self.assertNotIn("오늘 예정", agenda_panel)
        self.assertNotIn("지난 일정", agenda_panel)
        self.assertNotIn("예정", agenda_panel)
        self.assertNotIn("열기", agenda_panel)

    @override_settings(
        FEATURE_MESSAGE_CAPTURE_ENABLED=True,
        FEATURE_MESSAGE_CAPTURE_ITEM_TYPES=True,
    )
    def test_center_view_keeps_messagebox_link_inside_toolbar(self):
        Product.objects.create(
            title="업무 메시지 보관함",
            description="메시지 보관",
            price=0,
            is_active=True,
            service_type="classroom",
            launch_route_name="messagebox:main",
        )

        response = self.client_teacher.get(reverse("classcalendar:center"))
        content = response.content.decode("utf-8")
        toolbar_shell = content.split('class="classcalendar-main-actions"', 1)[1].split(
            'class="grid grid-cols-7', 1
        )[0]

        self.assertIn("업무 메시지 보관함", toolbar_shell)
        self.assertNotIn('class="mt-2 flex justify-end"', content)

    @override_settings(
        FEATURE_MESSAGE_CAPTURE_ENABLED=True,
        FEATURE_MESSAGE_CAPTURE_ITEM_TYPES=True,
    )
    def test_main_view_message_capture_actions_use_simple_complete_wireframe(self):
        response = self.client_teacher.get(reverse("calendar_main"), follow=True)
        content = response.content.decode("utf-8")

        self.assertIn("처리 완료", content)
        self.assertNotIn("메시지 상태", content)
        self.assertNotIn("연결된 메시지 보기", content)
        self.assertNotIn("다시 볼 메시지로 되돌리기", content)
        self.assertIn("if (event && event.message_capture_id && event.message_capture_completed_at) return 'done';", content)
        self.assertIn("bg-rose-100 text-rose-800 border-rose-300", content)
        self.assertIn("bg-emerald-100 text-emerald-800 border-emerald-300", content)

    @override_settings(
        FEATURE_MESSAGE_CAPTURE_ENABLED=True,
        FEATURE_MESSAGE_CAPTURE_ITEM_TYPES=True,
    )
    def test_main_view_message_archive_edit_action_uses_manual_edit_flow(self):
        response = self.client_teacher.get(reverse("calendar_main"), follow=True)
        content = response.content.decode("utf-8")

        self.assertIn("보관한 메시지를 바로 일정 확인 화면으로 열었어요.", content)
        self.assertIn("보관한 메시지를 바로 날짜 확인 화면으로 열었어요.", content)
        self.assertNotIn("await this.submitSavedMessageCaptureParse(detail.capture_id);", content)

    def test_main_view_event_forms_auto_fill_end_time_from_start_time(self):
        response = self.client_teacher.get(reverse("calendar_main"), follow=True)
        content = response.content.decode("utf-8")

        self.assertIn("toggleEventFormHasTime('create')", content)
        self.assertIn("toggleEventFormHasTime('edit')", content)
        self.assertIn("handleEventFormStartDateChange('create')", content)
        self.assertIn("handleEventFormStartDateChange('edit')", content)
        self.assertIn("handleEventFormStartClockChange('create')", content)
        self.assertIn("handleEventFormStartClockChange('edit')", content)
        self.assertIn("markEventFormEndManual('create')", content)
        self.assertIn("markEventFormEndManual('edit')", content)

    def test_legacy_today_memo_panel_route_redirects_to_home_surface(self):
        response = self.client_teacher.get(f"{reverse('classcalendar:main')}?panel=today-memos")

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("home"), response["Location"])
        self.assertIn("focus=memos", response["Location"])
        self.assertIn("#home-calendar", response["Location"])

    def test_today_view_redirect_keeps_same_note_source_on_home_surface(self):
        event = self._create_event(title="오늘 메모 일정")
        event.start_time = timezone.now()
        event.end_time = event.start_time + timedelta(hours=1)
        event.save(update_fields=["start_time", "end_time"])
        EventPageBlock.objects.create(
            event=event,
            block_type="text",
            order=1,
            content={"text": "체육관 열쇠 챙기기\n방송 멘트 다시 확인"},
        )

        response = self.client_teacher.get(f"{reverse('calendar_today')}?focus=memos", follow=True)
        selected_date = timezone.localtime(event.start_time).date().isoformat()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["initial_selected_date"], selected_date)
        self.assertEqual(response.context["calendar_page_variant"], "main")
        self.assertTrue(
            any("체육관 열쇠 챙기기" in (item.get("note") or "") for item in response.context["events_json"])
        )

    def test_today_review_route_redirects_to_home_surface_with_same_source(self):
        event = self._create_event(title="다시 볼 메모 일정")
        event.start_time = timezone.now() - timedelta(hours=2)
        event.end_time = event.start_time + timedelta(hours=1)
        event.save(update_fields=["start_time", "end_time"])
        EventPageBlock.objects.create(
            event=event,
            block_type="text",
            order=1,
            content={"text": "수업 끝난 뒤 다시 볼 메모"},
        )

        response = self.client_teacher.get(f"{reverse('calendar_today')}?focus=review", follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["calendar_page_variant"], "main")
        self.assertIn(
            "수업 끝난 뒤 다시 볼 메모",
            [item["note"] for item in response.context["events_json"]],
        )

    def test_events_json_includes_linked_message_capture_completion_state(self):
        event = self._create_event(title="연결 메모 일정")
        completed_at = timezone.now()
        capture = CalendarMessageCapture.objects.create(
            author=self.teacher,
            raw_text="연결된 메모",
            parse_status=CalendarMessageCapture.ParseStatus.PARSED,
            committed_event=event,
            follow_up_state=CalendarMessageCapture.FollowUpState.DONE,
            completed_at=completed_at,
        )

        response = self.client_teacher.get(reverse("calendar_main"), follow=True)
        serialized = next(
            item for item in response.context["events_json"] if item["id"] == str(event.id)
        )

        self.assertEqual(serialized["message_capture_id"], str(capture.id))
        self.assertEqual(serialized["message_capture_follow_up_state"], CalendarMessageCapture.FollowUpState.DONE)
        self.assertEqual(serialized["message_capture_follow_up_state_label"], "처리 완료")
        self.assertEqual(serialized["message_capture_completed_at"], completed_at.isoformat())

    def test_tasks_json_includes_linked_message_capture_completion_state(self):
        task = self._create_task(title="연결 메모 할 일")
        capture = CalendarMessageCapture.objects.create(
            author=self.teacher,
            raw_text="할 일 메모",
            parse_status=CalendarMessageCapture.ParseStatus.PARSED,
            committed_task=task,
            follow_up_state=CalendarMessageCapture.FollowUpState.PENDING,
        )

        response = self.client_teacher.get(reverse("calendar_main"), follow=True)
        serialized = next(
            item for item in response.context["tasks_json"] if item["id"] == str(task.id)
        )

        self.assertEqual(serialized["message_capture_id"], str(capture.id))
        self.assertEqual(serialized["message_capture_follow_up_state"], CalendarMessageCapture.FollowUpState.PENDING)
        self.assertEqual(serialized["message_capture_follow_up_state_label"], "처리 예정")
        self.assertEqual(serialized["message_capture_completed_at"], "")

    def test_calendar_alias_routes_require_login_for_anonymous(self):
        response = Client().get(reverse("calendar_main"))
        today_response = Client().get(reverse("calendar_today"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(today_response.status_code, 302)
        self.assertIn(reverse("calendar_main"), response["Location"])
        self.assertIn(reverse("calendar_today"), today_response["Location"])

    def test_calendar_alias_routes_render_same_surfaces_for_authenticated_user(self):
        main_response = self.client_teacher.get(reverse("calendar_main"))
        today_response = self.client_teacher.get(f"{reverse('calendar_today')}?focus=review")

        self.assertEqual(main_response.status_code, 302)
        self.assertEqual(today_response.status_code, 302)
        self.assertIn(reverse("home"), main_response["Location"])
        self.assertIn(reverse("home"), today_response["Location"])

    def test_main_view_includes_initial_open_event_deep_link(self):
        event = self._create_event(title="딥링크 일정")
        url = f"{reverse('classcalendar:main')}?date=2026-03-01&open_event={event.id}"

        response = self.client_teacher.get(url, follow=True)
        content = response.content.decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["initial_open_event_id"], str(event.id))
        self.assertIn("initialOpenEventId:", content)

    def test_create_event_rejects_invalid_time_range(self):
        response = self.client_teacher.post(
            reverse("classcalendar:api_create_event"),
            {
                "title": "Invalid Event",
                "start_time": "2026-03-01T11:00",
                "end_time": "2026-03-01T10:00",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "validation_error")

    def test_create_event_without_active_classroom_creates_personal_event(self):
        client = Client()
        client.login(username="teacher", password="pw")
        response = client.post(
            reverse("classcalendar:api_create_event"),
            {
                "title": "No Classroom",
                "start_time": "2026-03-01T10:00",
                "end_time": "2026-03-01T11:00",
            },
        )
        self.assertEqual(response.status_code, 201)
        event = CalendarEvent.objects.filter(title="No Classroom", author=self.teacher).first()
        self.assertIsNotNone(event)
        self.assertIsNone(event.classroom)

    def test_unauthenticated_user_cannot_create_event(self):
        response = Client().post(
            reverse("classcalendar:api_create_event"),
            {
                "title": "Anonymous Event",
                "start_time": "2026-03-01T10:00",
                "end_time": "2026-03-01T11:00",
            },
        )
        self.assertEqual(response.status_code, 302)

    def test_teacher_can_update_own_event(self):
        event = self._create_event()
        response = self.client_teacher.post(
            reverse("classcalendar:api_update_event", kwargs={"event_id": str(event.id)}),
            {
                "title": "수정된 일정",
                "start_time": "2026-03-01T13:00",
                "end_time": "2026-03-01T14:30",
                "color": "emerald",
            },
        )
        self.assertEqual(response.status_code, 200)
        event.refresh_from_db()
        self.assertEqual(event.title, "수정된 일정")
        self.assertEqual(event.color, "emerald")
        self.assertEqual(event.visibility, CalendarEvent.VISIBILITY_TEACHER)

    def test_teacher_can_update_event_note(self):
        event = self._create_event(title="노트 수정 일정")
        EventPageBlock.objects.create(
            event=event,
            block_type="text",
            content={"text": "이전 메모"},
            order=0,
        )
        response = self.client_teacher.post(
            reverse("classcalendar:api_update_event", kwargs={"event_id": str(event.id)}),
            {
                "title": "노트 수정 일정",
                "note": "새로운 준비물 체크",
                "start_time": "2026-03-01T10:00",
                "end_time": "2026-03-01T11:00",
                "color": "indigo",
            },
        )
        self.assertEqual(response.status_code, 200)
        event.refresh_from_db()
        text_block = event.blocks.filter(block_type="text").first()
        self.assertIsNotNone(text_block)
        self.assertEqual(text_block.content.get("text"), "새로운 준비물 체크")

    def test_teacher_can_delete_own_event(self):
        event = self._create_event()
        response = self.client_teacher.post(
            reverse("classcalendar:api_delete_event", kwargs={"event_id": str(event.id)})
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(CalendarEvent.objects.filter(id=event.id).exists())

    def test_teacher_can_delete_own_task(self):
        task = self._create_task()
        response = self.client_teacher.post(
            reverse("classcalendar:api_delete_task", kwargs={"task_id": str(task.id)})
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(CalendarTask.objects.filter(id=task.id).exists())

    def test_teacher_cannot_update_other_teacher_event(self):
        event = self._create_event(author=self.other_teacher)
        response = self.client_teacher.post(
            reverse("classcalendar:api_update_event", kwargs={"event_id": str(event.id)}),
            {
                "title": "권한없는 수정",
                "start_time": "2026-03-01T13:00",
                "end_time": "2026-03-01T14:30",
                "color": "rose",
            },
        )
        self.assertEqual(response.status_code, 404)

    def test_teacher_cannot_delete_other_teacher_task(self):
        task = self._create_task(author=self.other_teacher)
        response = self.client_teacher.post(
            reverse("classcalendar:api_delete_task", kwargs={"task_id": str(task.id)})
        )
        self.assertEqual(response.status_code, 404)

    def test_teacher_cannot_update_locked_integration_event(self):
        event = self._create_event()
        event.is_locked = True
        event.integration_source = "collect_deadline"
        event.integration_key = "collect:test"
        event.save(update_fields=["is_locked", "integration_source", "integration_key", "updated_at"])

        response = self.client_teacher.post(
            reverse("classcalendar:api_update_event", kwargs={"event_id": str(event.id)}),
            {
                "title": "잠금 수정 시도",
                "start_time": "2026-03-01T13:00",
                "end_time": "2026-03-01T14:00",
                "color": "rose",
            },
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "integration_event_readonly")

    def test_teacher_cannot_delete_locked_integration_event(self):
        event = self._create_event()
        event.is_locked = True
        event.integration_source = "consent_expiry"
        event.integration_key = "consent:test"
        event.save(update_fields=["is_locked", "integration_source", "integration_key", "updated_at"])

        response = self.client_teacher.post(
            reverse("classcalendar:api_delete_event", kwargs={"event_id": str(event.id)})
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "integration_event_readonly")
