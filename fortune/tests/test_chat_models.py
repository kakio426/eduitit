from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import get_user_model
from fortune.models import ChatSession, ChatMessage, UserSajuProfile

User = get_user_model()

class TestChatModels(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')
        self.profile = UserSajuProfile.objects.create(
            user=self.user,
            profile_name='MyProfile',
            person_name='TestUser',
            birth_year=1990,
            birth_month=1,
            birth_day=1,
            birth_hour=14,  # Change 'A' to int
            birth_minute=0,
            calendar_type='solar',
            gender='male'
        )

    def test_chat_session_creation(self):
        """Test ChatSession creation with default values."""
        session = ChatSession.objects.create(
            user=self.user,
            profile=self.profile
        )
        
        self.assertIsNotNone(session.id)
        self.assertEqual(session.user, self.user)
        self.assertEqual(session.profile, self.profile)
        self.assertTrue(session.is_active)
        self.assertEqual(session.current_turns, 0)
        self.assertEqual(session.max_turns, 10)  # Default limit
        
        # Check expires_at is roughly 7 days from now
        expected_expiry = timezone.now() + timedelta(days=7)
        # Allow 1 second difference
        delta = abs((session.expires_at - expected_expiry).total_seconds())
        self.assertLess(delta, 5)

    def test_chat_message_creation(self):
        """Test ChatMessage creation linked to a session."""
        session = ChatSession.objects.create(
            user=self.user,
            profile=self.profile
        )
        message = ChatMessage.objects.create(
            session=session,
            role='user',
            content='Hello teacher!'
        )
        
        self.assertIsNotNone(message.id)
        self.assertEqual(message.session, session)
        self.assertEqual(message.role, 'user')
        self.assertEqual(message.content, 'Hello teacher!')
        self.assertIsNotNone(message.created_at)

    def test_session_str_representation(self):
        """Test string representation of ChatSession."""
        session = ChatSession.objects.create(
            user=self.user,
            profile=self.profile
        )
        self.assertIn(self.user.username, str(session))
        self.assertIn("Active", str(session))

    def test_message_str_representation(self):
        """Test string representation of ChatMessage."""
        session = ChatSession.objects.create(
            user=self.user,
            profile=self.profile
        )
        message = ChatMessage.objects.create(
            session=session,
            role='assistant',
            content='Hello student.'
        )
        self.assertIn('assistant', str(message))
        self.assertIn('Hello student.', str(message))
