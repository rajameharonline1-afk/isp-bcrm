# ফাইল: backend/apps/olt/consumers.py
# এই ফাইলটি Django Channels WebSocket consumer ধারণ করে।
# ONU RX power real-time updates React dashboard-এ push করার জন্য।

import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

logger = logging.getLogger(__name__)


class OLTMonitorConsumer(AsyncWebsocketConsumer):
    """
    OLT monitoring WebSocket consumer।
    React frontend এই WebSocket-এ connect করে ONU updates real-time পায়।

    Connection URL: ws://<server>/ws/olt/<olt_id>/
    React থেকে subscribe করলে প্রতি SNMP poll-এ data push হবে।
    """

    async def connect(self):
        """WebSocket connection establish করা।"""
        self.olt_id    = self.scope['url_route']['kwargs']['olt_id']
        self.group_name = f'olt_{self.olt_id}'

        # JWT token validate করা
        user = self.scope.get('user')
        if not user or not user.is_authenticated:
            await self.close(code=4001)
            return

        # OLT-specific channel group-এ join করা
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # Connection সফল হলে current ONU data পাঠানো (initial snapshot)
        await self.send_initial_snapshot()
        logger.info(f"WS connected: OLT {self.olt_id} by user {user}")

    async def disconnect(self, close_code):
        """WebSocket disconnect হলে group থেকে বের হওয়া।"""
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
        logger.debug(f"WS disconnected: OLT {self.olt_id} code={close_code}")

    async def receive(self, text_data):
        """
        React থেকে আসা message handle করা।
        যেমন: manual refresh request, specific ONU subscribe।
        """
        try:
            data = json.loads(text_data)
            msg_type = data.get('type')

            if msg_type == 'refresh':
                # Manual refresh request — latest data পাঠানো
                await self.send_initial_snapshot()

            elif msg_type == 'ping':
                # Keepalive ping-এর উত্তর
                await self.send(text_data=json.dumps({'type': 'pong'}))

        except json.JSONDecodeError:
            pass

    # =============================================
    # Channel Layer Message Handlers
    # =============================================

    async def onu_update(self, event):
        """
        Celery task থেকে আসা ONU update React-এ forward করা।
        event: {'type': 'onu.update', 'olt_id': ..., 'onu_data': [...]}
        """
        await self.send(text_data=json.dumps({
            'type':      'onu_update',
            'olt_id':    event['olt_id'],
            'onu_data':  event['onu_data'],
            'timestamp': event.get('timestamp'),
        }))

    # =============================================
    # Helpers
    # =============================================

    async def send_initial_snapshot(self):
        """
        Connect করার সাথে সাথে DB থেকে সব ONU-র current data পাঠানো।
        React-এ table initial render-এর জন্য।
        """
        onus = await self.get_onu_snapshot()
        await self.send(text_data=json.dumps({
            'type':    'initial_snapshot',
            'olt_id':  int(self.olt_id),
            'onus':    onus,
        }))

    @database_sync_to_async
    def get_onu_snapshot(self) -> list:
        """DB থেকে OLT-এর সব ONU-র current data নেওয়া।"""
        from apps.olt.models import ONU

        onus = ONU.objects.filter(
            olt_id=self.olt_id
        ).select_related('port', 'client').order_by('port__frame', 'port__slot', 'port__port', 'onu_id')

        result = []
        for onu in onus:
            result.append({
                'id':            onu.id,
                'onu_id':        onu.onu_id,
                'serial':        onu.serial_number,
                'port':          onu.port.port_label if onu.port else '',
                'status':        onu.status,
                'rx_power':      onu.rx_power,
                'tx_power':      onu.tx_power,
                'olt_rx_power':  onu.olt_rx_power,
                'temperature':   onu.temperature,
                'voltage':       onu.voltage,
                'rx_power_status': onu.rx_power_status,
                'is_critical':   onu.is_signal_critical,
                'last_seen':     onu.last_seen.isoformat() if onu.last_seen else None,
                'last_polled':   onu.last_polled.isoformat() if onu.last_polled else None,
                'client_name':   onu.client.full_name if onu.client else None,
                'description':   onu.description,
                'pending_action': onu.pending_action,
            })
        return result


class OLTGlobalConsumer(AsyncWebsocketConsumer):
    """
    সব OLT-এর summary monitoring WebSocket।
    Dashboard-এ সব OLT-এর online/offline count দেখানোর জন্য।
    Connection URL: ws://<server>/ws/olt/global/
    """

    GROUP_NAME = 'olt_global'

    async def connect(self):
        user = self.scope.get('user')
        if not user or not user.is_authenticated:
            await self.close(code=4001)
            return

        await self.channel_layer.group_add(self.GROUP_NAME, self.channel_name)
        await self.accept()
        await self.send_global_summary()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.GROUP_NAME, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            if data.get('type') == 'refresh':
                await self.send_global_summary()
        except json.JSONDecodeError:
            pass

    async def olt_summary_update(self, event):
        """Global OLT summary update push করা।"""
        await self.send(text_data=json.dumps({
            'type':    'olt_summary',
            'data':    event['data'],
            'timestamp': event.get('timestamp'),
        }))

    async def send_global_summary(self):
        summary = await self.get_global_summary()
        await self.send(text_data=json.dumps({
            'type':    'initial_summary',
            'summary': summary,
        }))

    @database_sync_to_async
    def get_global_summary(self) -> list:
        """সব OLT-এর summary data নেওয়া।"""
        from apps.olt.models import OLT
        return list(OLT.objects.filter(is_active=True).values(
            'id', 'name', 'ip_address', 'vendor', 'status',
            'total_onus', 'online_onus', 'last_polled'
        ))
