#!/usr/bin/env python
"""모든 제품의 card_size를 small로 통일"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from products.models import Product

print("=" * 60)
print("그리드 크기 통일 작업")
print("=" * 60)

products = Product.objects.filter(is_active=True)

print(f"\n총 {products.count()}개 제품 처리 중...\n")

for product in products:
    old_size = product.card_size
    product.card_size = 'small'
    product.save()
    print(f"[OK] {product.title:30s} | {old_size} -> small")

print("\n" + "=" * 60)
print("완료!")
print("=" * 60)
