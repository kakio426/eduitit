import os
import sys
import django

sys.path.insert(0, 'c:\\Users\\kakio\\eduitit')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from products.models import Product, ProductFeature

try:
    p = Product.objects.get(title__icontains='서명')
    print("=== Product ===")
    print("Title:", p.title)
    print("Lead text:", p.lead_text)
    print("Description:", p.description)
    print()
    print("=== ProductFeatures ===")
    for f in ProductFeature.objects.filter(product=p):
        print(f"- [{f.icon}] {f.title}: {f.description}")

except Exception as e:
    import traceback
    traceback.print_exc()
