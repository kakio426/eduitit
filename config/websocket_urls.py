from quickdrop.routing import websocket_urlpatterns as quickdrop_websocket_urlpatterns
from textbooks.routing import websocket_urlpatterns as textbooks_websocket_urlpatterns


websocket_urlpatterns = [
    *textbooks_websocket_urlpatterns,
    *quickdrop_websocket_urlpatterns,
]
