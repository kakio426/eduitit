"""
Management command to ensure Ssambti product exists in database.

Usage:
    python manage.py ensure_ssambti

This command can be run multiple times safely - it will only create
the product if it doesn't exist, or update it if settings changed.
"""

from django.core.management.base import BaseCommand
from products.models import Product


class Command(BaseCommand):
    help = 'Ensure Ssambti product exists in database with correct settings'

    def handle(self, *args, **options):
        self.stdout.write('=' * 70)
        self.stdout.write(self.style.WARNING('[Ssambti Product Setup]'))
        self.stdout.write('=' * 70)

        # Check if product exists
        ssambti = Product.objects.filter(title='쌤BTI').first()

        if ssambti:
            self.stdout.write(self.style.WARNING(f'[!] Found existing Ssambti product (ID: {ssambti.id})'))
            self.stdout.write(f'  - Current external_url: "{ssambti.external_url}"')
            self.stdout.write(f'  - Current service_type: {ssambti.service_type}')
            self.stdout.write(f'  - Current display_order: {ssambti.display_order}')

            # Update if needed
            needs_update = False
            if ssambti.external_url != '':
                self.stdout.write(self.style.ERROR('  [X] external_url is not empty!'))
                ssambti.external_url = ''
                needs_update = True

            if ssambti.service_type != 'game':
                self.stdout.write(self.style.ERROR(f'  [X] service_type is "{ssambti.service_type}", should be "game"'))
                ssambti.service_type = 'game'
                needs_update = True

            if not ssambti.is_active:
                self.stdout.write(self.style.ERROR('  [X] is_active is False!'))
                ssambti.is_active = True
                needs_update = True

            if needs_update:
                ssambti.save()
                self.stdout.write(self.style.SUCCESS('[OK] Updated Ssambti product with correct settings'))
            else:
                self.stdout.write(self.style.SUCCESS('[OK] Ssambti product already has correct settings'))

        else:
            self.stdout.write(self.style.WARNING('[!] Ssambti product not found, creating...'))

            # Create new product
            ssambti = Product.objects.create(
                title='쌤BTI',
                lead_text='나는 어떤 선생님일까? 🦁',
                description='12가지 질문으로 알아보는 나의 교육 스타일! MBTI 기반 티처블 동물원에서 나와 닮은 동물을 찾아보세요.',
                price=0.00,
                is_active=True,
                is_featured=False,
                is_guest_allowed=True,
                icon='🦁',
                color_theme='orange',
                card_size='small',
                display_order=13,
                service_type='game',
                external_url='',  # CRITICAL: Must be empty for internal service
            )
            self.stdout.write(self.style.SUCCESS(f'[OK] Created Ssambti product (ID: {ssambti.id})'))

        # Final summary - ASCII-safe output
        self.stdout.write('')
        self.stdout.write('=' * 70)
        self.stdout.write(self.style.SUCCESS('[Final Product Details]'))
        self.stdout.write('=' * 70)
        try:
            self.stdout.write(f'  ID: {ssambti.id}')
            self.stdout.write(f'  Title: {ssambti.title}')
            self.stdout.write(f'  Icon: {repr(ssambti.icon)}')  # Use repr() for safe output
            self.stdout.write(f'  Service Type: {ssambti.service_type}')
            self.stdout.write(f'  Color Theme: {ssambti.color_theme}')
            self.stdout.write(f'  Display Order: {ssambti.display_order}')
            self.stdout.write(f'  External URL: "{ssambti.external_url}" (should be empty)')
            self.stdout.write(f'  Is Active: {ssambti.is_active}')
            self.stdout.write(f'  Is Guest Allowed: {ssambti.is_guest_allowed}')
        except UnicodeEncodeError:
            self.stdout.write('  [Details contain non-ASCII characters - skipping display]')

        self.stdout.write('=' * 70)
        self.stdout.write(self.style.SUCCESS('[OK] Done!'))
        self.stdout.write('')

        # Count total products
        total = Product.objects.count()
        self.stdout.write(self.style.SUCCESS(f'[INFO] Total products in database: {total}'))
        self.stdout.write('')
