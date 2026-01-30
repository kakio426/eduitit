#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from products.models import Product

ssambti = Product.objects.filter(title__icontains='BTI').first()

if ssambti:
    info = {
        "id": ssambti.id,
        "title": ssambti.title,
        "description": ssambti.description,
        "lead_text": ssambti.lead_text,
        "icon": ssambti.icon,
        "price": float(ssambti.price),
        "service_type": ssambti.service_type,
        "display_order": ssambti.display_order,
        "color_theme": ssambti.color_theme,
        "card_size": ssambti.card_size,
        "is_featured": ssambti.is_featured,
        "external_url": ssambti.external_url,
    }

    with open('ssambti_info.json', 'w', encoding='utf-8') as f:
        json.dump(info, f, ensure_ascii=False, indent=2)

    print("OK: ssambti_info.json created")
else:
    print("ERROR: 쌤BTI not found")
