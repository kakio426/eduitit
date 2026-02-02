"""
Django management command to generate 16 MBTI share card images.
Usage: python manage.py generate_share_cards
"""
from django.core.management.base import BaseCommand
from django.conf import settings
import os


class Command(BaseCommand):
    help = 'Generate 16 MBTI share card images'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting share card generation...'))
        
        # MBTI types
        mbti_types = [
            'ISTJ', 'ISFJ', 'INFJ', 'INTJ',
            'ISTP', 'ISFP', 'INFP', 'INTP',
            'ESTP', 'ESFP', 'ENFP', 'ENTP',
            'ESTJ', 'ESFJ', 'ENFJ', 'ENTJ'
        ]
        
        # Create output directory
        output_dir = os.path.join(settings.STATIC_ROOT or settings.BASE_DIR / 'static', 
                                  'ssambti', 'images', 'share_cards')
        os.makedirs(output_dir, exist_ok=True)
        
        self.stdout.write(f'Output directory: {output_dir}')
        self.stdout.write(self.style.WARNING(
            '\n⚠️  MANUAL STEP REQUIRED:\n'
            '1. Run the development server: python manage.py runserver\n'
            '2. Visit each MBTI result page\n'
            '3. Click "이미지 저장/공유" button\n'
            '4. Save each image as: {MBTI_TYPE}_card.png\n'
            '5. Move all 16 images to: ' + output_dir + '\n'
        ))
        
        self.stdout.write(self.style.SUCCESS(
            f'\n✅ Ready to generate {len(mbti_types)} cards\n'
            f'Expected files:\n'
        ))
        
        for mbti in mbti_types:
            filename = f'{mbti}_card.png'
            self.stdout.write(f'  - {filename}')
