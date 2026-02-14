
import os
import sys
import django
import re

# Setup Django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from products.models import ManualSection

def fix_one():
    s = ManualSection.objects.filter(manual__product__title__icontains='예약').first()
    if s:
        old = s.content
        print(f"BEFORE: {repr(old)}")
        
        # Manually perform steps
        new = old.replace('\\n', '\n')
        new = re.sub(r'#+\s*', '', new)
        new = re.sub(r'\*+', '', new)
        new = re.sub(r'>\s*', '', new)
        
        print(f"AFTER: {repr(new)}")
        
        if old != new:
            s.content = new
            s.save()
            print("SAVED!")

if __name__ == '__main__':
    fix_one()
