# ফাইল: backend/apps/olt/routing.py
# এই ফাইলটি OLT module-এর WebSocket URL routing ধারণ করে।

from django.urls import re_path
from .consumers import OLTMonitorConsumer, OLTGlobalConsumer

websocket_urlpatterns = [
    # নির্দিষ্ট OLT-এর ONU monitoring WebSocket
    re_path(r'ws/olt/(?P<olt_id>\d+)/$', OLTMonitorConsumer.as_asgi()),

    # সব OLT-এর global summary WebSocket
    re_path(r'ws/olt/global/$', OLTGlobalConsumer.as_asgi()),
]
