"""
WSGI config for config project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

# Railway 등 프로덕션 환경에서는 DJANGO_SETTINGS_MODULE 환경 변수로 제어
# 환경 변수가 없으면 기본값으로 config.settings 사용
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings_production')

application = get_wsgi_application()
