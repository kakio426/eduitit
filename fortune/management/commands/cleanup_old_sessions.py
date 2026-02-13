from django.core.management.base import BaseCommand
from django.utils import timezone
from fortune.models import ChatSession

class Command(BaseCommand):
    help = 'Deletes expired chat sessions (older than expiration date)'

    def handle(self, *args, **options):
        now = timezone.now()
        # Find sessions where expires_at < now
        expired_sessions = ChatSession.objects.filter(expires_at__lt=now)
        count = expired_sessions.count()
        
        if count > 0:
            # delete() returns (total_count, per_object_dict) since Django 1.9+
            deleted, _ = expired_sessions.delete()
            self.stdout.write(self.style.SUCCESS(f'Successfully deleted {deleted} expired chat sessions.'))
        else:
            self.stdout.write(self.style.SUCCESS('No expired sessions found.'))
