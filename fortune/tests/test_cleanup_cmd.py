from django.test import TestCase
from django.core.management import call_command
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import get_user_model
from fortune.models import ChatSession, UserSajuProfile
from io import StringIO

User = get_user_model()

class TestCleanupCommand(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='test', password='pw')
        self.profile = UserSajuProfile.objects.create(
            user=self.user,
            profile_name='p1',
            person_name='u1',
            birth_year=1990, birth_month=1, birth_day=1, gender='male'
        )
    
    def test_cleanup_deletes_expired(self):
        # Create expired session
        expired = ChatSession.objects.create(user=self.user, profile=self.profile)
        # Override save logic that sets default expires_at?
        # save() sets expires_at ONLY if not set.
        # But create() sets it via save().
        # So we update it after create.
        expired.expires_at = timezone.now() - timedelta(minutes=1)
        expired.save() # This save might trigger deactivated logic but that's fine.
        
        # Create valid session (active)
        valid = ChatSession.objects.create(user=self.user, profile=self.profile)
        # valid.expires_at is +7 days default.
        
        out = StringIO()
        call_command('cleanup_old_sessions', stdout=out)
        
        self.assertFalse(ChatSession.objects.filter(id=expired.id).exists())
        self.assertTrue(ChatSession.objects.filter(id=valid.id).exists())
        self.assertIn("Successfully deleted", out.getvalue())
