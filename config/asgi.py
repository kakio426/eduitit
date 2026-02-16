"""
ASGI config for config project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/asgi/
"""

import os
import warnings

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings_production')

# ASGI + sync static/file iterators can emit this warning for WhiteNoise-served assets.
# Suppress only this known warning to keep logs actionable.
warnings.filterwarnings(
    "ignore",
    message=(
        r"StreamingHttpResponse must consume synchronous iterators in order to "
        r"serve them asynchronously\. Use an asynchronous iterator instead\."
    ),
    module=r"django\.core\.handlers\.asgi",
)

application = get_asgi_application()
