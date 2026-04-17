"""
ASGI config for config project.
"""

import os
import warnings

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.conf import settings
from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler
from django.core.asgi import get_asgi_application

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    os.environ.get("DJANGO_SETTINGS_MODULE", "config.settings_production"),
)

warnings.filterwarnings(
    "ignore",
    message=(
        r"StreamingHttpResponse must consume synchronous iterators in order to "
        r"serve them asynchronously\. Use an asynchronous iterator instead\."
    ),
    module=r"django\.core\.handlers\.asgi",
)

django_asgi_app = get_asgi_application()

from config.websocket_urls import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AllowedHostsOriginValidator(
            AuthMiddlewareStack(URLRouter(websocket_urlpatterns))
        ),
    }
)

if settings.DEBUG:
    application = ASGIStaticFilesHandler(application)
