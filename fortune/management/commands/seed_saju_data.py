from django.core.management.base import BaseCommand
from fortune.models import Stem, Branch, SixtyJiazi

class Command(BaseCommand):
    help = 'Seeds initial Saju data (Stems, Branches, 60 Jiazi)'

    def handle(self, *args, **kwargs):
        stems_data = [
            ('Gap', '甲', 'yang', 'wood'), 
            ('Eul', '乙', 'yin', 'wood'),
            ('Byung', '丙', 'yang', 'fire'), 
            ('Jung', '丁', 'yin', 'fire'),
            ('Moo', '戊', 'yang', 'earth'), 
            ('Gi', '己', 'yin', 'earth'),
            ('Gyung', '庚', 'yang', 'metal'), 
            ('Shin', '辛', 'yin', 'metal'),
            ('Im', '壬', 'yang', 'water'), 
            ('Gye', '癸', 'yin', 'water'),
        ]
        
        branches_data = [
            ('Ja', '子', 'yang', 'water'), 
            ('Chuk', '丑', 'yin', 'earth'),
            ('In', '寅', 'yang', 'wood'), 
            ('Myo', '卯', 'yin', 'wood'),
            ('Jin', '辰', 'yang', 'earth'), 
            ('Sa', '巳', 'yin', 'fire'),
            ('O', '午', 'yang', 'fire'), 
            ('Mi', '未', 'yin', 'earth'),
            ('Shin', '申', 'yang', 'metal'), 
            ('Yoo', '酉', 'yin', 'metal'),
            ('Sool', '戌', 'yang', 'earth'), 
            ('Hae', '亥', 'yin', 'water'),
        ]

        stems = []
        for name, char, pol, elem in stems_data:
            s, _ = Stem.objects.update_or_create(
                character=char,
                defaults={'name': name, 'polarity': pol, 'element': elem}
            )
            stems.append(s)
            self.stdout.write(f'Stem {char} ({name}) processed')

        branches = []
        for name, char, pol, elem in branches_data:
            b, _ = Branch.objects.update_or_create(
                character=char,
                defaults={'name': name, 'polarity': pol, 'element': elem}
            )
            branches.append(b)
            self.stdout.write(f'Branch {char} ({name}) processed')

        # 60 Jiazi
        self.stdout.write('Generating 60 Jiazi...')
        for i in range(60):
            stem = stems[i % 10]
            branch = branches[i % 12]
            name = f"{stem.name}-{branch.name}"
            # Na Yin or other properties can be added later
            SixtyJiazi.objects.update_or_create(
                stem=stem, 
                branch=branch,
                defaults={'name': name}
            )
        
        self.stdout.write(self.style.SUCCESS('Successfully seeded Saju data'))
