from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from core.models import UserProfile
from doccollab.models import DocEditEvent, DocMembership, DocRevision, DocRoom
from doccollab.services import (
    accessible_rooms_queryset,
    append_room_collab_update,
    create_room_from_upload,
    load_room_collab_state,
)
from version_manager.models import DocumentVersion, get_raw_storage


User = get_user_model()


def hwpx_upload(name="document.hwpx", content=b"fake hwpx bytes"):
    return SimpleUploadedFile(name, content, content_type="application/octet-stream")


def hwp_upload(name="document.hwp", content=b"fake hwp bytes"):
    return SimpleUploadedFile(name, content, content_type="application/octet-stream")


class DoccollabViewTests(TestCase):
    def setUp(self):
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

    def test_doccollab_binary_files_use_raw_storage_callable(self):
        source_field = DocRoom._meta.get_field("source_file")
        revision_field = DocRevision._meta.get_field("file")

        self.assertIs(source_field._storage_callable, get_raw_storage)
        self.assertIs(revision_field._storage_callable, get_raw_storage)

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

        self.assertIn(own_room.title, my_card_titles)
        self.assertIn(shared_room.title, shared_card_titles)
        self.assertContains(response, "HWP 문서실")
        self.assertContains(response, "최근 문서")
        self.assertContains(response, "공유받은 문서")
        self.assertContains(response, "파일 열기")
        self.assertContains(response, "선택 후 바로 열림")
        self.assertNotContains(response, "함께문서실")

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
        self.assertContains(response, "문서 공유")

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

        self.assertEqual(response.status_code, 200)
        self.assertEqual(revision.export_format, DocRevision.ExportFormat.HWP_EXPORT)
        self.assertEqual(
            payload["revision"]["download_url"],
            reverse("doccollab:download_revision", kwargs={"room_id": room.id, "revision_id": revision.id}),
        )
        self.assertEqual(payload["download_url"], payload["revision"]["download_url"])
        self.assertTrue(DocumentVersion.objects.filter(pk=revision.mirrored_version_id).exists())
        self.assertEqual(load_room_collab_state(room)["base_revision_id"], str(revision.id))
        self.assertEqual(load_room_collab_state(room)["updates"], [])

    def test_room_payload_reports_source_and_save_formats(self):
        room, _revision = self._create_room(self.owner, "HWP 문서", "school-form.hwp")
        self.client.force_login(self.owner)

        response = self.client.get(reverse("doccollab:room_detail", kwargs={"room_id": room.id}))
        payload = response.context["room_payload"]

        self.assertEqual(payload["sourceFormat"], "hwp")
        self.assertEqual(payload["sourceName"], "school-form.hwp")
        self.assertEqual(payload["currentRevisionFormat"], "hwp")
        self.assertEqual(payload["saveFormat"], "hwp")
        self.assertEqual(payload["supportedUploadFormats"], ["hwp", "hwpx"])
        self.assertEqual(
            payload["initialFileUrl"],
            reverse("doccollab:download_revision", kwargs={"room_id": room.id, "revision_id": room.revisions.first().id}),
        )
        self.assertEqual(
            payload["sourceFileUrl"],
            reverse("doccollab:download_source", kwargs={"room_id": room.id}),
        )

    def test_room_detail_does_not_depend_on_storage_url_generation(self):
        room, _revision = self._create_room(self.owner, "URL 방어", "guard.hwpx")
        self.client.force_login(self.owner)

        with mock.patch("django.db.models.fields.files.FieldFile.url", new_callable=mock.PropertyMock) as mocked_url:
            mocked_url.side_effect = RuntimeError("storage url failed")
            response = self.client.get(reverse("doccollab:room_detail", kwargs={"room_id": room.id}))

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
        self.client.force_login(self.owner)

        response = self.client.get(reverse("doccollab:room_detail", kwargs={"room_id": room.id}))

        self.assertContains(response, "편집 기록")
        self.assertContains(response, "문장 입력 · 회의 안내")
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
