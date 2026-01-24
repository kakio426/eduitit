
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from products.models import Product

def list_all():
    prods = Product.objects.all().order_by('title', 'created_at')
    print("ID | Title | Created At")
    print("-" * 50)
    for p in prods:
        print(f"{p.id} | {p.title} | {p.created_at}")

if __name__ == "__main__":
    list_all()
