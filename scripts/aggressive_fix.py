
import os
import sys
import django
import re

# Setup Django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from products.models import ManualSection, ServiceManual, Product, ProductFeature

def clean_markdown_aggressive(text):
    if not text:
        return ""
    
    # 1. Convert literal \n strings to real newlines
    text = text.replace('\\n', '\n')
    
    # 2. Remove Headings (### Title) - any number of # at start of line
    text = re.sub(r'^\s*#+\s*', '', text, flags=re.MULTILINE)
    # Also catch headings that might not be at start of line if literal \n were present
    text = re.sub(r'#+\s+', '', text)
    
    # 3. Remove Bold/Italic (***, **, *, __, _) - everywhere
    text = re.sub(r'(\*{1,3}|_{1,3})', '', text)
    
    # 4. Remove Blockquotes (> Text) at start of line
    text = re.sub(r'^\s*>\s*', '', text, flags=re.MULTILINE)
    # Catch any remaining > at start of phrases
    text = re.sub(r'\n>\s*', '\n', text)
    
    # 5. Remove inline code (`code`)
    text = re.sub(r'`', '', text)
    
    return text.strip()

def run_fix():
    print("AGGRESSIVE CLEANING starting...")
    for model in [ManualSection, ServiceManual, Product, ProductFeature]:
        print(f"  Processing {model.__name__}...")
        objs = model.objects.all()
        for obj in objs:
            fields = ['content', 'description', 'lead_text']
            changed = False
            for field in fields:
                if hasattr(obj, field):
                    old_val = getattr(obj, field) or ""
                    new_val = clean_markdown_aggressive(old_val)
                    if old_val != new_val:
                        setattr(obj, field, new_val)
                        changed = True
            if changed:
                obj.save()
                print(f"    [FIXED] {obj}")

if __name__ == '__main__':
    run_fix()
