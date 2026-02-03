
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from products.models import Product

products = Product.objects.all()
print(f"Total products: {products.count()}")
for p in products:
    print(f"- ID: {p.id}, Title: {p.title}, Active: {p.is_active}")
