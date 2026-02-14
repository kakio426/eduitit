
import os
import sys
import django

# Setup Django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from products.models import ManualSection, ServiceManual, Product

def debug_md():
    print("DEBUG SEARCH FOR MD CHARS")
    
    for s in ManualSection.objects.all():
        if "**" in s.content or "#" in s.content:
            print(f"ManualSection Match: {s.manual.product.title} - {s.title}")
            print(f"Content: {repr(s.content)}")
            
    for m in ServiceManual.objects.all():
        if "**" in m.description or "#" in m.description:
            print(f"ServiceManual Desc Match: {m.product.title}")
            print(f"Desc: {repr(m.description)}")

    for p in Product.objects.all():
        desc = p.description or ""
        lead = p.lead_text or ""
        if "**" in desc or "#" in desc or "**" in lead or "#" in lead:
            print(f"Product Match: {p.title}")
            print(f"Desc: {repr(desc)}")
            print(f"Lead: {repr(lead)}")

if __name__ == '__main__':
    debug_md()
