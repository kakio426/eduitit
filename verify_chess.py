
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from products.models import Product

chess = Product.objects.filter(title__icontains='체스').first()
if chess:
    print(f"FOUND: {chess.title} (ID: {chess.id})")
    print(f"  External URL: '{chess.external_url}'")
else:
    print("NOT FOUND")
