
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from products.models import Product, ProductFeature

def inspect_all_products():
    products = Product.objects.all()
    for prod in products:
        print(f"Product: {prod.title} (ID: {prod.id})")
        features = list(prod.features.all())
        print(f"  Features count: {len(features)}")
        seen_titles = set()
        for f in features:
            print(f"    - {f.title} (ID: {f.id})")
            if f.title in seen_titles:
                print(f"      [DUPLICATE DETECTED] deleting {f.id}")
                f.delete()
            else:
                seen_titles.add(f.title)

if __name__ == "__main__":
    inspect_all_products()
