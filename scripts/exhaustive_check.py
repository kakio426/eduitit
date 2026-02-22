claude
import os
import sys
import django
import re

# Setup Django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from products.models import ProductFeature, Product, ServiceManual, ManualSection

def exhaustive_check():
    print("EXHAUSTIVE MARKDOWN SEARCH")
    
    models_to_check = [
        (ManualSection, ['title', 'content']),
        (ServiceManual, ['title', 'description']),
        (Product, ['title', 'description', 'lead_text']),
        (ProductFeature, ['title', 'description']),
    ]
    
    found = False
    for model, fields in models_to_check:
        print(f"Checking {model.__name__}...")
        for obj in model.objects.all():
            for field in fields:
                val = getattr(obj, field) or ""
                if "**" in val or "##" in val or "> " in val:
                    found = True
                    owner = ""
                    if hasattr(obj, 'product'): owner = obj.product.title
                    elif hasattr(obj, 'manual'): owner = obj.manual.product.title
                    
                    print(f"MATCH in {model.__name__} ({owner} - {getattr(obj, 'title', 'No Title')}): Field '{field}'")
                    print(f"  Content: {repr(val)}")

    if not found:
        print("No markdown characters found in mapped fields.")

if __name__ == '__main__':
    exhaustive_check()
