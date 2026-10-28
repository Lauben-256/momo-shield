"""
MoMo Shield ASGI configuration — supports both HTTP and WebSocket via Django Channels.
"""
import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'momoshield.settings')

# Import Django ASGI app first so settings are initialised
django_asgi_app = get_asgi_application()

from simulation.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    'http':      django_asgi_app,
    'websocket': AuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    ),
})
