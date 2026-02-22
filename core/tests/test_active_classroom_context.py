import uuid

from django.contrib.auth.models import AnonymousUser, User
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, TestCase

from core.context_processors import active_classroom
from happy_seed.models import HSClassroom


def _attach_session(request):
    middleware = SessionMiddleware(lambda req: None)
    middleware.process_request(request)
    request.session.save()


class ActiveClassroomContextTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username="teacher", password="password123")

    def _build_request(self, user):
        request = self.factory.get("/")
        request.user = user
        _attach_session(request)
        return request

    def test_anonymous_user_gets_empty_classroom_payload(self):
        request = self._build_request(AnonymousUser())

        context = active_classroom(request)

        self.assertIsNone(context["active_classroom"])
        self.assertFalse(context["has_hs_classrooms"])
        self.assertEqual(context["hs_classrooms_json"], [])

    def test_authenticated_user_gets_classroom_list_not_string(self):
        classroom = HSClassroom.objects.create(teacher=self.user, name="3학년 2반")
        request = self._build_request(self.user)
        request.session["active_classroom_source"] = "hs"
        request.session["active_classroom_id"] = str(classroom.id)

        context = active_classroom(request)

        self.assertEqual(context["active_classroom"].id, classroom.id)
        self.assertTrue(context["has_hs_classrooms"])
        self.assertIsInstance(context["hs_classrooms_json"], list)
        self.assertEqual(context["hs_classrooms_json"][0]["name"], "3학년 2반")

    def test_invalid_selected_classroom_clears_session(self):
        HSClassroom.objects.create(teacher=self.user, name="4학년 1반")
        request = self._build_request(self.user)
        request.session["active_classroom_source"] = "hs"
        request.session["active_classroom_id"] = str(uuid.uuid4())

        context = active_classroom(request)

        self.assertIsNone(context["active_classroom"])
        self.assertNotIn("active_classroom_source", request.session)
        self.assertNotIn("active_classroom_id", request.session)
