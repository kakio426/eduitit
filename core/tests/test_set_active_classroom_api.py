import json

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from happy_seed.models import HSClassroom


class SetActiveClassroomApiTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="teacher", password="password123")
        self.other_user = User.objects.create_user(username="other", password="password123")

    def _post_json(self, payload):
        return self.client.post(
            reverse("set_active_classroom"),
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_requires_login(self):
        classroom = HSClassroom.objects.create(teacher=self.user, name="3학년 4반")

        response = self._post_json({"source": "hs", "classroom_id": str(classroom.pk)})

        self.assertEqual(response.status_code, 302)

    def test_sets_active_classroom_for_owner(self):
        self.client.force_login(self.user)
        classroom = HSClassroom.objects.create(teacher=self.user, name="3학년 4반")

        response = self._post_json({"source": "hs", "classroom_id": str(classroom.pk)})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertEqual(response.json()["name"], "3학년 4반")
        session = self.client.session
        self.assertEqual(session["active_classroom_source"], "hs")
        self.assertEqual(session["active_classroom_id"], str(classroom.pk))

    def test_rejects_classroom_not_owned_by_user(self):
        self.client.force_login(self.user)
        classroom = HSClassroom.objects.create(teacher=self.other_user, name="다른 반")

        response = self._post_json({"source": "hs", "classroom_id": str(classroom.pk)})

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"], "classroom not found")

    def test_clear_resets_session_selection(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["active_classroom_source"] = "hs"
        session["active_classroom_id"] = "dummy-id"
        session.save()

        response = self._post_json({"classroom_id": ""})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "cleared")
        session = self.client.session
        self.assertNotIn("active_classroom_source", session)
        self.assertNotIn("active_classroom_id", session)

    def test_invalid_json_returns_400(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("set_active_classroom"),
            data="{invalid-json",
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "invalid json")

    def test_unknown_source_returns_400(self):
        self.client.force_login(self.user)

        response = self._post_json({"source": "unknown", "classroom_id": "any"})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "unknown source")
