
import os
import sys
import django

# Setup Django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from products.models import ManualSection

def inspect_content():
    s = ManualSection.objects.filter(manual__product__title__icontains='예약').first()
    if s:
        content = s.content
        print(f"Product: {s.manual.product.title}")
        print(f"Total length: {len(content)}")
        print(f"Real newlines (\\n): {content.count('\n')}")
        print(f"Literal backslash-n ('\\\\n'): {content.count('\\n')}")
        print(f"Raw content snippet: {repr(content[:100])}")

if __name__ == '__main__':
    inspect_content()
