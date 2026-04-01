from django.urls import re_path

from . import consumers


websocket_urlpatterns = [
    re_path(r"^schoolcomm/ws/rooms/(?P<room_id>[0-9a-f-]+)/$", consumers.SchoolcommRoomConsumer.as_asgi()),
    re_path(r"^schoolcomm/ws/users/me/$", consumers.SchoolcommUserConsumer.as_asgi()),
]

