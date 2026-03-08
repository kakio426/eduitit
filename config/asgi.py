"""
ASGI config for config project.
"""

import os
import warnings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', os.environ.get('DJANGO_SETTINGS_MODULE', 'config.settings_production'))

warnings.filterwarnings(
    "ignore",
    message=(
        r"StreamingHttpResponse must consume synchronous iterators in order to "
        r"serve them asynchronously\. Use an asynchronous iterator instead\."
    ),
    module=r"django\.core\.handlers\.asgi",
)

from config.routing import application  # noqa: E402
