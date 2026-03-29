import io
import json
import zipfile
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from classcalendar.models import CalendarEvent
from classcalendar.views import _resolve_integration_source_meta
from core.models import UserProfile
from hwpxchat.models import HwpxDocument, HwpxDocumentQuestion, HwpxWorkItem
from sheetbook.models import SheetCell, SheetTab, Sheetbook
from sheetbook.views import _create_default_tabs


def _build_sample_hwpx_file(name="sample.hwpx", body_text="학부모 회신서를 3월 14일까지 제출해 주세요."):
    section_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<hp:section xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph">
  <hp:p><hp:run><hp:t>{body_text}</hp:t></hp:run></hp:p>
</hp:section>
"""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("Contents/section0.xml", section_xml)
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="application/octet-stream")


def _build_long_parse_payload(*, total_blocks=36, block_size=1800):
    blocks = []
    chunks = []
    for index in range(total_blocks):
        if index % 4 == 0:
            text = (f"{index}번째 안내입니다. 회신 제출 마감 일정과 준비물 안내를 꼭 확인해 주세요. " * 40).strip()
        else:
            text = (f"{index}번째 일반 설명 문단입니다. " * 80).strip()
        markdown = text[:block_size]
        block = {
            "id": f"section0:{index + 1}",
            "kind": "text",
            "section_label": "section0.xml",
            "order": index + 1,
            "text": markdown,
            "markdown": markdown,
        }
        blocks.append(block)
        chunks.append(
            {
                "id": f"chunk-{index + 1}",
                "section_label": "section0.xml",
                "text": markdown,
                "markdown": markdown,
                "block_ids": [block["id"]],
                "has_evidence": index % 4 == 0,
            }
        )
    markdown_text = "\n\n".join(block["markdown"] for block in blocks)
    return {
        "markdown_text": markdown_text,
        "document_title": "긴 공문",
        "char_count": len(markdown_text),
        "first_text_block": blocks[0]["text"],
        "blocks": blocks,
        "chunks": chunks,
    }


class HwpxChatViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="hwpxchat_tester",
            password="pw123456",
            email="hwpxchat_tester@example.com",
        )
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.nickname = "hwpxchat_tester"
        profile.role = "school"
        profile.save(update_fields=["nickname", "role"])
        self.client.force_login(self.user)
        cache.clear()

    def _structured_payload(self):
        return {
            "summary_text": "가정통신문 회신과 준비물 전달을 확인해야 합니다.",
            "work_items": [
                {
                    "title": "회신서 안내",
                    "action_text": "학부모에게 회신서 제출 일정을 안내합니다.",
                    "due_date": "2026-03-14",
                    "assignee_text": "담임",
                    "target_text": "학부모",
                    "materials_text": "회신문",
                    "delivery_required": True,
                    "evidence_text": "학부모 회신서를 3월 14일까지 제출해 주세요.",
                    "confidence_score": 0.91,
                },
                {
                    "title": "준비물 확인",
                    "action_text": "체험학습 준비물을 다시 확인합니다.",
                    "assignee_text": "담임",
                    "target_text": "학생",
                    "materials_text": "체험학습 준비물",
                    "delivery_required": False,
                    "evidence_text": "체험학습 준비물을 금요일까지 챙겨 주세요.",
                    "confidence_score": 0.73,
                },
            ],
        }

    def test_main_wireframe_has_upload_focused_copy(self):
        response = self.client.get(reverse("hwpxchat:main"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "문서 올리기")
        self.assertContains(response, "공문을 오늘 할 일로 바로 정리하기")
        self.assertContains(response, "공문이나 한글 문서를 올리면 해야 할 일, 기한, 전달 대상을 카드로 정리해 드려요.")
        self.assertNotContains(response, "교무수첩")
        self.assertNotContains(response, "https://chatgpt.com/")

    def test_hwp_upload_is_blocked_server_side(self):
        response = self.client.post(
            reverse("hwpxchat:chat_process"),
            data={"hwpx_file": _build_sample_hwpx_file(name="sample.hwp")},
            HTTP_HX_REQUEST="true",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "HWP 파일은 지원하지 않습니다.", status_code=400)

    @patch("hwpxchat.views.generate_structured_workitems")
    def test_process_creates_document_and_work_items(self, mock_generate_structured_workitems):
        mock_generate_structured_workitems.return_value = self._structured_payload()

        response = self.client.post(
            reverse("hwpxchat:chat_process"),
            data={"hwpx_file": _build_sample_hwpx_file()},
            HTTP_HX_REQUEST="true",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "가정통신문 회신과 준비물 전달")
        self.assertContains(response, "업무 카드 전체 복사")
        self.assertNotContains(response, "교무수첩")
        self.assertNotContains(response, "학급 기록 보드에 보내기")
        self.assertEqual(HwpxDocument.objects.count(), 1)
        self.assertEqual(HwpxWorkItem.objects.count(), 2)
        document = HwpxDocument.objects.first()
        self.assertEqual(document.structure_status, HwpxDocument.StructureStatus.READY)
        self.assertEqual(document.provider, "deepseek")
        self.assertEqual(mock_generate_structured_workitems.call_count, 1)

    @patch("hwpxchat.views.generate_structured_workitems")
    def test_hidden_sheetbook_companion_stays_hidden_and_commit_returns_404(self, mock_generate_structured_workitems):
        mock_generate_structured_workitems.return_value = self._structured_payload()

        response = self.client.post(
            reverse("hwpxchat:chat_process"),
            data={"hwpx_file": _build_sample_hwpx_file()},
            HTTP_HX_REQUEST="true",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        document = HwpxDocument.objects.first()
        commit_response = self.client.post(
            reverse("hwpxchat:commit_document", kwargs={"document_id": document.id}),
            data={},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "업무 카드 전체 복사")
        self.assertNotContains(response, "교무수첩")
        self.assertNotContains(response, "학급 기록 보드에 보내기")
        self.assertEqual(commit_response.status_code, 404)

    @override_settings(SHEETBOOK_ENABLED=True, SHEETBOOK_DISCOVERY_VISIBLE=True)
    @patch("hwpxchat.views.generate_structured_workitems")
    def test_visible_sheetbook_companion_uses_public_name(self, mock_generate_structured_workitems):
        mock_generate_structured_workitems.return_value = self._structured_payload()
        sheetbook = Sheetbook.objects.create(owner=self.user, title="2026 3-1반 기록 보드")
        _create_default_tabs(sheetbook)

        response = self.client.post(
            reverse("hwpxchat:chat_process"),
            data={"hwpx_file": _build_sample_hwpx_file()},
            HTTP_HX_REQUEST="true",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "학급 기록 보드에 보내기")
        self.assertContains(response, "학급 기록 보드를 선택해 주세요")
        self.assertNotContains(response, "교무수첩")

    @patch("hwpxchat.views.generate_structured_workitems")
    def test_reupload_same_file_reuses_document_without_second_structure_call(self, mock_generate_structured_workitems):
        mock_generate_structured_workitems.return_value = self._structured_payload()
        upload = _build_sample_hwpx_file()

        first_response = self.client.post(
            reverse("hwpxchat:chat_process"),
            data={"hwpx_file": upload},
            HTTP_HX_REQUEST="true",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        second_response = self.client.post(
            reverse("hwpxchat:chat_process"),
            data={"hwpx_file": _build_sample_hwpx_file()},
            HTTP_HX_REQUEST="true",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(HwpxDocument.objects.count(), 1)
        self.assertEqual(mock_generate_structured_workitems.call_count, 1)
        self.assertContains(second_response, "이미 정리한 문서예요")

    @patch("hwpxchat.views.generate_structured_workitems")
    def test_long_document_uses_compressed_structure_input(self, mock_generate_structured_workitems):
        mock_generate_structured_workitems.return_value = self._structured_payload()
        long_parsed = _build_long_parse_payload()

        with patch("hwpxchat.views.parse_hwpx_document", return_value=long_parsed):
            response = self.client.post(
                reverse("hwpxchat:chat_process"),
                data={"hwpx_file": _build_sample_hwpx_file()},
                HTTP_HX_REQUEST="true",
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )

        self.assertEqual(response.status_code, 200)
        source_text = mock_generate_structured_workitems.call_args.kwargs["source_text"]
        self.assertLessEqual(len(source_text), 20000)
        self.assertIn("회신 제출 마감 일정", source_text)
        document = HwpxDocument.objects.first()
        self.assertEqual(document.parse_payload.get("structure_input_mode"), "compressed")

    @patch("hwpxchat.views.generate_structured_workitems")
    def test_too_large_document_is_saved_without_structure_call(self, mock_generate_structured_workitems):
        long_text = "긴 문장입니다. " * 14000
        parsed = {
            "markdown_text": long_text,
            "document_title": "매우 긴 공문",
            "char_count": len(long_text),
            "first_text_block": "긴 문장입니다.",
            "blocks": [{"id": "section0:1", "kind": "text", "section_label": "section0.xml", "order": 1, "text": long_text[:500], "markdown": long_text[:500]}],
            "chunks": [],
        }
        with patch("hwpxchat.views.parse_hwpx_document", return_value=parsed):
            response = self.client.post(
                reverse("hwpxchat:chat_process"),
                data={"hwpx_file": _build_sample_hwpx_file()},
                HTTP_HX_REQUEST="true",
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "문서가 너무 길어 나눠 올려 주세요")
        self.assertFalse(mock_generate_structured_workitems.called)
        document = HwpxDocument.objects.first()
        self.assertEqual(document.structure_status, HwpxDocument.StructureStatus.TOO_LARGE)
        self.assertEqual(document.work_items.count(), 0)

    @patch("hwpxchat.views.generate_structured_workitems")
    @patch("hwpxchat.views.rate_limit_exceeded", return_value=True)
    def test_structure_limit_creates_fallback_card(self, mock_rate_limit_exceeded, mock_generate_structured_workitems):
        response = self.client.post(
            reverse("hwpxchat:chat_process"),
            data={"hwpx_file": _build_sample_hwpx_file()},
            HTTP_HX_REQUEST="true",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "오늘 구조화 한도를 다 사용했어요")
        self.assertFalse(mock_generate_structured_workitems.called)
        document = HwpxDocument.objects.first()
        self.assertEqual(document.structure_status, HwpxDocument.StructureStatus.LIMIT_BLOCKED)
        self.assertEqual(document.work_items.count(), 1)
        self.assertEqual(document.work_items.first().title, "문서 확인 필요")
        self.assertTrue(mock_rate_limit_exceeded.called)

    @override_settings(SHEETBOOK_ENABLED=True, SHEETBOOK_DISCOVERY_VISIBLE=True)
    @patch("hwpxchat.views.generate_structured_workitems")
    def test_commit_creates_execution_tab_row_and_calendar_event(self, mock_generate_structured_workitems):
        mock_generate_structured_workitems.return_value = self._structured_payload()
        sheetbook = Sheetbook.objects.create(owner=self.user, title="2026 3-1반 기록 보드")
        _create_default_tabs(sheetbook)

        self.client.post(
            reverse("hwpxchat:chat_process"),
            data={"hwpx_file": _build_sample_hwpx_file()},
            HTTP_HX_REQUEST="true",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        document = HwpxDocument.objects.first()
        first_item = document.work_items.order_by("sort_order", "id").first()

        response = self.client.post(
            reverse("hwpxchat:commit_document", kwargs={"document_id": document.id}),
            data={
                "sheetbook_id": sheetbook.id,
                f"selected_{first_item.id}": "on",
                f"calendar_enabled_{first_item.id}": "on",
                f"title_{first_item.id}": "회신서 안내",
                f"action_text_{first_item.id}": "학부모에게 회신서 제출 일정을 안내합니다.",
                f"due_date_{first_item.id}": "2026-03-14",
                f"assignee_text_{first_item.id}": "담임",
                f"target_text_{first_item.id}": "학부모",
                f"materials_text_{first_item.id}": "회신문",
                f"delivery_required_{first_item.id}": "on",
                f"evidence_text_{first_item.id}": "학부모 회신서를 3월 14일까지 제출해 주세요.",
            },
        )

        self.assertEqual(response.status_code, 302)
        execution_tab = SheetTab.objects.get(sheetbook=sheetbook, name="실행업무")
        self.assertEqual(execution_tab.sort_order, 2)
        title_column = execution_tab.columns.get(key="title")
        due_date_column = execution_tab.columns.get(key="due_date")
        source_column = execution_tab.columns.get(key="source_document")
        self.assertEqual(execution_tab.rows.count(), 1)
        row = execution_tab.rows.first()
        self.assertEqual(SheetCell.objects.get(row=row, column=title_column).value_text, "회신서 안내")
        self.assertEqual(SheetCell.objects.get(row=row, column=due_date_column).value_date.isoformat(), "2026-03-14")
        self.assertEqual(SheetCell.objects.get(row=row, column=source_column).value_text, document.document_title)

        event = CalendarEvent.objects.get(integration_source="hwpxchat_workitem")
        self.assertEqual(event.integration_key, f"{document.id}:{first_item.id}")
        self.assertEqual(event.title, "회신서 안내")

    @override_settings(SHEETBOOK_ENABLED=True, SHEETBOOK_DISCOVERY_VISIBLE=True)
    @patch("hwpxchat.views.generate_structured_workitems")
    def test_recommit_updates_existing_row_and_can_remove_calendar_event(self, mock_generate_structured_workitems):
        mock_generate_structured_workitems.return_value = self._structured_payload()
        sheetbook = Sheetbook.objects.create(owner=self.user, title="2026 3-1반 기록 보드")
        _create_default_tabs(sheetbook)

        self.client.post(
            reverse("hwpxchat:chat_process"),
            data={"hwpx_file": _build_sample_hwpx_file()},
            HTTP_HX_REQUEST="true",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        document = HwpxDocument.objects.first()
        first_item = document.work_items.order_by("sort_order", "id").first()
        commit_url = reverse("hwpxchat:commit_document", kwargs={"document_id": document.id})

        self.client.post(
            commit_url,
            data={
                "sheetbook_id": sheetbook.id,
                f"selected_{first_item.id}": "on",
                f"calendar_enabled_{first_item.id}": "on",
                f"title_{first_item.id}": "회신서 안내",
                f"action_text_{first_item.id}": "학부모에게 회신서 제출 일정을 안내합니다.",
                f"due_date_{first_item.id}": "2026-03-14",
                f"assignee_text_{first_item.id}": "담임",
                f"target_text_{first_item.id}": "학부모",
                f"materials_text_{first_item.id}": "회신문",
                f"delivery_required_{first_item.id}": "on",
                f"evidence_text_{first_item.id}": "학부모 회신서를 3월 14일까지 제출해 주세요.",
            },
        )

        execution_tab = SheetTab.objects.get(sheetbook=sheetbook, name="실행업무")
        row = execution_tab.rows.first()
        self.client.post(
            commit_url,
            data={
                "sheetbook_id": sheetbook.id,
                f"selected_{first_item.id}": "on",
                f"title_{first_item.id}": "회신서 일정 다시 확인",
                f"action_text_{first_item.id}": "일정을 다시 공지합니다.",
                f"due_date_{first_item.id}": "2026-03-15",
                f"assignee_text_{first_item.id}": "담임",
                f"target_text_{first_item.id}": "학부모",
                f"materials_text_{first_item.id}": "회신문",
                f"delivery_required_{first_item.id}": "on",
                f"evidence_text_{first_item.id}": "학부모 회신서를 3월 14일까지 제출해 주세요.",
            },
        )

        self.assertEqual(execution_tab.rows.count(), 1)
        self.assertEqual(execution_tab.rows.first().id, row.id)
        title_column = execution_tab.columns.get(key="title")
        updated_title = SheetCell.objects.get(row=row, column=title_column).value_text
        self.assertEqual(updated_title, "회신서 일정 다시 확인")
        self.assertEqual(CalendarEvent.objects.filter(integration_source="hwpxchat_workitem").count(), 0)

    @patch("hwpxchat.views.answer_document_question")
    @patch("hwpxchat.views.generate_structured_workitems")
    def test_ask_without_evidence_skips_llm_call(self, mock_generate_structured_workitems, mock_answer_document_question):
        mock_generate_structured_workitems.return_value = self._structured_payload()
        self.client.post(
            reverse("hwpxchat:chat_process"),
            data={"hwpx_file": _build_sample_hwpx_file(body_text="학부모 회신서를 3월 14일까지 제출해 주세요.")},
            HTTP_HX_REQUEST="true",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        document = HwpxDocument.objects.first()

        response = self.client.post(
            reverse("hwpxchat:ask_document", kwargs={"document_id": document.id}),
            data={"question": "급식비 납부 일정만 알려줘"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content.decode("utf-8"))
        self.assertTrue(payload["has_insufficient_evidence"])
        self.assertEqual(payload["answer"], "문서 근거를 찾지 못했습니다.")
        self.assertFalse(mock_answer_document_question.called)
        self.assertEqual(HwpxDocumentQuestion.objects.count(), 1)

    @patch("hwpxchat.views.answer_document_question")
    @patch("hwpxchat.views.generate_structured_workitems")
    def test_ask_reuses_cached_answer_for_same_question(self, mock_generate_structured_workitems, mock_answer_document_question):
        mock_generate_structured_workitems.return_value = self._structured_payload()
        mock_answer_document_question.return_value = {
            "answer": "회신서는 3월 14일까지 받아야 합니다.",
            "citations": [{"chunk_id": "chunk-1", "quote": "학부모 회신서를 3월 14일까지 제출해 주세요."}],
            "has_insufficient_evidence": False,
        }
        self.client.post(
            reverse("hwpxchat:chat_process"),
            data={"hwpx_file": _build_sample_hwpx_file()},
            HTTP_HX_REQUEST="true",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        document = HwpxDocument.objects.first()
        ask_url = reverse("hwpxchat:ask_document", kwargs={"document_id": document.id})

        first_response = self.client.post(ask_url, data={"question": "회신서 제출 일정 알려줘"}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        second_response = self.client.post(ask_url, data={"question": "회신서 제출 일정 알려줘"}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(mock_answer_document_question.call_count, 1)
        self.assertEqual(HwpxDocumentQuestion.objects.count(), 1)
        second_payload = json.loads(second_response.content.decode("utf-8"))
        self.assertTrue(second_payload["reused"])
        self.assertEqual(second_payload["answer"], "회신서는 3월 14일까지 받아야 합니다.")

    @patch("hwpxchat.views.generate_structured_workitems")
    def test_download_markdown_accepts_document_query_param(self, mock_generate_structured_workitems):
        mock_generate_structured_workitems.return_value = self._structured_payload()
        self.client.post(
            reverse("hwpxchat:chat_process"),
            data={"hwpx_file": _build_sample_hwpx_file()},
            HTTP_HX_REQUEST="true",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        document = HwpxDocument.objects.first()

        response = self.client.get(reverse("hwpxchat:download_markdown"), data={"document_id": document.id})

        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment; filename=\"hwpx_markdown.md\"", response["Content-Disposition"])
        self.assertIn("학부모 회신서", response.content.decode("utf-8"))

    def test_hwpx_calendar_source_meta_points_to_document(self):
        event = CalendarEvent.objects.create(
            title="회신서 안내",
            author=self.user,
            start_time=timezone.now(),
            end_time=timezone.now(),
            integration_source="hwpxchat_workitem",
            integration_key="123e4567-e89b-12d3-a456-426614174000:123e4567-e89b-12d3-a456-426614174001",
        )

        source_url, source_label = _resolve_integration_source_meta(event)

        self.assertEqual(source_label, "원본 문서로 이동")
        self.assertEqual(
            source_url,
            reverse("hwpxchat:document_detail", kwargs={"document_id": "123e4567-e89b-12d3-a456-426614174000"}),
        )
