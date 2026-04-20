from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils import timezone
from urllib.parse import quote
from core.models import UserProfile
from .utils import get_max_booking_date
from .models import (
    BlackoutDate,
    GradeRecurringLock,
    RecurringSchedule,
    Reservation,
    ReservationCollaborator,
    School,
    SchoolConfig,
    SpecialRoom,
    build_reservation_owner_key,
    hash_reservation_edit_code,
)
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
        self.default_edit_code = '2468'
        self.client.force_login(self.user)

    def set_owner_cookie(self, client, *, grade=0, class_no=0, target_label='', name=''):
        owner_key = build_reservation_owner_key(
            grade=grade,
            class_no=class_no,
            target_label=target_label,
            name=name,
        )
        client.cookies['reservation_owner_key'] = quote(owner_key, safe='')
        return owner_key
        
    def test_reservation_index(self):
        # Shell check
        response = self.client.get(reverse('reservations:reservation_index', args=[self.school.slug]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test School')
        # Grid is loaded via HTMX, so room name won't be in initial response
        
    def test_reservation_index_uses_compact_header_actions(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('reservations:reservation_index', args=[self.school.slug]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '특별실별 현황')
        self.assertContains(response, '관리자 대시보드')
        self.assertContains(response, '날짜 이동')
        self.assertNotContains(response, '날짜를 고르고 칸을 눌러 바로 예약하거나 수정할 수 있습니다.')

    def test_reservation_index_has_date_jump_form(self):
        response = self.client.get(reverse('reservations:reservation_index', args=[self.school.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="jump-date"', html=False)
        self.assertContains(response, 'type="date"', html=False)
        self.assertContains(response, f'value="{self.target_date.strftime("%Y-%m-%d")}"', html=False)
        self.assertContains(response, '날짜 이동')

    def test_reservation_index_can_open_specific_reservation_from_query(self):
        reservation = Reservation.objects.create(
            room=self.room,
            created_by=self.user,
            date=self.target_date,
            period=3,
            grade=5,
            class_no=1,
            name='열기 테스트',
        )

        response = self.client.get(
            f"{reverse('reservations:reservation_index', args=[self.school.slug])}?date={self.target_date.strftime('%Y-%m-%d')}&reservation={reservation.id}"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['initial_open_reservation_payload']['id'], reservation.id)
        self.assertEqual(response.context['initial_open_reservation_payload']['roomName'], self.room.name)
        self.assertEqual(
            response.context['initial_open_reservation_payload']['date'],
            self.target_date.strftime('%Y-%m-%d'),
        )
        self.assertContains(response, 'reservation-initial-open-data')

    def test_reservation_index_date_jump_respects_teacher_limits(self):
        self.config.weekly_opening_mode = True
        self.config.save(update_fields=['weekly_opening_mode'])
        expected_max_date = get_max_booking_date(self.school)
        teacher = User.objects.create_user(username='shared-teacher', password='password2', email='shared@example.com')
        teacher_profile, _ = UserProfile.objects.get_or_create(user=teacher)
        teacher_profile.nickname = '공유담임'
        teacher_profile.save(update_fields=['nickname'])
        ReservationCollaborator.objects.create(school=self.school, collaborator=teacher, can_edit=True)

        self.client.force_login(teacher)
        response = self.client.get(reverse('reservations:reservation_index', args=[self.school.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'min="{timezone.localdate().strftime("%Y-%m-%d")}"', html=False)
        self.assertContains(response, f'max="{expected_max_date.strftime("%Y-%m-%d")}"', html=False)
        self.assertContains(response, '날짜 이동')
        self.assertNotContains(response, '날짜를 고르고 칸을 눌러 바로 예약하거나 수정할 수 있습니다.')

    def test_reservation_grid_htmx(self):
        # HTMX check
        url = reverse('reservations:reservation_index', args=[self.school.slug])
        headers = {'HTTP_HX-Request': 'true'}
        response = self.client.get(url, **headers)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Science Room')

    def test_reservation_index_uses_workspace_cache_headers(self):
        response = self.client.get(reverse('reservations:reservation_index', args=[self.school.slug]))
        self.assertEqual(response['Cache-Control'], 'private, no-cache, must-revalidate')

    def test_admin_dashboard_uses_sensitive_cache_headers(self):
        response = self.client.get(reverse('reservations:admin_dashboard', args=[self.school.slug]))
        self.assertEqual(response['Cache-Control'], 'no-store, private')

    def test_admin_dashboard_uses_grade_lock_matrix_shell(self):
        response = self.client.get(reverse('reservations:admin_dashboard', args=[self.school.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'grade-lock-matrix-container')
        self.assertContains(response, '특별실 시간표에서 칸을 눌러 바로 학년을 고정하거나 해제하세요.')
        self.assertNotContains(response, '학년 고정 저장')

    def test_smart_entry_redirects_directly_when_user_has_one_school(self):
        response = self.client.get(reverse('reservations:smart_entry'))

        self.assertRedirects(
            response,
            reverse('reservations:reservation_index', args=[self.school.slug]),
        )

    def test_smart_entry_redirects_collaborator_to_shared_school(self):
        collaborator = User.objects.create_user(
            username='shared-entry',
            password='password2',
            email='shared-entry@example.com',
        )
        collaborator_profile, _ = UserProfile.objects.get_or_create(user=collaborator)
        collaborator_profile.nickname = '공유입장'
        collaborator_profile.save(update_fields=['nickname'])
        ReservationCollaborator.objects.create(
            school=self.school,
            collaborator=collaborator,
            can_edit=True,
        )

        self.client.force_login(collaborator)
        response = self.client.get(reverse('reservations:smart_entry'))

        self.assertRedirects(
            response,
            reverse('reservations:reservation_index', args=[self.school.slug]),
        )

    def test_smart_entry_keeps_chooser_when_user_has_multiple_schools(self):
        second_school = School.objects.create(
            name='Another School',
            slug='another-school',
            owner=self.user,
        )
        SchoolConfig.objects.create(school=second_school)

        response = self.client.get(reverse('reservations:smart_entry'))

        self.assertRedirects(
            response,
            reverse('reservations:dashboard_landing'),
        )

    def test_authenticated_public_link_is_saved_to_recent_history(self):
        outsider = User.objects.create_user(username='recentoutsider', password='password2', email='recentoutsider@example.com')
        outsider_profile, _ = UserProfile.objects.get_or_create(user=outsider)
        outsider_profile.nickname = '최근교사'
        outsider_profile.save(update_fields=['nickname'])

        self.client.force_login(outsider)
        self.client.get(reverse('reservations:reservation_index', args=[self.school.slug]))

        outsider_profile.refresh_from_db()
        self.assertEqual(outsider_profile.recent_reservation_school_ids, [self.school.id])

    def test_smart_entry_redirects_recent_public_link_user_to_recent_school(self):
        outsider = User.objects.create_user(username='smartrecent', password='password2', email='smartrecent@example.com')
        outsider_profile, _ = UserProfile.objects.get_or_create(user=outsider)
        outsider_profile.nickname = '기억교사'
        outsider_profile.save(update_fields=['nickname'])

        self.client.force_login(outsider)
        self.client.get(reverse('reservations:reservation_index', args=[self.school.slug]))
        response = self.client.get(reverse('reservations:smart_entry'))

        self.assertRedirects(
            response,
            reverse('reservations:reservation_index', args=[self.school.slug]),
        )

    def test_dashboard_landing_shows_recent_public_reservation_boards(self):
        outsider = User.objects.create_user(username='recentdashboard', password='password2', email='recentdashboard@example.com')
        outsider_profile, _ = UserProfile.objects.get_or_create(user=outsider)
        outsider_profile.nickname = '대시교사'
        outsider_profile.save(update_fields=['nickname'])
        second_school = School.objects.create(name='Second School', slug='second-school', owner=self.user)
        SchoolConfig.objects.create(school=second_school)

        self.client.force_login(outsider)
        self.client.get(reverse('reservations:reservation_index', args=[self.school.slug]))
        self.client.get(reverse('reservations:reservation_index', args=[second_school.slug]))
        response = self.client.get(reverse('reservations:dashboard_landing'))

        self.assertContains(response, '최근 열어본 예약판')
        self.assertContains(response, 'Test School')
        self.assertContains(response, 'Second School')
        self.assertContains(response, '학교 예약 시스템')
        self.assertNotContains(response, '잇티예약')
        self.assertNotContains(response, '내 학교 목록')

    def test_dashboard_landing_uses_short_owner_labels(self):
        response = self.client.get(reverse('reservations:dashboard_landing'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '학교 예약 시스템')
        self.assertContains(response, '내 학교')
        self.assertNotContains(response, '잇티예약')
        self.assertNotContains(response, '내 학교 목록')

    def test_unshared_user_can_use_public_link(self):
        outsider = User.objects.create_user(username='outsider', password='password2', email='outsider@example.com')
        outsider_profile, _ = UserProfile.objects.get_or_create(user=outsider)
        outsider_profile.nickname = '외부교사'
        outsider_profile.save(update_fields=['nickname'])

        self.client.force_login(outsider)
        response = self.client.get(reverse('reservations:reservation_index', args=[self.school.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '로그인 없이 예약 가능. 다른 기기에서는 예약 칸의 코드 버튼으로 수정하거나 취소합니다.')
        self.assertContains(response, '주소로 예약')
        self.assertContains(response, '내 예약 찾기')

    def test_readonly_collaborator_can_view_but_cannot_create(self):
        viewer = User.objects.create_user(username='viewer', password='password2', email='viewer@example.com')
        viewer_profile, _ = UserProfile.objects.get_or_create(user=viewer)
        viewer_profile.nickname = '조회교사'
        viewer_profile.save(update_fields=['nickname'])
        ReservationCollaborator.objects.create(school=self.school, collaborator=viewer, can_edit=False)

        self.client.force_login(viewer)
        index_response = self.client.get(reverse('reservations:reservation_index', args=[self.school.slug]))
        self.assertEqual(index_response.status_code, 200)
        self.assertContains(index_response, '읽기 전용으로 공유되었습니다')

        create_response = self.client.post(
            reverse('reservations:create_reservation', args=[self.school.slug]),
            {
                'room_id': self.room.id,
                'date': self.target_date.strftime('%Y-%m-%d'),
                'period': 1,
                'grade': 6,
                'class_no': 1,
                'name': '조회교사',
                'edit_code': self.default_edit_code,
            },
        )
        self.assertEqual(create_response.status_code, 403)

    def test_edit_collaborator_can_create_reservation(self):
        editor = User.objects.create_user(username='editor', password='password2', email='editor@example.com')
        editor_profile, _ = UserProfile.objects.get_or_create(user=editor)
        editor_profile.nickname = '공유교사'
        editor_profile.save(update_fields=['nickname'])
        ReservationCollaborator.objects.create(school=self.school, collaborator=editor, can_edit=True)

        self.client.force_login(editor)
        response = self.client.post(
            reverse('reservations:create_reservation', args=[self.school.slug]),
            {
                'room_id': self.room.id,
                'date': self.target_date.strftime('%Y-%m-%d'),
                'period': 4,
                'grade': 5,
                'class_no': 2,
                'name': '공유교사',
                'edit_code': self.default_edit_code,
            },
        )

        self.assertEqual(response.status_code, 200)
        created = Reservation.objects.get(room=self.room, date=self.target_date, period=4)
        self.assertEqual(created.created_by, editor)

    def test_owner_can_share_school_with_teacher_by_email(self):
        collaborator = User.objects.create_user(
            username='collab',
            password='password2',
            email='collab@example.com',
        )
        collaborator_profile, _ = UserProfile.objects.get_or_create(user=collaborator)
        collaborator_profile.nickname = '협업교사'
        collaborator_profile.save(update_fields=['nickname'])

        response = self.client.post(
            reverse('reservations:collaborator_add', args=[self.school.slug]),
            {
                'collaborator_query': collaborator.email,
                'can_edit': 'true',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            ReservationCollaborator.objects.filter(
                school=self.school,
                collaborator=collaborator,
                can_edit=True,
            ).exists()
        )
        
    def test_create_reservation(self):
        url = reverse('reservations:create_reservation', args=[self.school.slug])
        data = {
            'room_id': self.room.id,
            'date': self.target_date.strftime('%Y-%m-%d'),
            'period': 1,
            'grade': 6,
            'class_no': 1,
            'name': 'Tester',
            'edit_code': self.default_edit_code,
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        created = Reservation.objects.filter(room=self.room, date=self.target_date, period=1).first()
        self.assertIsNotNone(created)
        self.assertEqual(created.owner_key, build_reservation_owner_key(grade=6, class_no=1, name='Tester'))
        self.assertTrue(created.check_edit_code(self.default_edit_code))

        session = self.client.session
        self.assertIn(created.id, session.get('owned_reservation_ids', []))
        
        # Duplicate check
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 409)

    def test_create_reservation_with_custom_target_label(self):
        url = reverse('reservations:create_reservation', args=[self.school.slug])
        data = {
            'room_id': self.room.id,
            'date': self.target_date.strftime('%Y-%m-%d'),
            'period': 4,
            'target_label': '보건',
            'name': '김선생',
            'memo': '응급키트 점검',
            'edit_code': self.default_edit_code,
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)

        reservation = Reservation.objects.get(room=self.room, date=self.target_date, period=4)
        self.assertEqual(reservation.grade, 0)
        self.assertEqual(reservation.class_no, 0)
        self.assertEqual(reservation.target_label, '보건')
        self.assertEqual(reservation.name, '김선생')

    def test_create_reservation_requires_edit_code(self):
        response = self.client.post(
            reverse('reservations:create_reservation', args=[self.school.slug]),
            {
                'room_id': self.room.id,
                'date': self.target_date.strftime('%Y-%m-%d'),
                'period': 2,
                'grade': 6,
                'class_no': 1,
                'name': '무코드',
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('수정 코드 4자리를 입력해 주세요.', response.content.decode('utf-8'))

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

    def test_delete_reservation_htmx_triggers_grid_refresh(self):
        reservation = Reservation.objects.create(
            room=self.room,
            date=self.target_date,
            period=2,
            grade=5,
            class_no=2,
            name='HTMX Delete'
        )

        session = self.client.session
        session['owned_reservation_ids'] = [reservation.id]
        session.save()

        url = reverse('reservations:delete_reservation', args=[self.school.slug, reservation.id])
        response = self.client.post(url, HTTP_HX_REQUEST='true')

        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.headers.get('HX-Trigger'), 'refresh-reservations')
        self.assertFalse(Reservation.objects.filter(id=reservation.id).exists())

    def test_delete_reservation_missing_redirects_back_to_board(self):
        reservation = Reservation.objects.create(
            room=self.room,
            date=self.target_date,
            period=2,
            grade=5,
            class_no=2,
            name='Missing Delete',
        )
        reservation_id = reservation.id
        reservation.delete()

        session = self.client.session
        session['owned_reservation_ids'] = [reservation_id]
        session.save()

        url = reverse('reservations:delete_reservation', args=[self.school.slug, reservation_id])
        response = self.client.post(url)

        self.assertRedirects(response, reverse('reservations:reservation_index', args=[self.school.slug]))

    def test_delete_reservation_missing_htmx_redirects_back_to_board(self):
        reservation = Reservation.objects.create(
            room=self.room,
            date=self.target_date,
            period=2,
            grade=5,
            class_no=2,
            name='Missing HTMX Delete',
        )
        reservation_id = reservation.id
        reservation.delete()

        session = self.client.session
        session['owned_reservation_ids'] = [reservation_id]
        session.save()

        url = reverse('reservations:delete_reservation', args=[self.school.slug, reservation_id])
        response = self.client.post(url, HTTP_HX_REQUEST='true')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers.get('HX-Redirect'),
            reverse('reservations:reservation_index', args=[self.school.slug]),
        )

    def test_delete_reservation_by_creator_without_session_ownership(self):
        self.client.force_login(self.user)
        reservation = Reservation.objects.create(
            room=self.room,
            created_by=self.user,
            date=self.target_date,
            period=6,
            grade=4,
            class_no=1,
            name='Creator Delete'
        )

        # 세션 owned_reservation_ids 없이도 created_by가 본인이면 삭제 가능해야 한다.
        url = reverse('reservations:delete_reservation', args=[self.school.slug, reservation.id])
        response = self.client.post(url)

        self.assertRedirects(response, reverse('reservations:reservation_index', args=[self.school.slug]))
        self.assertFalse(Reservation.objects.filter(id=reservation.id).exists())

    def test_delete_reservation_by_matching_owner_profile_cookie(self):
        reservation = Reservation.objects.create(
            room=self.room,
            owner_key=build_reservation_owner_key(grade=2, class_no=3, name='이병주'),
            date=self.target_date,
            period=6,
            grade=2,
            class_no=3,
            name='이병주',
        )

        second_client = Client()
        self.set_owner_cookie(second_client, grade=2, class_no=3, name='이병주')

        url = reverse('reservations:delete_reservation', args=[self.school.slug, reservation.id])
        response = second_client.post(url)

        self.assertRedirects(response, reverse('reservations:reservation_index', args=[self.school.slug]))
        self.assertFalse(Reservation.objects.filter(id=reservation.id).exists())

    def test_delete_reservation_by_matching_edit_code_without_ownership(self):
        reservation = Reservation.objects.create(
            room=self.room,
            edit_code_hash=hash_reservation_edit_code('1357'),
            date=self.target_date,
            period=6,
            grade=2,
            class_no=3,
            name='이병주',
        )

        second_client = Client()
        url = reverse('reservations:delete_reservation', args=[self.school.slug, reservation.id])
        response = second_client.post(url, {'edit_code': '1357'}, HTTP_HX_REQUEST='true')

        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.headers.get('HX-Trigger'), 'refresh-reservations')
        self.assertFalse(Reservation.objects.filter(id=reservation.id).exists())

    def test_delete_reservation_rejects_wrong_edit_code_without_ownership(self):
        reservation = Reservation.objects.create(
            room=self.room,
            edit_code_hash=hash_reservation_edit_code('1357'),
            date=self.target_date,
            period=6,
            grade=2,
            class_no=3,
            name='이병주',
        )

        second_client = Client()
        url = reverse('reservations:delete_reservation', args=[self.school.slug, reservation.id])
        response = second_client.post(url, {'edit_code': '9999'}, HTTP_HX_REQUEST='true')

        self.assertEqual(response.status_code, 403)
        self.assertTrue(Reservation.objects.filter(id=reservation.id).exists())

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

    def test_claim_reservation_access_by_edit_code_restores_session_ownership(self):
        reservation = Reservation.objects.create(
            room=self.room,
            owner_key=build_reservation_owner_key(grade=2, class_no=3, name='이병주'),
            edit_code_hash=hash_reservation_edit_code('1357'),
            date=self.target_date,
            period=5,
            grade=2,
            class_no=3,
            name='이병주',
        )

        second_client = Client()
        response = second_client.post(
            reverse('reservations:claim_reservation_access', args=[self.school.slug, reservation.id]),
            {'edit_code': '1357'},
            HTTP_HX_REQUEST='true',
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(f"reservation={reservation.id}", response.headers.get('HX-Redirect'))
        self.assertIn(reservation.id, second_client.session.get('owned_reservation_ids', []))
        self.assertIn('reservation_owner_key', response.cookies)

    def test_claim_reservation_access_rejects_wrong_edit_code(self):
        reservation = Reservation.objects.create(
            room=self.room,
            edit_code_hash=hash_reservation_edit_code('1357'),
            date=self.target_date,
            period=5,
            grade=2,
            class_no=3,
            name='이병주',
        )

        second_client = Client()
        response = second_client.post(
            reverse('reservations:claim_reservation_access', args=[self.school.slug, reservation.id]),
            {'edit_code': '9999'},
            HTTP_HX_REQUEST='true',
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(second_client.session.get('owned_reservation_ids', []), [])

    def test_claim_reservation_access_redirects_when_reservation_missing(self):
        reservation = Reservation.objects.create(
            room=self.room,
            edit_code_hash=hash_reservation_edit_code('1357'),
            date=self.target_date,
            period=5,
            grade=2,
            class_no=3,
            name='이병주',
        )
        reservation_id = reservation.id
        reservation.delete()

        second_client = Client()
        response = second_client.post(
            reverse('reservations:claim_reservation_access', args=[self.school.slug, reservation_id]),
            {'edit_code': '1357'},
            HTTP_HX_REQUEST='true',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers.get('HX-Redirect'),
            reverse('reservations:reservation_index', args=[self.school.slug]),
        )

    def test_delete_reservation_forbidden_with_non_matching_owner_profile_cookie(self):
        reservation = Reservation.objects.create(
            room=self.room,
            owner_key=build_reservation_owner_key(grade=2, class_no=3, name='이병주'),
            date=self.target_date,
            period=5,
            grade=2,
            class_no=3,
            name='이병주',
        )

        second_client = Client()
        self.set_owner_cookie(second_client, grade=2, class_no=4, name='이병주')

        url = reverse('reservations:delete_reservation', args=[self.school.slug, reservation.id])
        response = second_client.post(url)

        self.assertEqual(response.status_code, 403)
        self.assertTrue(Reservation.objects.filter(id=reservation.id).exists())

    def test_update_reservation_by_creator(self):
        self.client.force_login(self.user)
        reservation = Reservation.objects.create(
            room=self.room,
            created_by=self.user,
            edit_code_hash=hash_reservation_edit_code(self.default_edit_code),
            date=self.target_date,
            period=2,
            grade=5,
            class_no=2,
            name='Before Update',
            memo='old memo',
        )

        url = reverse('reservations:update_reservation', args=[self.school.slug, reservation.id])
        response = self.client.post(url, {
            'room_id': self.room.id,
            'date': self.target_date.strftime('%Y-%m-%d'),
            'period': 2,
            'grade': 6,
            'class_no': 3,
            'name': 'After Update',
            'memo': 'new memo',
            'edit_code': '',
        })

        self.assertEqual(response.status_code, 200)
        reservation.refresh_from_db()
        self.assertEqual(reservation.grade, 6)
        self.assertEqual(reservation.class_no, 3)
        self.assertEqual(reservation.name, 'After Update')
        self.assertEqual(reservation.memo, 'new memo')

    def test_update_reservation_to_custom_target_by_creator(self):
        self.client.force_login(self.user)
        reservation = Reservation.objects.create(
            room=self.room,
            created_by=self.user,
            edit_code_hash=hash_reservation_edit_code(self.default_edit_code),
            date=self.target_date,
            period=5,
            grade=3,
            class_no=1,
            name='Before',
        )

        url = reverse('reservations:update_reservation', args=[self.school.slug, reservation.id])
        response = self.client.post(url, {
            'room_id': self.room.id,
            'date': self.target_date.strftime('%Y-%m-%d'),
            'period': 5,
            'target_label': '사서',
            'name': 'After',
            'memo': '도서관 수업',
            'edit_code': '',
        })

        self.assertEqual(response.status_code, 200)
        reservation.refresh_from_db()
        self.assertEqual(reservation.grade, 0)
        self.assertEqual(reservation.class_no, 0)
        self.assertEqual(reservation.target_label, '사서')
        self.assertEqual(reservation.name, 'After')

    def test_update_legacy_reservation_requires_new_edit_code(self):
        reservation = Reservation.objects.create(
            room=self.room,
            created_by=self.user,
            date=self.target_date,
            period=6,
            grade=2,
            class_no=1,
            name='Legacy',
        )

        url = reverse('reservations:update_reservation', args=[self.school.slug, reservation.id])
        response = self.client.post(url, {
            'room_id': self.room.id,
            'date': self.target_date.strftime('%Y-%m-%d'),
            'period': 6,
            'grade': 2,
            'class_no': 1,
            'name': 'Legacy',
            'edit_code': '',
        })

        self.assertEqual(response.status_code, 400)
        self.assertIn('예전 예약이라 수정 코드가 없습니다.', response.content.decode('utf-8'))

        response = self.client.post(url, {
            'room_id': self.room.id,
            'date': self.target_date.strftime('%Y-%m-%d'),
            'period': 6,
            'grade': 2,
            'class_no': 1,
            'name': 'Legacy',
            'edit_code': '1357',
        })

        self.assertEqual(response.status_code, 200)
        reservation.refresh_from_db()
        self.assertTrue(reservation.check_edit_code('1357'))

    def test_update_reservation_redirects_when_reservation_missing(self):
        reservation = Reservation.objects.create(
            room=self.room,
            created_by=self.user,
            edit_code_hash=hash_reservation_edit_code(self.default_edit_code),
            date=self.target_date,
            period=6,
            grade=2,
            class_no=1,
            name='Legacy',
        )
        reservation_id = reservation.id
        reservation.delete()

        url = reverse('reservations:update_reservation', args=[self.school.slug, reservation_id])
        response = self.client.post(url, {
            'room_id': self.room.id,
            'date': self.target_date.strftime('%Y-%m-%d'),
            'period': 6,
            'grade': 2,
            'class_no': 1,
            'name': 'Legacy',
            'edit_code': self.default_edit_code,
        }, HTTP_HX_REQUEST='true')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers.get('HX-Redirect'),
            reverse('reservations:reservation_index', args=[self.school.slug]),
        )

    def test_update_reservation_forbidden_without_ownership(self):
        other_user = User.objects.create_user(username='other', password='password2', email='other@example.com')
        reservation = Reservation.objects.create(
            room=self.room,
            created_by=other_user,
            date=self.target_date,
            period=3,
            grade=3,
            class_no=1,
            name='Protected Update',
        )

        url = reverse('reservations:update_reservation', args=[self.school.slug, reservation.id])
        response = self.client.post(url, {
            'room_id': self.room.id,
            'date': self.target_date.strftime('%Y-%m-%d'),
            'period': 3,
            'grade': 4,
            'class_no': 1,
            'name': 'Should Fail',
        })

        self.assertEqual(response.status_code, 403)
        reservation.refresh_from_db()
        self.assertEqual(reservation.name, 'Protected Update')

    def test_anonymous_create_reservation_works(self):
        self.client.logout()
        create_url = reverse('reservations:create_reservation', args=[self.school.slug])
        data = {
            'room_id': self.room.id,
            'date': self.target_date.strftime('%Y-%m-%d'),
            'period': 5,
            'grade': 6,
            'class_no': 3,
            'name': 'Anon Tester',
            'edit_code': self.default_edit_code,
        }
        response = self.client.post(create_url, data)
        self.assertEqual(response.status_code, 200)
        created = Reservation.objects.filter(room=self.room, date=self.target_date, period=5).first()
        self.assertIsNotNone(created)
        self.assertIsNone(created.created_by)
        self.assertEqual(created.owner_key, build_reservation_owner_key(grade=6, class_no=3, name='Anon Tester'))
        self.assertTrue(created.check_edit_code(self.default_edit_code))
        self.assertIn(created.id, self.client.session.get('owned_reservation_ids', []))
        self.assertIn('reservation_owner_key', response.cookies)

    def test_reservation_grid_shows_profile_matched_reservation_as_editable(self):
        reservation = Reservation.objects.create(
            room=self.room,
            owner_key=build_reservation_owner_key(grade=2, class_no=3, name='이병주'),
            date=self.target_date,
            period=2,
            grade=2,
            class_no=3,
            name='이병주',
        )

        anonymous_client = Client()
        self.set_owner_cookie(anonymous_client, grade=2, class_no=3, name='이병주')

        response = anonymous_client.get(
            reverse('reservations:reservation_index', args=[self.school.slug]),
            HTTP_HX_REQUEST='true',
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('reservations:delete_reservation', args=[self.school.slug, reservation.id]))

    def test_authenticated_create_shows_followup_summary_on_next_page(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('reservations:create_reservation', args=[self.school.slug]),
            {
                'room_id': self.room.id,
                'date': self.target_date.strftime('%Y-%m-%d'),
                'period': 1,
                'grade': 4,
                'class_no': 2,
                'name': '김선생',
                'memo': '실험 수업',
                'edit_code': self.default_edit_code,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get('HX-Refresh'), 'true')

        page = self.client.get(reverse('reservations:reservation_index', args=[self.school.slug]))
        self.assertContains(page, '방금 예약한 내용')
        self.assertContains(page, '실험 수업')
        self.assertContains(page, self.default_edit_code)
        self.assertNotContains(page, '안내문으로 이어서 만들기')
        self.assertNotContains(page, '학부모 연락으로 이어서 하기')

    def test_start_notice_followup_stores_seed_and_redirects(self):
        self.client.force_login(self.user)
        reservation = Reservation.objects.create(
            room=self.room,
            created_by=self.user,
            date=self.target_date,
            period=2,
            grade=5,
            class_no=1,
            name='홍교사',
            memo='준비물 확인',
        )

        response = self.client.post(reverse('reservations:start_notice_followup', args=[self.school.slug, reservation.id]))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('noticegen:main'), response['Location'])
        seed_token = response['Location'].split('sb_seed=')[-1]
        session = self.client.session
        workflow_seed = session['workflow_action_seeds'][seed_token]
        self.assertEqual(workflow_seed['action'], 'notice')
        self.assertEqual(workflow_seed['data']['origin_service'], 'reservations')
        self.assertIn('Science Room', workflow_seed['data']['keywords'])

    def test_start_parentcomm_followup_stores_seed_and_redirects(self):
        self.client.force_login(self.user)
        reservation = Reservation.objects.create(
            room=self.room,
            created_by=self.user,
            date=self.target_date,
            period=3,
            grade=6,
            class_no=4,
            name='박교사',
            memo='보호자 준비물 안내',
        )

        response = self.client.post(reverse('reservations:start_parentcomm_followup', args=[self.school.slug, reservation.id]))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('parentcomm:main'), response['Location'])
        seed_token = response['Location'].split('sb_seed=')[-1]
        session = self.client.session
        workflow_seed = session['workflow_action_seeds'][seed_token]
        self.assertEqual(workflow_seed['action'], 'parentcomm_notice')
        self.assertEqual(workflow_seed['data']['origin_service'], 'reservations')
        self.assertIn('Science Room', workflow_seed['data']['title'])

    def test_admin_dashboard_share_copy_has_failure_feedback(self):
        response = self.client.get(reverse('reservations:admin_dashboard', args=[self.school.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "copyError: '',", html=False)
        self.assertContains(response, 'navigator.clipboard.writeText(this.shareUrl).then(() => {', html=False)
        self.assertContains(response, '복사에 실패했습니다. 다시 시도해 주세요.')
        self.assertContains(response, '공유할 선생님 추가')
        self.assertContains(response, '로그인 없이 열림')
        self.assertContains(response, '학교 목록')
        self.assertNotContains(response, '내 학교 목록')

    def test_grade_lock_settings_get_renders_matrix(self):
        response = self.client.get(reverse('reservations:grade_lock_settings', args=[self.school.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '칸을 눌러 학년을 바로 고정하거나 해제합니다.')
        self.assertContains(response, 'Science Room')
        self.assertContains(response, '1학년')
        self.assertContains(response, '학년 고정')

    def test_grade_lock_settings_can_set_update_and_delete_by_slot(self):
        url = reverse('reservations:grade_lock_settings', args=[self.school.slug])

        response = self.client.post(url, {
            'action': 'set',
            'room_id': self.room.id,
            'day_of_week': 1,
            'period': 2,
            'grade': 2,
        })

        self.assertEqual(response.status_code, 200)
        lock = GradeRecurringLock.objects.get(room=self.room, day_of_week=1, period=2)
        self.assertEqual(lock.grade, 2)

        response = self.client.post(url, {
            'action': 'set',
            'room_id': self.room.id,
            'day_of_week': 1,
            'period': 2,
            'grade': 5,
        })

        self.assertEqual(response.status_code, 200)
        lock.refresh_from_db()
        self.assertEqual(lock.grade, 5)

        response = self.client.post(url, {
            'action': 'delete',
            'room_id': self.room.id,
            'day_of_week': 1,
            'period': 2,
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(GradeRecurringLock.objects.filter(room=self.room, day_of_week=1, period=2).exists())

    def test_grade_lock_settings_rejects_slots_with_recurring_schedule(self):
        RecurringSchedule.objects.create(
            room=self.room,
            day_of_week=2,
            period=3,
            name='6-1 고정수업',
        )

        response = self.client.post(
            reverse('reservations:grade_lock_settings', args=[self.school.slug]),
            {
                'action': 'set',
                'room_id': self.room.id,
                'day_of_week': 2,
                'period': 3,
                'grade': 4,
            },
        )

        self.assertEqual(response.status_code, 409)
        self.assertIn('이미 고정 수업이 있어', response.content.decode('utf-8'))
        self.assertFalse(GradeRecurringLock.objects.filter(room=self.room, day_of_week=2, period=3).exists())

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

    def test_admin_delete_reservation_htmx_triggers_grid_refresh(self):
        reservation = Reservation.objects.create(
            room=self.room,
            date=self.target_date,
            period=3,
            grade=3,
            class_no=3,
            name='Admin HTMX Delete'
        )
        self.client.force_login(self.user)
        url = reverse('reservations:admin_delete_reservation', args=[self.school.slug, reservation.id])
        response = self.client.post(url, HTTP_HX_REQUEST='true')

        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.headers.get('HX-Trigger'), 'refresh-reservations')
        self.assertFalse(Reservation.objects.filter(id=reservation.id).exists())

    def test_admin_delete_reservation_missing_htmx_redirects_back_to_board(self):
        reservation = Reservation.objects.create(
            room=self.room,
            date=self.target_date,
            period=3,
            grade=3,
            class_no=3,
            name='Missing Admin Delete',
        )
        reservation_id = reservation.id
        reservation.delete()

        url = reverse('reservations:admin_delete_reservation', args=[self.school.slug, reservation_id])
        response = self.client.post(url, HTTP_HX_REQUEST='true')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers.get('HX-Redirect'),
            reverse('reservations:reservation_index', args=[self.school.slug]),
        )

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
            'name': 'Tester',
            'edit_code': self.default_edit_code,
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Reservation.objects.filter(room=self.room, date=self.target_date).exists())

    def test_period_times_are_rendered_in_grid(self):
        self.config.period_labels = "1교시,2교시"
        self.config.period_times = "09:00-09:40,09:50-10:30"
        self.config.save()

        url = reverse('reservations:reservation_index', args=[self.school.slug])
        response = self.client.get(url, HTTP_HX_REQUEST='true')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "09:00-09:40")
        self.assertContains(response, "09:50-10:30")

    def test_update_config_saves_optional_period_times(self):
        self.client.force_login(self.user)
        url = reverse('reservations:update_config', args=[self.school.slug])
        response = self.client.post(url, {
            'school_name': self.school.name,
            'period_labels': '1교시,2교시,3교시',
            'period_times': '09:00-09:40,09:50-10:30,',
        })

        self.assertEqual(response.status_code, 200)
        self.config.refresh_from_db()
        self.assertEqual(self.config.period_labels, '1교시,2교시,3교시')
        self.assertEqual(self.config.period_times, '09:00-09:40,09:50-10:30')

    def test_booking_form_uses_examples_and_opt_in_local_storage(self):
        url = reverse('reservations:reservation_index', args=[self.school.slug])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "예: 홍길동")
        self.assertContains(response, "remember_reservation_info")
        self.assertContains(response, "my_reservation_info")
        self.assertContains(response, "reservation_edit_code")
        self.assertContains(response, "reservation_profile_version")
        self.assertContains(response, "학년/반 또는 역할을 다시 입력")
        self.assertContains(response, "수정 코드 4자리")

    def test_grade_lock_blocks_different_grade_without_override(self):
        GradeRecurringLock.objects.create(
            room=self.room,
            day_of_week=self.target_date.weekday(),
            period=1,
            grade=3,
        )

        url = reverse('reservations:create_reservation', args=[self.school.slug])
        response = self.client.post(url, {
            'room_id': self.room.id,
            'date': self.target_date.strftime('%Y-%m-%d'),
            'period': 1,
            'grade': 4,
            'class_no': 1,
            'name': 'Tester',
            'edit_code': self.default_edit_code,
        })

        self.assertEqual(response.status_code, 409)
        self.assertIn("3학년 고정", response.content.decode('utf-8'))
        self.assertFalse(Reservation.objects.filter(room=self.room, date=self.target_date, period=1).exists())
        self.assertTrue(GradeRecurringLock.objects.filter(room=self.room, day_of_week=self.target_date.weekday(), period=1).exists())

    def test_grade_lock_override_allows_booking_and_keeps_lock_for_future_weeks(self):
        GradeRecurringLock.objects.create(
            room=self.room,
            day_of_week=self.target_date.weekday(),
            period=2,
            grade=2,
        )

        url = reverse('reservations:create_reservation', args=[self.school.slug])
        response = self.client.post(url, {
            'room_id': self.room.id,
            'date': self.target_date.strftime('%Y-%m-%d'),
            'period': 2,
            'grade': 5,
            'class_no': 1,
            'name': 'Tester',
            'override_grade_lock': '1',
            'edit_code': self.default_edit_code,
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get('HX-Refresh'), 'true')
        self.assertTrue(Reservation.objects.filter(room=self.room, date=self.target_date, period=2).exists())
        self.assertTrue(GradeRecurringLock.objects.filter(room=self.room, day_of_week=self.target_date.weekday(), period=2).exists())

    def test_update_grade_lock_override_keeps_lock_for_future_weeks(self):
        GradeRecurringLock.objects.create(
            room=self.room,
            day_of_week=self.target_date.weekday(),
            period=4,
            grade=2,
        )
        reservation = Reservation.objects.create(
            room=self.room,
            created_by=self.user,
            edit_code_hash=hash_reservation_edit_code(self.default_edit_code),
            date=self.target_date,
            period=4,
            grade=2,
            class_no=1,
            name='Before',
        )

        url = reverse('reservations:update_reservation', args=[self.school.slug, reservation.id])
        response = self.client.post(url, {
            'room_id': self.room.id,
            'date': self.target_date.strftime('%Y-%m-%d'),
            'period': 4,
            'grade': 5,
            'class_no': 1,
            'name': 'After',
            'override_grade_lock': '1',
            'edit_code': '',
        })

        self.assertEqual(response.status_code, 200)
        reservation.refresh_from_db()
        self.assertEqual(reservation.grade, 5)
        self.assertEqual(reservation.name, 'After')
        self.assertTrue(GradeRecurringLock.objects.filter(room=self.room, day_of_week=self.target_date.weekday(), period=4).exists())

    def test_grade_lock_same_grade_reserves_without_unlock(self):
        GradeRecurringLock.objects.create(
            room=self.room,
            day_of_week=self.target_date.weekday(),
            period=3,
            grade=6,
        )

        url = reverse('reservations:create_reservation', args=[self.school.slug])
        response = self.client.post(url, {
            'room_id': self.room.id,
            'date': self.target_date.strftime('%Y-%m-%d'),
            'period': 3,
            'grade': 6,
            'class_no': 2,
            'name': 'Tester',
            'edit_code': self.default_edit_code,
        })

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Reservation.objects.filter(room=self.room, date=self.target_date, period=3).exists())
        self.assertTrue(GradeRecurringLock.objects.filter(room=self.room, day_of_week=self.target_date.weekday(), period=3).exists())

    def test_room_overview_allows_public_link_and_groups_by_room(self):
        second_room = SpecialRoom.objects.create(school=self.school, name='Music Room', icon='🎵')
        Reservation.objects.create(
            room=self.room,
            date=self.target_date,
            period=1,
            grade=3,
            class_no=2,
            name='Alpha',
            memo='실험',
        )
        Reservation.objects.create(
            room=second_room,
            date=self.target_date,
            period=2,
            grade=5,
            class_no=1,
            name='Beta',
        )

        self.client.logout()
        url = reverse('reservations:room_overview', args=[self.school.slug])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '특별실별 예약 현황')
        self.assertContains(response, 'Science Room')
        self.assertContains(response, 'Music Room')
        self.assertContains(response, 'Alpha')
        self.assertContains(response, 'Beta')

    def test_room_overview_respects_date_range_filter(self):
        Reservation.objects.create(
            room=self.room,
            date=self.target_date,
            period=1,
            grade=4,
            class_no=1,
            name='In Range',
        )
        Reservation.objects.create(
            room=self.room,
            date=self.target_date + timedelta(days=10),
            period=2,
            grade=4,
            class_no=2,
            name='Out Of Range',
        )

        url = reverse('reservations:room_overview', args=[self.school.slug])
        response = self.client.get(url, {
            'from': self.target_date.strftime('%Y-%m-%d'),
            'days': 7,
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'In Range')
        self.assertNotContains(response, 'Out Of Range')

    def test_room_overview_displays_custom_target_label(self):
        Reservation.objects.create(
            room=self.room,
            date=self.target_date,
            period=6,
            grade=0,
            class_no=0,
            target_label='영양',
            name='박선생',
        )

        url = reverse('reservations:room_overview', args=[self.school.slug])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '영양 박선생')
