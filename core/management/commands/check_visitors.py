from django.core.management.base import BaseCommand
from django.db import connection
from core.models import VisitorLog
from django.utils import timezone


class Command(BaseCommand):
    help = '방문자 기록 상태를 확인합니다'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=== 방문자 기록 상태 확인 ===\n'))

        # 1. 테이블 존재 여부 확인
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_name = 'core_visitorlog'
                """)
                table_exists = cursor.fetchone()

                if table_exists:
                    self.stdout.write(self.style.SUCCESS('✓ core_visitorlog 테이블 존재'))
                else:
                    self.stdout.write(self.style.ERROR('✗ core_visitorlog 테이블이 존재하지 않습니다!'))
                    self.stdout.write(self.style.WARNING('  → python manage.py migrate를 실행하세요'))
                    return
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'테이블 확인 중 오류: {e}'))

        # 2. 데이터 개수 확인
        try:
            today = timezone.localdate()
            total_count = VisitorLog.objects.count()
            today_count = VisitorLog.objects.filter(visit_date=today).count()

            self.stdout.write(self.style.SUCCESS(f'✓ 전체 방문 기록: {total_count}개'))
            self.stdout.write(self.style.SUCCESS(f'✓ 오늘 방문 기록: {today_count}개'))

            # 최근 5개 기록 출력
            recent_logs = VisitorLog.objects.order_by('-visit_date', '-id')[:5]
            if recent_logs:
                self.stdout.write(self.style.SUCCESS('\n최근 방문 기록:'))
                for log in recent_logs:
                    self.stdout.write(f'  - {log.visit_date} | {log.ip_address}')
            else:
                self.stdout.write(self.style.WARNING('\n⚠ 방문 기록이 없습니다.'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'데이터 조회 중 오류: {e}'))

        # 3. 테스트 데이터 추가
        try:
            test_ip = '127.0.0.1'
            today = timezone.localdate()
            obj, created = VisitorLog.objects.get_or_create(
                ip_address=test_ip,
                visit_date=today
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'\n✓ 테스트 기록 추가됨: {test_ip}'))
            else:
                self.stdout.write(self.style.SUCCESS(f'\n✓ 테스트 기록 이미 존재: {test_ip}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n✗ 테스트 기록 추가 실패: {e}'))

        self.stdout.write(self.style.SUCCESS('\n=== 확인 완료 ==='))
