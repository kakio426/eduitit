from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from reservations.models import Reservation, School, SpecialRoom


User = get_user_model()


class ReservationIntegrationScopeTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="reservation_owner",
            password="pw12345",
            email="reservation_owner@example.com",
        )
        self.other = User.objects.create_user(
            username="reservation_other",
            password="pw12345",
            email="reservation_other@example.com",
        )
        self.school = School.objects.create(
            name="테스트학교",
            slug="reservation-scope-school",
            owner=self.owner,
        )
        self.room = SpecialRoom.objects.create(
            school=self.school,
            name="과학실",
            icon="🔬",
        )
        self.client = Client()

    def _hub_items_for(self, user):
        self.client.force_login(user)
        response = self.client.get(reverse("classcalendar:api_events"))
        self.assertEqual(response.status_code, 200)
        return response.json().get("hub_items") or []

    def test_hub_includes_only_reservations_created_by_author(self):
        today = timezone.localdate()
        mine = Reservation.objects.create(
            room=self.room,
            created_by=self.owner,
            date=today,
            period=2,
            grade=5,
            class_no=1,
            name="담임교사",
        )
        Reservation.objects.create(
            room=self.room,
            created_by=self.other,
            date=today,
            period=3,
            grade=5,
            class_no=2,
            name="다른교사",
        )
        Reservation.objects.create(
            room=self.room,
            created_by=None,
            date=today,
            period=4,
            grade=5,
            class_no=3,
            name="익명예약",
        )

        items = [item for item in self._hub_items_for(self.owner) if item.get("item_kind") == "reservation"]
        self.assertEqual(len(items), 1)
        self.assertIn(f"reservation={mine.id}", items[0]["source_url"])

    def test_hub_uses_creator_even_when_school_owner_differs(self):
        today = timezone.localdate()
        reservation = Reservation.objects.create(
            room=self.room,
            created_by=self.other,
            date=today,
            period=1,
            grade=6,
            class_no=1,
            name="다른사용자",
        )

        items = [item for item in self._hub_items_for(self.other) if item.get("item_kind") == "reservation"]
        self.assertEqual(len(items), 1)
        self.assertIn(f"reservation={reservation.id}", items[0]["source_url"])
