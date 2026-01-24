"""
DB에서 중복된 SocialApp 레코드를 정리하는 관리 커맨드.
코드 기반 설정(SOCIALACCOUNT_PROVIDERS)을 사용할 때 DB에 남아있는 레코드로 인한 충돌을 방지합니다.

사용법:
    python manage.py clear_social_apps
"""
from django.core.management.base import BaseCommand
from allauth.socialaccount.models import SocialApp


class Command(BaseCommand):
    help = 'DB에서 모든 SocialApp 레코드를 삭제합니다 (코드 기반 설정 사용 시 필요)'

    def handle(self, *args, **options):
        count = SocialApp.objects.count()
        if count == 0:
            self.stdout.write(self.style.WARNING('삭제할 SocialApp 레코드가 없습니다.'))
            return
        
        SocialApp.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f'{count}개의 SocialApp 레코드가 삭제되었습니다.'))
