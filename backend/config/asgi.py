# ফাইল: backend/config/asgi.py
# এই ফাইলটি Django Channels (WebSocket) এবং HTTP উভয় request handle করার জন্য ASGI entry point।

import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

# Django ASGI application initialize করা
django_asgi_app = get_asgi_application()

# WebSocket routing import (OLT real-time updates-এর জন্য)
# from apps.olt import routing as olt_routing

application = ProtocolTypeRouter({
    # HTTP request Django-র সাধারণ view-এ পাঠানো হবে
    'http': django_asgi_app,

    # WebSocket request Auth middleware দিয়ে handle করা হবে
    # 'websocket': AllowedHostsOriginValidator(
    #     AuthMiddlewareStack(
    #         URLRouter(
    #             olt_routing.websocket_urlpatterns
    #         )
    #     )
    # ),
})
