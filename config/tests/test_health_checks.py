from django.contrib.auth import get_user_model
from django.db import connection
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext


class HealthCheckTests(TestCase):
    def test_health_check_is_query_free_for_anonymous_requests(self):
        client = Client()

        with CaptureQueriesContext(connection) as ctx:
            response = client.get("/health/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertEqual(len(ctx), 0)

    def test_health_check_is_query_free_for_authenticated_requests(self):
        user = get_user_model().objects.create_user(
            username="health-user",
            email="health@example.com",
            password="pw123456",
        )
        client = Client()
        client.force_login(user)

        with CaptureQueriesContext(connection) as ctx:
            response = client.get("/health/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertEqual(len(ctx), 0)

    def test_database_health_check_reports_connection_state(self):
        response = self.client.get("/health/db/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertEqual(response.json()["db"], "connected")
