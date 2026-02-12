
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from products.models import Product, ProductFeature
from collect.views import get_collect_service

def check_collect_service():
    print("--- Checking get_collect_service() ---")
    service = get_collect_service()
    if service:
        print(f"Service returned: {service.title} (ID: {service.id})")
        features = list(service.features.all())
        print(f"Features count: {len(features)}")
        for f in features:
            print(f" - {f.title} (ID: {f.id})")
    else:
        print("get_collect_service() returned None")

    print("\n--- Listing all products matching '간편 수합' ---")
    products = Product.objects.filter(title__icontains="간편 수합")
    for p in products:
        print(f"Product: {p.title} (ID: {p.id})")
        features = list(p.features.all())
        print(f"  Features count: {len(features)}")
        for f in features:
            print(f"    - {f.title} (ID: {f.id})")

if __name__ == "__main__":
    check_collect_service()
