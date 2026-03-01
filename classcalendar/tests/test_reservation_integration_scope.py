from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from classcalendar.integrations import SOURCE_RESERVATION, sync_user_calendar_integrations
from classcalendar.models import CalendarEvent
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

    def test_sync_includes_only_reservations_created_by_author(self):
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

        sync_user_calendar_integrations(self.owner)

        events = CalendarEvent.objects.filter(
            author=self.owner,
            integration_source=SOURCE_RESERVATION,
        )
        self.assertEqual(events.count(), 1)
        self.assertEqual(events.first().integration_key.split(":")[1], str(mine.id))

    def test_sync_uses_creator_even_when_school_owner_differs(self):
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

        sync_user_calendar_integrations(self.other)

        events = CalendarEvent.objects.filter(
            author=self.other,
            integration_source=SOURCE_RESERVATION,
        )
        self.assertEqual(events.count(), 1)
        self.assertEqual(events.first().integration_key.split(":")[1], str(reservation.id))
