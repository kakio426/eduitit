import zipfile
from io import BytesIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import UserProfile
from doccollab.models import (
    DocAnalysis,
    DocAssistantQuestion,
    DocEditEvent,
    DocMembership,
    DocRevision,
    DocRoom,
    DocWorksheet,
    DocWorkspace,
    revision_upload_to,
    room_source_upload_to,
)
from doccollab.assistant_service import MAX_DOCUMENT_BYTES, MAX_QUESTIONS_PER_ANALYSIS
from doccollab.services import (
    accessible_rooms_queryset,
    append_room_collab_update,
    create_room_from_upload,
    load_room_collab_state,
    save_room_revision,
)
from doccollab.worksheet_hwp_builder import WorksheetBuildError
from doccollab.worksheet_service import (
    generate_single_page_worksheet,
    publish_generated_worksheet,
    worksheet_daily_limit_used,
)
from version_manager.models import Document, DocumentGroup, DocumentVersion, document_version_upload_to, get_raw_storage


User = get_user_model()


def hwpx_upload(name="document.hwpx", content=b"fake hwpx bytes"):
    return SimpleUploadedFile(name, content, content_type="application/octet-stream")


def hwp_upload(name="document.hwp", content=b"fake hwp bytes"):
    return SimpleUploadedFile(name, content, content_type="application/octet-stream")


def valid_hwpx_bytes(paragraphs=None):
    body = "".join(f"<p><run><t>{text}</t></run></p>" for text in (paragraphs or []))
    section_xml = f"<section>{body}</section>".encode("utf-8")
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("Contents/section0.xml", section_xml)
    return buffer.getvalue()


def valid_hwpx_upload(name="notice.hwpx", paragraphs=None):
    content = valid_hwpx_bytes(
        paragraphs
        or [
            "2026.04.30까지 신청서를 제출해 주세요.",
            "학생 준비물 안내와 담임 협조가 필요합니다.",
        ]
    )
    return SimpleUploadedFile(name, content, content_type="application/octet-stream")


class DoccollabViewTests(TestCase):
    CHROME_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

    def setUp(self):
        cache.clear()
        self.owner = User.objects.create_user(
            username="doc-owner",
            email="doc-owner@example.com",
            password="pw123456",
        )
        self.viewer = User.objects.create_user(
            username="doc-viewer",
            email="doc-viewer@example.com",
            password="pw123456",
        )
        self.other_teacher = User.objects.create_user(
            username="doc-other",
            email="doc-other@example.com",
            password="pw123456",
        )
        for user, nickname in (
            (self.owner, "문서주인"),
            (self.viewer, "문서보기"),
            (self.other_teacher, "다른선생님"),
        ):
            profile = UserProfile.objects.get(user=user)
            profile.nickname = nickname
            profile.save(update_fields=["nickname"])

    def _create_room(self, user, title, file_name):
        upload_factory = hwp_upload if file_name.lower().endswith(".hwp") else hwpx_upload
        return create_room_from_upload(
            user=user,
            title=title,
            uploaded_file=upload_factory(file_name, content=f"{title}-bytes".encode("utf-8")),
        )

    def _create_valid_hwpx_room(self, *, title="AI 공문"):
        return create_room_from_upload(
            user=self.owner,
            title=title,
            uploaded_file=valid_hwpx_upload(f"{title}.hwpx"),
        )

    def _create_raw_revision_room(self, *, title, file_name, raw_bytes):
        workspace = DocWorkspace.objects.create(name=title, created_by=self.owner)
        DocMembership.objects.create(
            workspace=workspace,
            user=self.owner,
            role=DocMembership.Role.OWNER,
            status=DocMembership.Status.ACTIVE,
            invited_by=self.owner,
        )
        source_format = DocRoom.SourceFormat.HWP if file_name.lower().endswith(".hwp") else DocRoom.SourceFormat.HWPX
        export_format = (
            DocRevision.ExportFormat.SOURCE_HWP
            if source_format == DocRoom.SourceFormat.HWP
            else DocRevision.ExportFormat.SOURCE_HWPX
        )
        room = DocRoom.objects.create(
            workspace=workspace,
            title=title,
            created_by=self.owner,
            source_name=file_name,
            source_format=source_format,
            source_sha256="0" * 64,
        )
        revision = DocRevision.objects.create(
            room=room,
            revision_number=1,
            file=ContentFile(raw_bytes, name=file_name),
            original_name=file_name,
            file_sha256="0" * 64,
            export_format=export_format,
            note="원본 업로드",
            created_by=self.owner,
        )
        return room, revision

    def _worksheet_payload(self, *, title="물의 순환 학습지", summary="구름과 비를 따라가요.", short=False):
        return {
            "title": title,
            "companion_line": "와리와 함께 물의 여행을 살펴봐요 ☆",
            "curiosity_opening": (
                "비가 그친 뒤 웅덩이가 사라지는 까닭을 떠올려 볼까요? 햇볕을 받은 물은 하늘로 올라가요."
                if not short
                else "햇볕을 받은 물이 하늘로 올라가 구름이 돼요."
            ),
            "key_points": [
                "물이 수증기가 되면 눈에 잘 안 보여요.",
                "수증기가 모이면 구름이 돼요.",
                "구름 속 물방울이 무거워지면 비가 내려요.",
            ],
            "quiz_items": [
                {"prompt": "햇볕을 받은 물은 _____ 로 올라가요.", "answer_lines": 1},
                {"prompt": "비가 온 뒤 웅덩이가 어떻게 변할지 한 줄로 적어 봐요. _____", "answer_lines": 2},
            ],
            "summary_text": summary,
            "search_text": "물의 순환 구름 비 증발",
        }

    def _worksheet_generation_result(self, *, title="물의 순환 학습지", summary="구름과 비를 따라가요.", short=False):
        return {
            "content": self._worksheet_payload(title=title, summary=summary, short=short),
            "hwp_bytes": b"worksheet-hwp",
            "page_count": 1,
            "used_profile": "comfortable" if not short else "tight",
            "file_name": f"{title}.hwp",
        }

    def _create_generated_room(self, *, user=None, title="물의 순환 학습지", topic="물의 순환", ready=False, published=False):
        owner = user or self.owner
        workspace = DocWorkspace.objects.create(name=title, created_by=owner)
        DocMembership.objects.create(
            workspace=workspace,
            user=owner,
            role=DocMembership.Role.OWNER,
            status=DocMembership.Status.ACTIVE,
            invited_by=owner,
        )
        room = DocRoom.objects.create(
            workspace=workspace,
            title=title,
            created_by=owner,
            origin_kind=DocRoom.OriginKind.GENERATED_WORKSHEET,
            source_name="",
            source_format=DocRoom.SourceFormat.HWP,
            source_sha256="",
        )
        worksheet = DocWorksheet.objects.create(
            room=room,
            topic=topic,
            summary_text="구름과 비를 따라가요.",
            content_json=self._worksheet_payload(title=title),
            search_text="물의 순환",
            provider="deepseek",
            prompt_version="worksheet-v1",
            bootstrap_status=DocWorksheet.BootstrapStatus.PENDING,
        )
        revision = None
        if ready:
            revision = save_room_revision(
                room=room,
                user=owner,
                uploaded_file=hwp_upload(f"{title}.hwp", content=b"worksheet-hwp"),
                export_format=DocRevision.ExportFormat.HWP_EXPORT,
                note="학습지 초안 생성",
            )
            worksheet.bootstrap_status = DocWorksheet.BootstrapStatus.READY
            worksheet.latest_page_count = 1
            worksheet.save(update_fields=["bootstrap_status", "latest_page_count", "updated_at"])
            if published:
                publish_generated_worksheet(worksheet=worksheet)
                worksheet.refresh_from_db()
        return room, worksheet, revision

    def test_doccollab_binary_files_use_raw_storage_callable(self):
        source_field = DocRoom._meta.get_field("source_file")
        revision_field = DocRevision._meta.get_field("file")

        self.assertIs(source_field._storage_callable, get_raw_storage)
        self.assertIs(revision_field._storage_callable, get_raw_storage)

    def test_binary_file_path_budget_covers_generated_storage_paths(self):
        source_field = DocRoom._meta.get_field("source_file")
        revision_field = DocRevision._meta.get_field("file")
        mirrored_field = DocumentVersion._meta.get_field("upload")

        long_name = f"{'a' * 180}.hwpx"
        room_path = room_source_upload_to(DocRoom(title="긴 파일명"), long_name)
        revision_path = revision_upload_to(DocRevision(revision_number=1), long_name)
        mirrored_path = document_version_upload_to(
            DocumentVersion(
                document=Document(
                    group=DocumentGroup(name="HWP 문서실", slug="hwp-docs"),
                    base_name="a" * 200,
                ),
                version=1,
            ),
            "mirrored.hwp",
        )

        self.assertEqual(source_field.max_length, 500)
        self.assertEqual(revision_field.max_length, 500)
        self.assertEqual(mirrored_field.max_length, 500)
        self.assertLessEqual(len(room_path), source_field.max_length)
        self.assertLessEqual(len(revision_path), revision_field.max_length)
        self.assertLessEqual(len(mirrored_path), mirrored_field.max_length)

    def test_create_room_builds_workspace_first_revision_and_collab_seed(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("doccollab:create_room"),
            {
                "title": "가정통신문",
                "source_file": hwpx_upload("notice.hwpx"),
            },
        )

        room = DocRoom.objects.get()
        revision = room.revisions.get(revision_number=1)

        self.assertRedirects(response, reverse("doccollab:room_detail", kwargs={"room_id": room.id}))
        self.assertEqual(room.workspace.name, "가정통신문")
        self.assertEqual(room.source_name, "notice.hwpx")
        self.assertEqual(room.source_format, DocRoom.SourceFormat.HWPX)
        self.assertEqual(room.mirrored_document.versions.count(), 1)
        self.assertTrue(
            DocMembership.objects.filter(
                workspace=room.workspace,
                user=self.owner,
                role=DocMembership.Role.OWNER,
            ).exists()
        )
        self.assertEqual(revision.export_format, DocRevision.ExportFormat.SOURCE_HWPX)
        self.assertEqual(load_room_collab_state(room)["base_revision_id"], str(revision.id))
        self.assertEqual(load_room_collab_state(room)["updates"], [])

    def test_create_room_accepts_hwp_upload_and_marks_source_format(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("doccollab:create_room"),
            {
                "title": "회의록",
                "source_file": hwp_upload("minutes.hwp"),
            },
        )

        room = DocRoom.objects.get(title="회의록")
        revision = room.revisions.get(revision_number=1)

        self.assertRedirects(response, reverse("doccollab:room_detail", kwargs={"room_id": room.id}))
        self.assertEqual(room.source_name, "minutes.hwp")
        self.assertEqual(room.source_format, DocRoom.SourceFormat.HWP)
        self.assertEqual(revision.export_format, DocRevision.ExportFormat.SOURCE_HWP)

    def test_create_room_handles_unexpected_service_error_without_500(self):
        self.client.force_login(self.owner)

        with mock.patch("doccollab.views.create_room_from_upload", side_effect=RuntimeError("boom")):
            response = self.client.post(
                reverse("doccollab:create_room"),
                {
                    "title": "오류 테스트",
                    "source_file": hwpx_upload("error.hwpx"),
                },
                follow=True,
            )

        self.assertEqual(response.status_code, 200)
        messages = [message.message for message in response.context["messages"]]
        self.assertIn("문서를 여는 중 오류가 발생했습니다. 다시 시도해 주세요.", messages)

    def test_sharing_is_scoped_to_the_room_workspace(self):
        shared_room, _shared_revision = self._create_room(self.owner, "공유 문서", "shared.hwpx")
        private_room, _private_revision = self._create_room(self.owner, "비공유 문서", "private.hwpx")

        DocMembership.objects.create(
            workspace=shared_room.workspace,
            user=self.viewer,
            role=DocMembership.Role.VIEWER,
            status=DocMembership.Status.ACTIVE,
            invited_by=self.owner,
        )

        accessible_titles = list(accessible_rooms_queryset(self.viewer).values_list("title", flat=True))

        self.assertIn(shared_room.title, accessible_titles)
        self.assertNotIn(private_room.title, accessible_titles)

    def test_dashboard_separates_my_rooms_shared_rooms_and_today_work(self):
        own_room, _ = self._create_room(self.owner, "내 문서", "mine.hwpx")
        shared_room, _ = self._create_room(self.other_teacher, "같이 쓰는 문서", "shared-room.hwpx")
        DocMembership.objects.create(
            workspace=shared_room.workspace,
            user=self.owner,
            role=DocMembership.Role.EDITOR,
            status=DocMembership.Status.ACTIVE,
            invited_by=self.other_teacher,
        )

        self.client.force_login(self.owner)
        response = self.client.get(reverse("doccollab:main"))

        my_titles = [room.title for room in response.context["my_rooms"]]
        shared_titles = [room.title for room in response.context["shared_rooms"]]
        today_titles = [room.title for room in response.context["today_rooms"]]

        self.assertIn(own_room.title, my_titles)
        self.assertIn(shared_room.title, shared_titles)
        self.assertIn(own_room.title, today_titles)
        self.assertIn(shared_room.title, today_titles)

        my_card_titles = [room["title"] for room in response.context["my_room_cards"]]
        shared_card_titles = [room["title"] for room in response.context["shared_room_cards"]]
        today_card_titles = [room["title"] for room in response.context["today_room_cards"]]

        self.assertIn(own_room.title, my_card_titles)
        self.assertIn(shared_room.title, shared_card_titles)
        self.assertIn(own_room.title, today_card_titles)
        self.assertContains(response, "잇티한글")
        self.assertContains(response, "오늘 연 문서")
        self.assertContains(response, "최근 수정한 문서")
        self.assertContains(response, "공유받은 문서")
        self.assertContains(response, "파일 열기")
        self.assertContains(response, "선택 후 바로 열림")
        self.assertNotContains(response, "학습지 만들기")
        self.assertContains(response, reverse("doccollab:remove_room", kwargs={"room_id": own_room.id}))
        self.assertContains(response, reverse("doccollab:remove_room", kwargs={"room_id": shared_room.id}))
        self.assertContains(response, "수정")
        self.assertContains(response, "삭제")
        self.assertContains(response, "제거")
        self.assertNotContains(response, "함께문서실")

    def test_remove_room_archives_owned_document_from_dashboard(self):
        own_room, _ = self._create_room(self.owner, "지울 문서", "remove-me.hwpx")

        self.client.force_login(self.owner)
        response = self.client.post(reverse("doccollab:remove_room", kwargs={"room_id": own_room.id}), follow=True)

        own_room.refresh_from_db()
        own_room.workspace.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(own_room.status, DocRoom.Status.ARCHIVED)
        self.assertEqual(own_room.workspace.status, own_room.workspace.Status.ARCHIVED)
        self.assertFalse(
            DocMembership.objects.filter(
                workspace=own_room.workspace,
                user=self.owner,
                status=DocMembership.Status.ACTIVE,
            ).exists()
        )
        self.assertNotContains(response, "지울 문서")

    def test_remove_room_disables_shared_membership_only_for_current_user(self):
        shared_room, _ = self._create_room(self.other_teacher, "공유 제거 문서", "shared-remove.hwpx")
        owner_membership = DocMembership.objects.get(workspace=shared_room.workspace, user=self.other_teacher)
        shared_membership = DocMembership.objects.create(
            workspace=shared_room.workspace,
            user=self.owner,
            role=DocMembership.Role.EDITOR,
            status=DocMembership.Status.ACTIVE,
            invited_by=self.other_teacher,
        )

        self.client.force_login(self.owner)
        response = self.client.post(reverse("doccollab:remove_room", kwargs={"room_id": shared_room.id}), follow=True)

        shared_room.refresh_from_db()
        shared_membership.refresh_from_db()
        owner_membership.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(shared_room.status, DocRoom.Status.ACTIVE)
        self.assertEqual(shared_membership.status, DocMembership.Status.DISABLED)
        self.assertEqual(owner_membership.status, DocMembership.Status.ACTIVE)
        self.assertNotContains(response, "공유 제거 문서")

    def test_shared_room_detail_shows_share_owner_members_and_access_label(self):
        shared_room, _ = self._create_room(self.other_teacher, "공유 수정 문서", "shared-edit.hwpx")
        DocMembership.objects.create(
            workspace=shared_room.workspace,
            user=self.owner,
            role=DocMembership.Role.EDITOR,
            status=DocMembership.Status.ACTIVE,
            invited_by=self.other_teacher,
        )

        self.client.force_login(self.owner)
        response = self.client.get(reverse("doccollab:room_detail", kwargs={"room_id": shared_room.id}))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["share_title"], "공유받은 문서")
        self.assertEqual(response.context["access_label"], "편집 가능")
        self.assertEqual(len(response.context["shared_members"]), 2)
        self.assertContains(response, "문서 편집")
        self.assertContains(response, "공유받은 문서")
        self.assertContains(response, "공유 2")
        self.assertContains(response, "표 수정")
        self.assertContains(response, "아래 행")

    def test_same_title_rooms_keep_separate_mirrored_documents(self):
        first_room, _ = self._create_room(self.owner, "같은 제목", "same-1.hwpx")
        second_room, _ = self._create_room(self.owner, "같은 제목", "same-2.hwpx")

        self.assertNotEqual(first_room.id, second_room.id)
        self.assertNotEqual(first_room.mirrored_document_id, second_room.mirrored_document_id)

    def test_save_revision_returns_download_url_and_resets_live_updates(self):
        room, _revision = self._create_room(self.owner, "저장 테스트", "save-test.hwpx")
        append_room_collab_update(room, [1, 2, 3])

        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("doccollab:save_revision", kwargs={"room_id": room.id}),
            {
                "note": "문서 저장",
                "export_file": hwp_upload("save-test.hwp"),
            },
        )

        payload = response.json()
        revision = DocRevision.objects.get(id=payload["revision"]["id"])
        download_response = self.client.get(payload["download_url"])

        self.assertEqual(response.status_code, 200)
        self.assertEqual(download_response.status_code, 200)
        self.assertEqual(revision.export_format, DocRevision.ExportFormat.HWP_EXPORT)
        self.assertEqual(payload["edit_events"][0]["summary"], f"저장본 저장 · r{revision.revision_number}")
        self.assertEqual(
            payload["revision"]["download_url"],
            reverse("doccollab:download_revision", kwargs={"room_id": room.id, "revision_id": revision.id}),
        )
        self.assertEqual(payload["download_url"], payload["revision"]["download_url"])
        self.assertTrue(DocumentVersion.objects.filter(pk=revision.mirrored_version_id).exists())
        self.assertEqual(load_room_collab_state(room)["base_revision_id"], str(revision.id))
        self.assertEqual(load_room_collab_state(room)["updates"], [])
        self.assertTrue(
            DocEditEvent.objects.filter(
                room=room,
                command_id=f"save:{revision.id}",
                summary=f"저장본 저장 · r{revision.revision_number}",
            ).exists()
        )

    def test_save_revision_handles_unexpected_error_without_html_500(self):
        room, _revision = self._create_room(self.owner, "저장 오류", "save-error.hwpx")
        self.client.force_login(self.owner)

        with mock.patch("doccollab.views.save_room_revision", side_effect=RuntimeError("save boom")):
            response = self.client.post(
                reverse("doccollab:save_revision", kwargs={"room_id": room.id}),
                {
                    "note": "문서 저장",
                    "export_file": hwp_upload("save-error.hwp"),
                },
            )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["message"], "저장 중 오류가 발생했습니다. 다시 시도해 주세요.")

    def test_create_room_from_upload_survives_mirror_failure(self):
        with mock.patch("doccollab.services._mirror_revision", side_effect=RuntimeError("mirror fail")):
            room, revision = create_room_from_upload(
                user=self.owner,
                title="미러 실패",
                uploaded_file=hwpx_upload("mirror-fail.hwpx"),
            )

        self.assertEqual(room.title, "미러 실패")
        self.assertIsNone(room.mirrored_document_id)
        self.assertIsNone(revision.mirrored_version_id)

    def test_save_room_revision_survives_collab_state_reset_failure(self):
        room, _revision = self._create_room(self.owner, "캐시 실패", "cache-fail.hwpx")

        with mock.patch("doccollab.services.reset_room_collab_state", side_effect=RuntimeError("cache fail")):
            revision = save_room_revision(
                room=room,
                user=self.owner,
                uploaded_file=hwp_upload("cache-fail.hwp"),
                export_format=DocRevision.ExportFormat.HWP_EXPORT,
                note="문서 저장",
            )

        self.assertEqual(revision.export_format, DocRevision.ExportFormat.HWP_EXPORT)

    def test_room_payload_reports_source_and_save_formats(self):
        room, _revision = self._create_room(self.owner, "HWP 문서", "school-form.hwp")
        self.client.force_login(self.owner)

        response = self.client.get(
            reverse("doccollab:room_detail", kwargs={"room_id": room.id}),
            HTTP_USER_AGENT="Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        )
        payload = response.context["room_payload"]

        self.assertEqual(payload["sourceFormat"], "hwp")
        self.assertEqual(payload["sourceName"], "school-form.hwp")
        self.assertEqual(payload["currentRevisionFormat"], "hwp")
        self.assertEqual(payload["saveFormat"], "hwp")
        self.assertTrue(payload["editingSupported"])
        self.assertTrue(payload["studioUrl"].endswith("/static/doccollab/rhwp-studio/index.html"))
        self.assertEqual(payload["supportedUploadFormats"], ["hwp", "hwpx"])
        self.assertEqual(
            payload["initialFileUrl"],
            reverse("doccollab:download_revision", kwargs={"room_id": room.id, "revision_id": room.revisions.first().id}),
        )
        self.assertEqual(
            payload["sourceFileUrl"],
            reverse("doccollab:download_source", kwargs={"room_id": room.id}),
        )
        self.assertTrue(payload["studioUrl"].endswith("/static/doccollab/rhwp-studio/index.html"))

    def test_room_detail_shows_assistant_actions_for_uploaded_documents(self):
        room, _revision = self._create_valid_hwpx_room(title="AI 문서")
        self.client.force_login(self.owner)

        response = self.client.get(
            reverse("doccollab:room_detail", kwargs={"room_id": room.id}),
            HTTP_USER_AGENT=self.CHROME_UA,
        )
        payload = response.context["room_payload"]

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["assistant_enabled"])
        self.assertTrue(payload["assistantEnabled"])
        self.assertEqual(payload["assistantAnalyzeUrl"], reverse("doccollab:assistant_analyze", kwargs={"room_id": room.id}))
        self.assertEqual(payload["assistantAskUrl"], reverse("doccollab:assistant_ask", kwargs={"room_id": room.id}))
        self.assertContains(response, "AI 정리")
        self.assertContains(response, "PDF")
        self.assertContains(response, "할 일")
        self.assertContains(response, "질문")

    def test_assistant_analyze_extracts_hwpx_and_first_get_200(self):
        room, _revision = self._create_valid_hwpx_room(title="정리 공문")
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("doccollab:assistant_analyze", kwargs={"room_id": room.id}),
            HTTP_ACCEPT="application/json",
        )
        detail = self.client.get(reverse("doccollab:room_detail", kwargs={"room_id": room.id}))

        analysis = DocAnalysis.objects.get(room=room)
        payload = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(analysis.status, DocAnalysis.Status.READY)
        self.assertEqual(payload["analysis"]["status"], "ready")
        self.assertEqual(payload["analysis"]["work_items"][0]["due_text"], "2026.04.30")
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, "제출 확인")

    def test_assistant_analyze_returns_expected_errors_without_500(self):
        cases = [
            ("손상", "broken.hwpx", b"not-a-zip", 400, "HWPX 파일 형식이 올바르지 않습니다."),
            ("빈 파일", "empty.hwpx", b"", 400, "빈 파일은 정리할 수 없습니다."),
            ("초과", "large.hwpx", b"x" * (MAX_DOCUMENT_BYTES + 1), 400, "문서가 너무 큽니다. 나눠서 올려 주세요."),
            ("미지원", "note.txt", b"plain text", 400, "HWP 또는 HWPX 파일만 정리합니다."),
        ]
        self.client.force_login(self.owner)

        for title, file_name, raw_bytes, status_code, message in cases:
            with self.subTest(title=title):
                room, _revision = self._create_raw_revision_room(
                    title=f"{title} 문서",
                    file_name=file_name,
                    raw_bytes=raw_bytes,
                )
                response = self.client.post(
                    reverse("doccollab:assistant_analyze", kwargs={"room_id": room.id}),
                    HTTP_ACCEPT="application/json",
                )

                self.assertEqual(response.status_code, status_code)
                self.assertEqual(response.json()["message"], message)
                self.assertEqual(DocAnalysis.objects.filter(room=room, status=DocAnalysis.Status.FAILED).count(), 1)

    def test_assistant_question_cache_no_evidence_and_rate_limit(self):
        room, _revision = self._create_valid_hwpx_room(title="질문 공문")
        self.client.force_login(self.owner)
        analyze = self.client.post(
            reverse("doccollab:assistant_analyze", kwargs={"room_id": room.id}),
            HTTP_ACCEPT="application/json",
        )
        analysis = DocAnalysis.objects.get(id=analyze.json()["analysis"]["id"])

        first = self.client.post(
            reverse("doccollab:assistant_ask", kwargs={"room_id": room.id}),
            {"question": "마감일은 언제인가요?"},
            HTTP_ACCEPT="application/json",
        )
        cached = self.client.post(
            reverse("doccollab:assistant_ask", kwargs={"room_id": room.id}),
            {"question": "마감일은 언제인가요?"},
            HTTP_ACCEPT="application/json",
        )
        no_evidence = self.client.post(
            reverse("doccollab:assistant_ask", kwargs={"room_id": room.id}),
            {"question": "급식 메뉴는 무엇인가요?"},
            HTTP_ACCEPT="application/json",
        )

        self.assertEqual(first.status_code, 200)
        self.assertIn("2026.04.30", first.json()["answer"])
        self.assertFalse(first.json()["has_insufficient_evidence"])
        self.assertTrue(first.json()["citations"])
        self.assertEqual(cached.status_code, 200)
        self.assertTrue(cached.json()["reused"])
        self.assertEqual(no_evidence.status_code, 200)
        self.assertTrue(no_evidence.json()["has_insufficient_evidence"])

        existing_count = analysis.questions.count()
        for index in range(MAX_QUESTIONS_PER_ANALYSIS - existing_count):
            DocAssistantQuestion.objects.create(
                analysis=analysis,
                created_by=self.owner,
                question=f"질문 {index}",
                normalized_question=f"limit-{index}",
                answer="답변",
                provider="doccollab-local-v1",
            )
        limited = self.client.post(
            reverse("doccollab:assistant_ask", kwargs={"room_id": room.id}),
            {"question": "새로운 질문입니다."},
            HTTP_ACCEPT="application/json",
        )

        self.assertEqual(limited.status_code, 429)
        self.assertEqual(limited.json()["message"], "질문이 많습니다. 잠시 후 다시 시도해 주세요.")

    def test_room_detail_does_not_depend_on_storage_url_generation(self):
        room, _revision = self._create_room(self.owner, "URL 방어", "guard.hwpx")
        self.client.force_login(self.owner)

        with mock.patch("django.db.models.fields.files.FieldFile.url", new_callable=mock.PropertyMock) as mocked_url:
            mocked_url.side_effect = RuntimeError("storage url failed")
            response = self.client.get(
                reverse("doccollab:room_detail", kwargs={"room_id": room.id}),
                HTTP_USER_AGENT="Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
            )

        self.assertEqual(response.status_code, 200)
        payload = response.context["room_payload"]
        self.assertEqual(
            payload["initialFileUrl"],
            reverse("doccollab:download_revision", kwargs={"room_id": room.id, "revision_id": room.revisions.first().id}),
        )
        self.assertEqual(
            payload["sourceFileUrl"],
            reverse("doccollab:download_source", kwargs={"room_id": room.id}),
        )

    def test_download_source_streams_original_upload(self):
        room, _revision = self._create_room(self.owner, "원본 다운로드", "source-check.hwp")
        self.client.force_login(self.owner)

        response = self.client.get(reverse("doccollab:download_source", kwargs={"room_id": room.id}))

        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment;", response.headers["Content-Disposition"])
        self.assertIn("source-check.hwp", response.headers["Content-Disposition"])

    def test_room_detail_shows_recent_edit_history(self):
        room, revision = self._create_room(self.owner, "이력 문서", "history.hwpx")
        DocEditEvent.objects.create(
            room=room,
            base_revision=revision,
            user=self.owner,
            command_id="history-1",
            command_type="insert_text",
            display_name="문서주인",
            summary="문장 입력 · 회의 안내",
            command_json={"type": "insert_text", "text": "회의 안내"},
        )
        DocEditEvent.objects.create(
            room=room,
            base_revision=revision,
            user=self.owner,
            command_id="history-2",
            command_type="delete_text",
            display_name="문서주인",
            summary="삭제 · 1자",
            command_json={"type": "delete_text", "count": 1},
        )
        self.client.force_login(self.owner)

        response = self.client.get(reverse("doccollab:room_detail", kwargs={"room_id": room.id}))

        self.assertContains(response, "편집 기록")
        self.assertContains(response, "본문 수정 2건")
        self.assertNotContains(response, "문장 입력 · 회의 안내")
        self.assertContains(response, "배포본")

    def test_mobile_room_is_read_only(self):
        room, _revision = self._create_room(self.owner, "모바일 보기", "mobile.hwpx")
        self.client.force_login(self.owner)

        response = self.client.get(
            reverse("doccollab:room_detail", kwargs={"room_id": room.id}),
            HTTP_USER_AGENT="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)",
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["editing_supported"])
        self.assertContains(response, "휴대폰에서는 보기만 가능합니다.")

    @mock.patch("doccollab.worksheet_service.generate_single_page_worksheet")
    def test_generate_worksheet_creates_generated_room_and_first_get_200(self, mock_generate):
        mock_generate.return_value = self._worksheet_generation_result()
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("doccollab:generate_worksheet"),
            {"topic": "물의 순환"},
            follow=True,
            HTTP_USER_AGENT=self.CHROME_UA,
        )

        room = DocRoom.objects.get(origin_kind=DocRoom.OriginKind.GENERATED_WORKSHEET)
        worksheet = room.worksheet

        self.assertEqual(response.status_code, 200)
        self.assertEqual(room.source_name, "")
        self.assertEqual(worksheet.topic, "물의 순환")
        self.assertEqual(worksheet.bootstrap_status, DocWorksheet.BootstrapStatus.READY)
        self.assertEqual(room.revisions.count(), 1)
        revision = room.revisions.get()
        self.assertEqual(response.context["room"].id, room.id)
        self.assertEqual(response.context["room_payload"]["initialFileUrl"], reverse("doccollab:download_revision", kwargs={"room_id": room.id, "revision_id": revision.id}))
        self.assertEqual(response.context["room_payload"]["sourceFileUrl"], "")

    @override_settings(DOCCOLLAB_WORKSHEET_DAILY_LIMIT=3)
    @mock.patch("doccollab.worksheet_service.generate_single_page_worksheet")
    def test_generate_worksheet_returns_429_on_fourth_request(self, mock_generate):
        mock_generate.return_value = self._worksheet_generation_result()
        self.client.force_login(self.owner)

        for _ in range(3):
            response = self.client.post(
                reverse("doccollab:generate_worksheet"),
                {"topic": "물의 순환"},
                HTTP_USER_AGENT=self.CHROME_UA,
                HTTP_ACCEPT="application/json",
            )
            self.assertEqual(response.status_code, 200)

        blocked = self.client.post(
            reverse("doccollab:generate_worksheet"),
            {"topic": "태양계"},
            HTTP_USER_AGENT=self.CHROME_UA,
            HTTP_ACCEPT="application/json",
        )

        self.assertEqual(blocked.status_code, 429)
        self.assertEqual(blocked.json()["message"], "오늘 학습지 3장을 모두 사용했어요. 내일 다시 만들어 볼까요?")

    @override_settings(DOCCOLLAB_WORKSHEET_DAILY_LIMIT=1)
    @mock.patch("doccollab.worksheet_service.generate_single_page_worksheet")
    def test_invalid_generate_request_releases_daily_limit(self, mock_generate):
        mock_generate.return_value = self._worksheet_generation_result()
        self.client.force_login(self.owner)

        invalid = self.client.post(
            reverse("doccollab:generate_worksheet"),
            {"topic": ""},
            HTTP_USER_AGENT=self.CHROME_UA,
            HTTP_ACCEPT="application/json",
        )
        valid = self.client.post(
            reverse("doccollab:generate_worksheet"),
            {"topic": "물의 순환"},
            HTTP_USER_AGENT=self.CHROME_UA,
            HTTP_ACCEPT="application/json",
        )

        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(valid.status_code, 200)
        self.assertEqual(worksheet_daily_limit_used(self.owner.id), 1)

    @override_settings(DOCCOLLAB_WORKSHEET_DAILY_LIMIT=1)
    @mock.patch("doccollab.worksheet_service.generate_single_page_worksheet")
    def test_generate_worksheet_returns_revision_metadata(self, mock_generate):
        mock_generate.return_value = self._worksheet_generation_result()
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("doccollab:generate_worksheet"),
            {"topic": "물의 순환"},
            HTTP_ACCEPT="application/json",
        )

        payload = response.json()
        room = DocRoom.objects.get(id=payload["room_id"])
        revision = room.revisions.get()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["revision_id"], str(revision.id))
        self.assertEqual(
            payload["download_url"],
            reverse("doccollab:download_revision", kwargs={"room_id": room.id, "revision_id": revision.id}),
        )
        self.assertEqual(payload["daily_used"], 1)
        self.assertEqual(payload["daily_limit"], 1)

    @override_settings(DOCCOLLAB_WORKSHEET_DAILY_LIMIT=1)
    @mock.patch("doccollab.worksheet_service.generate_single_page_worksheet")
    def test_generate_worksheet_builder_error_releases_daily_limit(self, mock_generate):
        mock_generate.side_effect = [
            WorksheetBuildError("builder failed"),
            self._worksheet_generation_result(),
        ]
        self.client.force_login(self.owner)

        failed = self.client.post(
            reverse("doccollab:generate_worksheet"),
            {"topic": "물의 순환"},
            HTTP_ACCEPT="application/json",
        )
        succeeded = self.client.post(
            reverse("doccollab:generate_worksheet"),
            {"topic": "태양계"},
            HTTP_ACCEPT="application/json",
        )

        self.assertEqual(failed.status_code, 503)
        self.assertEqual(succeeded.status_code, 200)
        self.assertEqual(worksheet_daily_limit_used(self.owner.id), 1)

    @override_settings(DOCCOLLAB_WORKSHEET_DAILY_LIMIT=1)
    @mock.patch("doccollab.views.generate_single_page_worksheet")
    def test_generate_worksheet_file_returns_hwp_download(self, mock_generate):
        mock_generate.return_value = self._worksheet_generation_result()
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("doccollab:generate_worksheet_file"),
            {"topic": "물의 순환"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment;", response.headers["Content-Disposition"])
        self.assertIn("filename*=", response.headers["Content-Disposition"])
        self.assertIn(".hwp", response.headers["Content-Disposition"])
        self.assertEqual(response.headers["Content-Type"], "application/x-hwp")
        self.assertEqual(response.headers["X-Worksheet-Daily-Used"], "1")
        self.assertEqual(response.headers["X-Worksheet-Daily-Limit"], "1")
        self.assertEqual(response.headers["X-Worksheet-Layout-Profile"], "comfortable")

    @override_settings(DOCCOLLAB_WORKSHEET_DAILY_LIMIT=1)
    def test_generate_worksheet_file_invalid_request_returns_400_without_consuming_quota(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("doccollab:generate_worksheet_file"),
            {"topic": ""},
            HTTP_ACCEPT="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["message"], "학습 주제를 먼저 입력해 주세요.")
        self.assertEqual(worksheet_daily_limit_used(self.owner.id), 0)

    @mock.patch("doccollab.worksheet_service.build_worksheet_hwp_bytes")
    @mock.patch("doccollab.worksheet_service.generate_worksheet_content")
    def test_generate_single_page_worksheet_retries_short_content_after_all_profiles(self, mock_generate, mock_build):
        mock_generate.side_effect = [
            self._worksheet_payload(),
            self._worksheet_payload(summary="짧은 버전", short=True),
        ]
        mock_build.side_effect = [
            {"layout_profile": "comfortable", "page_count": 2, "file_name": "comfortable.hwp", "hwp_bytes": b"a"},
            {"layout_profile": "compact", "page_count": 2, "file_name": "compact.hwp", "hwp_bytes": b"b"},
            {"layout_profile": "tight", "page_count": 2, "file_name": "tight.hwp", "hwp_bytes": b"c"},
            {"layout_profile": "comfortable", "page_count": 1, "file_name": "short.hwp", "hwp_bytes": b"d"},
        ]

        result = generate_single_page_worksheet(topic="물의 순환")

        self.assertEqual(result["page_count"], 1)
        self.assertEqual(result["used_profile"], "comfortable")
        self.assertEqual(result["hwp_bytes"], b"d")
        self.assertEqual(
            [call.kwargs["layout_profile"] for call in mock_build.call_args_list],
            ["comfortable", "compact", "tight", "comfortable"],
        )
        self.assertEqual(
            [call.kwargs["force_short"] for call in mock_generate.call_args_list],
            [False, True],
        )

    def test_published_worksheet_is_visible_for_download_and_clone(self):
        room, worksheet, revision = self._create_generated_room(ready=True, published=True)
        self.client.force_login(self.other_teacher)

        detail = self.client.get(
            reverse("doccollab:room_detail", kwargs={"room_id": room.id}),
            HTTP_USER_AGENT=self.CHROME_UA,
        )
        download = self.client.get(
            reverse("doccollab:download_revision", kwargs={"room_id": room.id, "revision_id": revision.id})
        )
        clone = self.client.post(
            reverse("doccollab:worksheet_clone", kwargs={"room_id": room.id}),
            follow=True,
        )

        cloned = DocWorksheet.objects.exclude(id=worksheet.id).get()
        self.assertEqual(detail.status_code, 200)
        self.assertTrue(detail.context["public_library_view"])
        self.assertEqual(download.status_code, 200)
        self.assertEqual(clone.status_code, 200)
        self.assertEqual(cloned.source_worksheet_id, worksheet.id)
        self.assertContains(clone, "내 학습지로 가져왔습니다.")
