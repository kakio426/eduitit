from django.test import TestCase
from django.utils import timezone
from .models import Achievement, LectureProgram, Inquiry

class AchievementModelTest(TestCase):
    def test_create_achievement(self):
        """Test creating an achievement"""
        achievement = Achievement.objects.create(
            title="Django Award",
            issuer="Django Software Foundation",
            date_awarded=timezone.now().date(),
            description="Best Django Project"
        )
        self.assertEqual(achievement.title, "Django Award")
        self.assertTrue(Achievement.objects.filter(id=achievement.id).exists())

class LectureProgramModelTest(TestCase):
    def test_create_program(self):
        """Test creating a lecture program"""
        program = LectureProgram.objects.create(
            title="Intro to Python",
            description="Basic Python course",
            target_audience="Beginners",
            duration="2 hours",
            syllabus="1. Setup 2. Variables"
        )
        self.assertEqual(program.title, "Intro to Python")
        self.assertTrue(program.is_active)

class InquiryModelTest(TestCase):
    def test_create_inquiry(self):
        """Test creating an inquiry"""
        inquiry = Inquiry.objects.create(
            name="John Doe",
            organization="Test Corp",
            email="john@example.com",
            phone="010-1234-5678",
            topic="Lecture Request",
            message="Please come teach us."
        )
        self.assertEqual(inquiry.email, "john@example.com")
        self.assertFalse(inquiry.is_reviewed)

from .forms import InquiryForm

class InquiryFormTest(TestCase):
    def test_valid_form(self):
        data = {
            'name': 'Jane Doe',
            'organization': 'School',
            'email': 'jane@school.edu',
            'phone': '010-9876-5432',
            'topic': 'AI Education',
            'message': 'We need a workshop.'
        }
        form = InquiryForm(data=data)
        self.assertTrue(form.is_valid())

        data = {'name': '', 'email': 'invalid'}
        form = InquiryForm(data=data)
        self.assertFalse(form.is_valid())

from django.urls import reverse

class PortfolioViewTest(TestCase):
    def test_portfolio_page_status(self):
        response = self.client.get(reverse('portfolio:list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'portfolio/portfolio_list.html')

    def test_inquiry_create_view(self):
        response = self.client.get(reverse('portfolio:inquiry'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'portfolio/inquiry_form.html')

        data = {
            'name': 'Inquirer',
            'organization': 'Org',
            'email': 'i@org.com',
            'phone': '123',
            'topic': 'Topic',
            'message': 'Message'
        }
        response = self.client.post(reverse('portfolio:inquiry'), data)
        self.assertRedirects(response, reverse('portfolio:inquiry_success')) # Assume success url
        self.assertTrue(Inquiry.objects.filter(email='i@org.com').exists())
