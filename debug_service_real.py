
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from products.models import Product
from collect.views import get_collect_service

def debug_service():
    print("--- 1. get_collect_service() returns ---")
    s = get_collect_service()
    if s:
        print(f"ID: {s.id}, Title: {s.title}")
        feats = s.features.all()
        print(f"Features count: {feats.count()}")
        for f in feats:
            print(f" - {f.title} (ID: {f.id})")
    else:
        print("None")

    print("\n--- 2. All Products with '간편 수합' ---")
    ps = Product.objects.filter(title__icontains="간편 수합")
    for p in ps:
        print(f"ID: {p.id}, Title: {p.title}")
        fs = p.features.all()
        print(f"  Features count: {fs.count()}")
        for f in fs:
            print(f"    - {f.title} (ID: {f.id})")

if __name__ == "__main__":
    debug_service()
