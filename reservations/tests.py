from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from core.models import UserProfile
from .models import School, SchoolConfig, SpecialRoom, RecurringSchedule, BlackoutDate, Reservation
from datetime import date, timedelta

class ReservationsViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='admin', password='password', email='admin@example.com')
        
        # UserProfile setup
        profile, created = UserProfile.objects.get_or_create(user=self.user)
        profile.nickname = 'AdminUser'
        profile.role = 'school'
        profile.save()
        
        self.school = School.objects.create(name='Test School', slug='test-school', owner=self.user)
        self.config = SchoolConfig.objects.create(school=self.school, max_periods=6) # Config auto-created via logic? No, manual here for test isolation if auto-create signal absent
        # Update: In views.py dashboard_landing, we create Config manually. In tests, we should check if signal exists or create manually.
        # Models don't have post_save for School to create Config.
        if not hasattr(self.school, 'config'):
             SchoolConfig.objects.create(school=self.school)
             
        self.room = SpecialRoom.objects.create(school=self.school, name='Science Room')
        self.target_date = date.today()
        
    def test_reservation_index(self):
        # Shell check
        response = self.client.get(reverse('reservations:reservation_index', args=[self.school.slug]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test School')
        # Grid is loaded via HTMX, so room name won't be in initial response
        
    def test_reservation_grid_htmx(self):
        # HTMX check
        url = reverse('reservations:reservation_index', args=[self.school.slug])
        headers = {'HTTP_HX-Request': 'true'}
        response = self.client.get(url, **headers)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Science Room')
        
    def test_create_reservation(self):
        url = reverse('reservations:create_reservation', args=[self.school.slug])
        data = {
            'room_id': self.room.id,
            'date': self.target_date.strftime('%Y-%m-%d'),
            'period': 1,
            'grade': 6,
            'class_no': 1,
            'name': 'Tester'
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        created = Reservation.objects.filter(room=self.room, date=self.target_date, period=1).first()
        self.assertIsNotNone(created)

        session = self.client.session
        self.assertIn(created.id, session.get('owned_reservation_ids', []))
        
        # Duplicate check
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 409)
        
    def test_delete_reservation(self):
        reservation = Reservation.objects.create(
            room=self.room,
            date=self.target_date,
            period=2,
            grade=5,
            class_no=2,
            name='To Delete'
        )

        session = self.client.session
        session['owned_reservation_ids'] = [reservation.id]
        session.save()

        url = reverse('reservations:delete_reservation', args=[self.school.slug, reservation.id])
        response = self.client.post(url)
        self.assertRedirects(response, reverse('reservations:reservation_index', args=[self.school.slug]))
        self.assertFalse(Reservation.objects.filter(id=reservation.id).exists())

    def test_delete_reservation_forbidden_without_ownership(self):
        reservation = Reservation.objects.create(
            room=self.room,
            date=self.target_date,
            period=4,
            grade=4,
            class_no=1,
            name='Protected'
        )
        url = reverse('reservations:delete_reservation', args=[self.school.slug, reservation.id])

        response = self.client.post(url)
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Reservation.objects.filter(id=reservation.id).exists())

    def test_anonymous_can_delete_only_own_session_reservation(self):
        self.client.logout()
        create_url = reverse('reservations:create_reservation', args=[self.school.slug])
        data = {
            'room_id': self.room.id,
            'date': self.target_date.strftime('%Y-%m-%d'),
            'period': 5,
            'grade': 6,
            'class_no': 3,
            'name': 'Anon Tester'
        }
        response = self.client.post(create_url, data)
        self.assertEqual(response.status_code, 200)

        reservation = Reservation.objects.get(room=self.room, date=self.target_date, period=5)
        delete_url = reverse('reservations:delete_reservation', args=[self.school.slug, reservation.id])
        response = self.client.post(delete_url)

        self.assertRedirects(response, reverse('reservations:reservation_index', args=[self.school.slug]))
        self.assertFalse(Reservation.objects.filter(id=reservation.id).exists())

    def test_admin_delete_reservation(self):
        reservation = Reservation.objects.create(
            room=self.room,
            date=self.target_date,
            period=3,
            grade=3,
            class_no=3,
            name='Admin Delete'
        )
        url = reverse('reservations:admin_delete_reservation', args=[self.school.slug, reservation.id])
        
        # 1. Unauthenticated -> Login Redirect
        self.client.logout()
        response = self.client.post(url)
        self.assertNotEqual(response.status_code, 200) 
        self.assertTrue(Reservation.objects.filter(id=reservation.id).exists())
        
        # 2. Authenticated Admin -> Success
        self.client.force_login(self.user)
        response = self.client.post(url)
        self.assertRedirects(response, reverse('reservations:reservation_index', args=[self.school.slug]))
        self.assertFalse(Reservation.objects.filter(id=reservation.id).exists())

    def test_blackout_prevention(self):
        # Set Blackout
        BlackoutDate.objects.create(
            school=self.school, 
            start_date=self.target_date, 
            end_date=self.target_date, 
            reason='Holiday'
        )
        
        url = reverse('reservations:create_reservation', args=[self.school.slug])
        data = {
            'room_id': self.room.id,
            'date': self.target_date.strftime('%Y-%m-%d'),
            'period': 1,
            'grade': 6,
            'class_no': 1,
            'name': 'Tester'
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Reservation.objects.filter(room=self.room, date=self.target_date).exists())
