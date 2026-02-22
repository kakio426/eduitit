import os
import django
import sys
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from products.models import Product

with open('search_test.txt', 'w', encoding='utf-8') as f:
    products = Product.objects.all()
    res = []
    for p in products:
        if '사주' in p.title or '운세' in p.title:
            res.append({'title': p.title, 'is_active': p.is_active, 'solve': p.solve_text})
    f.write(json.dumps(res, ensure_ascii=False))
