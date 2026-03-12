from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.test import RequestFactory, TestCase


User = get_user_model()


class AuthSecurityLoggingTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.staff = User.objects.create_user(
            username="staff_teacher",
            email="staff@example.com",
            password="pw123456",
            is_staff=True,
        )

    def test_staff_login_success_is_logged(self):
        request = self.factory.get("/secret-admin-kakio/login/")
        request.META["REMOTE_ADDR"] = "127.0.0.1"

        with self.assertLogs("core.auth_security", level="INFO") as captured:
            user_logged_in.send(sender=User, request=request, user=self.staff)

        self.assertIn("staff login success", captured.output[0])
        self.assertIn("staff_teacher", captured.output[0])

    def test_staff_login_failure_is_logged(self):
        request = self.factory.post("/secret-admin-kakio/login/")
        request.META["REMOTE_ADDR"] = "127.0.0.1"

        with self.assertLogs("core.auth_security", level="WARNING") as captured:
            user_login_failed.send(
                sender=User,
                credentials={"username": self.staff.username},
                request=request,
            )

        self.assertIn("staff login failed", captured.output[0])
        self.assertIn("staff_teacher", captured.output[0])
