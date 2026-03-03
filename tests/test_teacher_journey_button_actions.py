from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models import Comment, Post, UserProfile
from happy_seed.models import HSClassroom, HSClassroomConfig, HSGuardianConsent, HSStudent
from reservations.models import BlackoutDate, RecurringSchedule, School, SchoolConfig, SpecialRoom


User = get_user_model()


class ReservationsButtonActionSmokeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="res_button_teacher",
            password="pw123456",
            email="res_button_teacher@example.com",
        )
        UserProfile.objects.update_or_create(
            user=self.user,
            defaults={"nickname": "예약교사", "role": "school"},
        )
        self.client.force_login(self.user)
        self.school = School.objects.create(name="테스트학교", slug="res-button-school", owner=self.user)
        SchoolConfig.objects.create(school=self.school)
        self.room = SpecialRoom.objects.create(school=self.school, name="과학실", icon="🔬")

    def test_room_settings_add_and_delete(self):
        url = reverse("reservations:room_settings", args=[self.school.slug])
        add_response = self.client.post(url, {"action": "add", "name": "컴퓨터실", "icon": "💻"})
        self.assertEqual(add_response.status_code, 200)
        added_room = SpecialRoom.objects.filter(school=self.school, name="컴퓨터실").first()
        self.assertIsNotNone(added_room)

        delete_response = self.client.post(url, {"action": "delete", "room_id": added_room.id})
        self.assertEqual(delete_response.status_code, 200)
        self.assertFalse(SpecialRoom.objects.filter(id=added_room.id).exists())

    def test_blackout_settings_add_and_delete(self):
        url = reverse("reservations:blackout_settings", args=[self.school.slug])
        add_response = self.client.post(
            url,
            {
                "action": "add",
                "start_date": "2026-03-10",
                "end_date": "2026-03-12",
                "reason": "평가기간",
            },
        )
        self.assertEqual(add_response.status_code, 200)
        blackout = BlackoutDate.objects.filter(school=self.school, reason="평가기간").first()
        self.assertIsNotNone(blackout)

        delete_response = self.client.post(url, {"action": "delete", "item_id": blackout.id})
        self.assertEqual(delete_response.status_code, 200)
        self.assertFalse(BlackoutDate.objects.filter(id=blackout.id).exists())

    def test_recurring_settings_toggle(self):
        url = reverse("reservations:recurring_settings", args=[self.school.slug])
        payload = {"room_id": self.room.id, "day": 0, "period": 1, "name": "고정수업"}

        first = self.client.post(url, payload)
        self.assertEqual(first.status_code, 200)
        self.assertTrue(
            RecurringSchedule.objects.filter(
                room=self.room, day_of_week=0, period=1, name="고정수업"
            ).exists()
        )

        second = self.client.post(url, payload)
        self.assertEqual(second.status_code, 200)
        self.assertFalse(
            RecurringSchedule.objects.filter(
                room=self.room, day_of_week=0, period=1
            ).exists()
        )

    def test_update_config_returns_hx_refresh(self):
        url = reverse("reservations:update_config", args=[self.school.slug])
        response = self.client.post(
            url,
            {
                "school_name": "테스트학교(수정)",
                "period_labels": "1교시,2교시",
                "period_times": "09:00-09:40,09:50-10:30",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("HX-Refresh"), "true")


class HappySeedButtonActionSmokeTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(
            username="happy_button_teacher",
            password="pw123456",
            email="happy_button_teacher@example.com",
        )
        UserProfile.objects.update_or_create(
            user=self.teacher,
            defaults={"nickname": "행복교사", "role": "school"},
        )
        self.client.force_login(self.teacher)
        self.classroom = HSClassroom.objects.create(
            teacher=self.teacher,
            name="5-2",
            school_name="행복초",
        )
        HSClassroomConfig.objects.create(classroom=self.classroom)
        self.student = HSStudent.objects.create(classroom=self.classroom, name="민지", number=1)
        HSGuardianConsent.objects.create(student=self.student, status="pending")

    def test_student_add_action(self):
        url = reverse("happy_seed:student_add", kwargs={"classroom_id": self.classroom.id})
        response = self.client.post(url, {"name": "지훈", "number": 2})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(HSStudent.objects.filter(classroom=self.classroom, name="지훈", number=2).exists())

    def test_student_delete_action(self):
        url = reverse("happy_seed:student_delete", kwargs={"student_id": self.student.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(HSStudent.objects.filter(id=self.student.id).exists())

    def test_seed_grant_action(self):
        url = reverse("happy_seed:seed_grant", kwargs={"student_id": self.student.id})
        response = self.client.post(url, {"amount": 2, "detail": "교사 부여"})
        self.assertEqual(response.status_code, 200)
        self.student.refresh_from_db()
        self.assertEqual(self.student.seed_count, 2)

    def test_consent_update_action(self):
        url = reverse("happy_seed:consent_update", kwargs={"student_id": self.student.id})
        response = self.client.post(url, {"status": "approved"})
        self.assertEqual(response.status_code, 200)
        self.student.consent.refresh_from_db()
        self.assertEqual(self.student.consent.status, "approved")


class CoreButtonActionSmokeTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            username="core_author",
            password="pw123456",
            email="core_author@example.com",
        )
        self.reporter = User.objects.create_user(
            username="core_reporter",
            password="pw123456",
            email="core_reporter@example.com",
        )
        UserProfile.objects.update_or_create(
            user=self.author,
            defaults={"nickname": "작성교사", "role": "school"},
        )
        UserProfile.objects.update_or_create(
            user=self.reporter,
            defaults={"nickname": "신고교사", "role": "school"},
        )
        self.post = Post.objects.create(author=self.author, content="초기 글", post_type="general")
        self.comment = Comment.objects.create(post=self.post, author=self.author, content="초기 댓글")

    def test_post_like_action(self):
        self.client.force_login(self.reporter)
        url = reverse("post_like", args=[self.post.id])
        response = self.client.post(url, HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.post.likes.filter(id=self.reporter.id).exists())

    def test_comment_create_action(self):
        self.client.force_login(self.reporter)
        url = reverse("comment_create", args=[self.post.id])
        response = self.client.post(url, {"content": "댓글 생성 테스트"}, HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            Comment.objects.filter(post=self.post, author=self.reporter, content="댓글 생성 테스트").exists()
        )

    def test_post_edit_action(self):
        self.client.force_login(self.author)
        url = reverse("post_edit", args=[self.post.id])
        response = self.client.post(url, {"content": "수정된 글"}, HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 200)
        self.post.refresh_from_db()
        self.assertEqual(self.post.content, "수정된 글")

    def test_comment_edit_action(self):
        self.client.force_login(self.author)
        url = reverse("comment_edit", args=[self.comment.id])
        response = self.client.post(url, {"content": "수정된 댓글"}, HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 200)
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.content, "수정된 댓글")

    def test_comment_report_action(self):
        self.client.force_login(self.reporter)
        url = reverse("comment_report", args=[self.comment.id])
        response = self.client.post(url, {"reason": "spam"}, HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 200)
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.report_count, 1)
