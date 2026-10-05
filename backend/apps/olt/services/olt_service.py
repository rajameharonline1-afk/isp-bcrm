# ফাইল: backend/apps/olt/services/olt_service.py
# এই ফাইলটি OLT-এর সব high-level operations orchestrate করে।
# SNMP poll ডেটা DB-তে save, ONU status update, WebSocket push সব এখানে।

import logging
from django.utils import timezone
from django.db import transaction
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from .snmp_service import SNMPService
from .ssh_service import get_olt_cli, OLTCLIError

logger = logging.getLogger(__name__)


class OLTService:
    """
    SNMP poll → DB save → WebSocket broadcast pipeline।
    Celery task এই class-এর methods call করে।
    """

    @staticmethod
    def get_snmp_service(olt) -> SNMPService:
        """OLT model থেকে SNMPService instance তৈরি করা।"""
        return SNMPService(
            host=olt.ip_address,
            community=olt.snmp_community,
            port=olt.snmp_port,
            timeout=olt.snmp_timeout,
            retries=olt.snmp_retries,
            version=olt.snmp_version,
            v3_username=olt.snmp_v3_username,
            v3_auth_key=olt.snmp_v3_auth_key,
            v3_priv_key=olt.snmp_v3_priv_key,
            v3_auth_proto=olt.snmp_v3_auth_proto,
            v3_priv_proto=olt.snmp_v3_priv_proto,
        )

    @staticmethod
    def poll_olt_and_save(olt_id: int) -> dict:
        """
        একটি OLT-এ SNMP poll করে সব ONU-র RX power ও status DB-তে save করে।
        WebSocket দিয়ে real-time update React UI-তে পাঠানো হয়।
        Celery task প্রতি ৫ মিনিটে এই method call করে।
        """
        from apps.olt.models import OLT, ONU, ONUSignalLog, ONUEvent

        try:
            olt = OLT.objects.get(id=olt_id, is_active=True)
        except OLT.DoesNotExist:
            return {'success': False, 'error': f'OLT {olt_id} not found'}

        snmp = OLTService.get_snmp_service(olt)

        # SNMP connection test
        test = snmp.test_connection()
        if not test['success']:
            olt.status = 'offline'
            olt.last_polled = timezone.now()
            olt.save(update_fields=['status', 'last_polled'])
            logger.warning(f"OLT offline: {olt.name} ({olt.ip_address})")
            return {'success': False, 'error': test.get('error')}

        olt.status = 'online'

        # Vendor-specific OID profile থেকে full poll
        try:
            # DB-তে custom OID profile থাকলে নেওয়া
            from apps.olt.models import OLTSNMPOIDProfile
            try:
                oid_profile = OLTSNMPOIDProfile.objects.get(vendor=olt.vendor)
                custom_oids = {
                    'onu_rx_power':  oid_profile.oid_onu_rx_power,
                    'onu_tx_power':  oid_profile.oid_onu_tx_power,
                    'olt_rx_power':  oid_profile.oid_olt_rx_power,
                    'onu_status':    oid_profile.oid_onu_status,
                    'onu_serial':    oid_profile.oid_onu_serial,
                    'onu_temperature': oid_profile.oid_onu_temperature,
                    'onu_voltage':   oid_profile.oid_onu_voltage,
                    'power_scale':   oid_profile.power_scale_factor,
                    'voltage_scale': 1000.0,
                    'temp_scale':    1.0,
                }
            except OLTSNMPOIDProfile.DoesNotExist:
                custom_oids = None

            polled_data = snmp.full_poll(olt.vendor, custom_oids)

        except Exception as e:
            logger.error(f"SNMP poll error for OLT {olt.name}: {e}")
            olt.last_polled = timezone.now()
            olt.save(update_fields=['status', 'last_polled'])
            return {'success': False, 'error': str(e)}

        # DB আপডেট
        updated_onus = []
        now = timezone.now()

        with transaction.atomic():
            for snmp_index, data in polled_data.items():
                # snmp_index থেকে ONU খোঁজা (সব ONU তে pon_index সেট থাকতে হবে)
                # অথবা port-wise onu_id থেকে
                onu_qs = ONU.objects.filter(
                    olt=olt
                ).filter(
                    port__pon_index=snmp_index
                ).select_related('port')

                if not onu_qs.exists():
                    # Index দিয়ে সরাসরি খোঁজা
                    onu_qs = ONU.objects.filter(olt=olt, serial_number=data.get('serial_number', ''))

                for onu in onu_qs:
                    old_rx    = onu.rx_power
                    new_rx    = data.get('rx_power')
                    new_status = data.get('status', onu.status)

                    # ONU update
                    onu.rx_power     = new_rx
                    onu.tx_power     = data.get('tx_power')
                    onu.olt_rx_power = data.get('olt_rx_power')
                    onu.temperature  = data.get('temperature')
                    onu.voltage      = data.get('voltage')
                    onu.last_polled  = now

                    # Status change detect
                    if new_status in ('online', 'offline', 'los', 'dying_gasp'):
                        old_status = onu.status
                        onu.status = new_status
                        if new_status == 'online':
                            onu.last_seen = now

                        # Status change event log
                        if old_status != new_status and new_status in ('online', 'offline', 'los', 'dying_gasp'):
                            ONUEvent.objects.create(
                                onu=onu,
                                event_type=new_status,
                                rx_power=new_rx,
                                details=f"Status changed: {old_status} → {new_status}",
                            )

                    # Signal degradation event
                    if (old_rx is not None and new_rx is not None and
                            old_rx >= onu.rx_power_threshold_warn and
                            new_rx < onu.rx_power_threshold_warn):
                        ONUEvent.objects.create(
                            onu=onu,
                            event_type=ONUEvent.EventType.POWER_DEGRADED,
                            rx_power=new_rx,
                            details=f"RX power degraded: {old_rx} → {new_rx} dBm",
                        )

                    onu.save(update_fields=[
                        'rx_power', 'tx_power', 'olt_rx_power', 'temperature',
                        'voltage', 'status', 'last_polled', 'last_seen'
                    ])

                    # Signal log তৈরি (time-series)
                    ONUSignalLog.objects.create(
                        onu=onu,
                        rx_power=new_rx,
                        tx_power=data.get('tx_power'),
                        olt_rx_power=data.get('olt_rx_power'),
                        temperature=data.get('temperature'),
                        voltage=data.get('voltage'),
                        status=new_status,
                        recorded_at=now,
                    )

                    updated_onus.append({
                        'onu_id': onu.id,
                        'serial': onu.serial_number,
                        'rx_power': new_rx,
                        'tx_power': data.get('tx_power'),
                        'olt_rx_power': data.get('olt_rx_power'),
                        'temperature': data.get('temperature'),
                        'status': new_status,
                        'rx_power_status': onu.rx_power_status,
                    })

        # OLT summary update
        online_count  = ONU.objects.filter(olt=olt, status='online').count()
        total_count   = ONU.objects.filter(olt=olt).count()
        olt.online_onus = online_count
        olt.total_onus  = total_count
        olt.last_polled = now
        olt.save(update_fields=['status', 'online_onus', 'total_onus', 'last_polled'])

        # WebSocket দিয়ে React UI-তে real-time update পাঠানো
        OLTService._broadcast_onu_updates(olt_id, updated_onus)

        logger.info(f"OLT poll complete: {olt.name}, {len(updated_onus)} ONUs updated")
        return {
            'success': True,
            'olt_name': olt.name,
            'updated_onus': len(updated_onus),
            'online': online_count,
            'total': total_count,
        }

    @staticmethod
    def _broadcast_onu_updates(olt_id: int, onu_data: list):
        """
        Django Channels WebSocket দিয়ে React-এ ONU updates push করা।
        React dashboard OLT room-এ subscribe করলে real-time data পাবে।
        """
        try:
            channel_layer = get_channel_layer()
            if channel_layer:
                async_to_sync(channel_layer.group_send)(
                    f'olt_{olt_id}',  # OLT-specific channel group
                    {
                        'type':      'onu.update',
                        'olt_id':    olt_id,
                        'onu_data':  onu_data,
                        'timestamp': timezone.now().isoformat(),
                    }
                )
        except Exception as e:
            logger.warning(f"WebSocket broadcast failed for OLT {olt_id}: {e}")

    # =============================================
    # ONU Authorize / Delete (immediate action)
    # =============================================

    @staticmethod
    def authorize_onu(onu_id: int, user_id: int, **kwargs) -> dict:
        """
        ONU authorize করে SSH CLI দিয়ে।
        Status pending_auth → CLI command → success হলে authorized।
        WebSocket দিয়ে status update React-এ পাঠানো হয়।
        """
        from apps.olt.models import ONU, ONUEvent
        from apps.accounts.models import User

        try:
            onu  = ONU.objects.select_related('olt', 'port').get(id=onu_id)
            user = User.objects.get(id=user_id)
        except (ONU.DoesNotExist, User.DoesNotExist) as e:
            return {'success': False, 'error': str(e)}

        # Status pending_auth-এ set করা (optimistic update)
        onu.pending_action = ONU.PendingAction.AUTHORIZE
        onu.save(update_fields=['pending_action'])

        OLTService._broadcast_onu_updates(onu.olt_id, [{
            'onu_id': onu_id, 'status': 'pending_auth', 'serial': onu.serial_number
        }])

        try:
            cli = get_olt_cli(onu.olt)
            port = onu.port

            if onu.olt.vendor == 'zte':
                result = cli.authorize_onu(
                    chassis=port.frame, slot=port.slot, port=port.port, onu_id=onu.onu_id,
                    serial=onu.serial_number,
                    profile_name=kwargs.get('profile_name', 'FTTH'),
                    desc=kwargs.get('desc', ''),
                )
            else:
                result = cli.authorize_onu(
                    frame=port.frame, slot=port.slot, port=port.port, onu_id=onu.onu_id,
                    serial=onu.serial_number,
                    ont_lineprofile_id=kwargs.get('lineprofile_id', 10),
                    ont_srvprofile_id=kwargs.get('srvprofile_id', 10),
                    desc=kwargs.get('desc', ''),
                )

            if result['success']:
                onu.status         = ONU.ONUStatus.AUTHORIZED
                onu.pending_action = ONU.PendingAction.NONE
                onu.authorized_at  = timezone.now()
                onu.save(update_fields=['status', 'pending_action', 'authorized_at'])

                ONUEvent.objects.create(
                    onu=onu, event_type=ONUEvent.EventType.AUTHORIZED,
                    triggered_by=user,
                    details=f"Authorized by {user.full_name}",
                )
            else:
                onu.pending_action = ONU.PendingAction.NONE
                onu.save(update_fields=['pending_action'])

            # WebSocket-এ final status পাঠানো
            OLTService._broadcast_onu_updates(onu.olt_id, [{
                'onu_id': onu_id,
                'status': onu.status,
                'serial': onu.serial_number,
                'pending_action': onu.pending_action,
            }])

            return result

        except OLTCLIError as e:
            onu.pending_action = ONU.PendingAction.NONE
            onu.save(update_fields=['pending_action'])
            return {'success': False, 'error': str(e)}

    @staticmethod
    def delete_onu(onu_id: int, user_id: int) -> dict:
        """
        ONU delete করে SSH CLI দিয়ে।
        সফল হলে DB থেকেও ONU record remove করা হয়।
        """
        from apps.olt.models import ONU, ONUEvent
        from apps.accounts.models import User

        try:
            onu  = ONU.objects.select_related('olt', 'port').get(id=onu_id)
            user = User.objects.get(id=user_id)
        except (ONU.DoesNotExist, User.DoesNotExist) as e:
            return {'success': False, 'error': str(e)}

        # Pending delete status set করা
        onu.pending_action = ONU.PendingAction.DELETE
        onu.save(update_fields=['pending_action'])

        OLTService._broadcast_onu_updates(onu.olt_id, [{
            'onu_id': onu_id, 'status': 'pending_delete', 'serial': onu.serial_number
        }])

        try:
            cli  = get_olt_cli(onu.olt)
            port = onu.port

            result = cli.delete_onu(
                frame=port.frame, slot=port.slot,
                port=port.port,   onu_id=onu.onu_id
            )

            if result['success']:
                ONUEvent.objects.create(
                    onu=onu, event_type=ONUEvent.EventType.DELETED,
                    triggered_by=user,
                    details=f"Deleted by {user.full_name}",
                )
                onu_olt_id = onu.olt_id
                onu.delete()
                OLTService._broadcast_onu_updates(onu_olt_id, [{'onu_id': onu_id, 'deleted': True}])
            else:
                onu.pending_action = ONU.PendingAction.NONE
                onu.save(update_fields=['pending_action'])

            return result

        except OLTCLIError as e:
            onu.pending_action = ONU.PendingAction.NONE
            onu.save(update_fields=['pending_action'])
            return {'success': False, 'error': str(e)}
