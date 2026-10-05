# ফাইল: backend/config/asgi.py
# এই ফাইলটি HTTP এবং WebSocket উভয় request handle করার ASGI entry point।
# Django Channels দিয়ে OLT real-time monitoring WebSocket সংযোগ handle করা হয়।

import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

# Django ASGI app initialize করা
django_asgi_app = get_asgi_application()

# OLT WebSocket routes import করা
from apps.olt.routing import websocket_urlpatterns as olt_ws_patterns

application = ProtocolTypeRouter({
    # HTTP request সাধারণ Django view-এ যাবে
    'http': django_asgi_app,

    # WebSocket request JWT auth middleware দিয়ে handle হবে
    'websocket': AllowedHostsOriginValidator(
        AuthMiddlewareStack(
            URLRouter(
                olt_ws_patterns
            )
        )
    ),
})
