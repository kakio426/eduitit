
import os
import sys
import django
import re

# Setup Django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from products.models import ManualSection, ServiceManual, Product, ProductFeature

def clean_text(text):
    if not text: return ""
    # Convert literal \n
    text = text.replace('\\n', '\n')
    # Remove MD
    text = re.sub(r'#+\s*', '', text)
    text = re.sub(r'\*+', '', text)
    text = re.sub(r'>\s*', '', text)
    text = re.sub(r'`+', '', text)
    return text.strip()

def fix_all():
    models = [ManualSection, ServiceManual, Product, ProductFeature]
    for model in models:
        print(f"Cleaning {model.__name__}...")
        for obj in model.objects.all():
            if model == ManualSection:
                fields = ['content']
            elif model == ServiceManual:
                fields = ['description']
            elif model == Product:
                fields = ['description', 'lead_text']
            elif model == ProductFeature:
                fields = ['description']
            
            changed = False
            for f in fields:
                old = getattr(obj, f) or ""
                new = clean_text(old)
                if old != new:
                    setattr(obj, f, new)
                    changed = True
            
            if changed:
                obj.save()
                print(f"  [OK] Fixed {model.__name__} ID: {obj.id}")

if __name__ == '__main__':
    fix_all()
