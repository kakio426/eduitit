from django.urls import re_path

from . import consumers


websocket_urlpatterns = [
    re_path(r"^quickdrop/ws/(?P<slug>[0-9a-z]+)/$", consumers.QuickdropConsumer.as_asgi()),
]
