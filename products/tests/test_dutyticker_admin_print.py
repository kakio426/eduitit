from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from core.models import UserProfile
from products.models import DTRole, DTRoleAssignment, DTStudent


class DutyTickerAdminPrintTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='teacher', password='pw1234', email='teacher@example.com')
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.nickname = '담임교사'
        profile.save()
        self.url = reverse('dt_admin_print_sheet')

    def test_print_sheet_requires_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_print_sheet_renders_role_assignment_with_description(self):
        self.client.login(username='teacher', password='pw1234')
        student = DTStudent.objects.create(user=self.user, name='김철수', number=1)
        role = DTRole.objects.create(
            user=self.user,
            name='칠판 지우기',
            time_slot='쉬는시간',
            description='수업 후 칠판을 깨끗하게 정리합니다.',
        )
        DTRoleAssignment.objects.create(user=self.user, role=role, student=student)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'products/dutyticker/print_sheet.html')
        self.assertContains(response, '1인 1역 배정표')
        self.assertContains(response, '칠판 지우기')
        self.assertContains(response, '쉬는시간')
        self.assertContains(response, '김철수')
        self.assertContains(response, '수업 후 칠판을 깨끗하게 정리합니다.')
