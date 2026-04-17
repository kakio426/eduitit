from doccollab.routing import websocket_urlpatterns as doccollab_websocket_urlpatterns
from quickdrop.routing import websocket_urlpatterns as quickdrop_websocket_urlpatterns
from schoolcomm.routing import websocket_urlpatterns as schoolcomm_websocket_urlpatterns
from textbooks.routing import websocket_urlpatterns as textbooks_websocket_urlpatterns


websocket_urlpatterns = [
    *doccollab_websocket_urlpatterns,
    *textbooks_websocket_urlpatterns,
    *schoolcomm_websocket_urlpatterns,
    *quickdrop_websocket_urlpatterns,
]
