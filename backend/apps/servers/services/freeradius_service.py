# ফাইল: backend/apps/servers/services/freeradius_service.py
# এই ফাইলটি FreeRADIUS-এর সাথে সব interaction পরিচালনা করে।
# PPPoE user create, enable, disable, package change, disconnect এখানে।

import logging
import subprocess
from django.db import transaction, connections
from django.utils import timezone

logger = logging.getLogger(__name__)


class FreeRADIUSError(Exception):
    """FreeRADIUS-সংক্রান্ত সব error-এর জন্য custom exception।"""
    pass


class FreeRADIUSService:
    """
    FreeRADIUS database-এর সাথে সব interaction এই class-এ।
    SQL backend ব্যবহার করা হচ্ছে (rlm_sql module)।
    radcheck, radreply, radusergroup table direct update করা হয়।
    """

    RADIUS_DB = 'radius'  # Database router-এ FreeRADIUS DB-র নাম

    # =============================================
    # User Create / Delete
    # =============================================

    @staticmethod
    @transaction.atomic
    def create_user(username: str, password: str, group: str) -> dict:
        """
        FreeRADIUS-এ নতুন PPPoE user তৈরি করে।
        radcheck-এ password এবং radusergroup-এ group/package set করে।
        নতুন client connection দেওয়ার সময় call করা হয়।
        """
        from apps.servers.models import RadCheck, RadUserGroup

        # username-এ শুধু valid characters আছে কিনা check
        if not FreeRADIUSService._is_valid_username(username):
            raise FreeRADIUSError(f"Invalid username: '{username}'")

        # আগে থেকে user আছে কিনা check
        if RadCheck.objects.using(FreeRADIUSService.RADIUS_DB).filter(
            username=username, attribute='Cleartext-Password'
        ).exists():
            raise FreeRADIUSError(f"'{username}' ইতিমধ্যে RADIUS-এ আছে।")

        try:
            # radcheck-এ password সংরক্ষণ
            RadCheck.objects.using(FreeRADIUSService.RADIUS_DB).create(
                username=username,
                attribute='Cleartext-Password',
                op=':=',
                value=password,
            )

            # radusergroup-এ package/group সংরক্ষণ
            RadUserGroup.objects.using(FreeRADIUSService.RADIUS_DB).create(
                username=username,
                groupname=group,
                priority=1,
            )

            logger.info(f"RADIUS user created: {username}, group: {group}")
            return {
                'success': True,
                'message': f"RADIUS user '{username}' সফলভাবে তৈরি হয়েছে।"
            }

        except Exception as e:
            raise FreeRADIUSError(f"RADIUS user তৈরি করা যায়নি: {e}")

    @staticmethod
    @transaction.atomic
    def delete_user(username: str) -> dict:
        """
        FreeRADIUS থেকে user সম্পূর্ণ মুছে ফেলে।
        সব radcheck, radreply এবং radusergroup entries মুছে দেয়।
        """
        from apps.servers.models import RadCheck, RadReply, RadUserGroup

        try:
            # radcheck entries মুছে ফেলা
            RadCheck.objects.using(FreeRADIUSService.RADIUS_DB).filter(username=username).delete()
            # radreply entries মুছে ফেলা
            RadReply.objects.using(FreeRADIUSService.RADIUS_DB).filter(username=username).delete()
            # radusergroup entries মুছে ফেলা
            RadUserGroup.objects.using(FreeRADIUSService.RADIUS_DB).filter(username=username).delete()

            logger.info(f"RADIUS user deleted: {username}")
            return {'success': True, 'message': f"RADIUS user '{username}' সফলভাবে মুছে গেছে।"}

        except Exception as e:
            raise FreeRADIUSError(f"RADIUS user মুছতে পারা যায়নি: {e}")

    # =============================================
    # Enable / Disable User
    # =============================================

    @staticmethod
    @transaction.atomic
    def disable_user(username: str) -> dict:
        """
        FreeRADIUS-এ user disable করে (authentication reject করে)।
        radcheck-এ 'Auth-Type := Reject' attribute যোগ করে।
        বিল বকেয়া বা মেয়াদোত্তীর্ণ user-এর জন্য ব্যবহৃত।
        """
        from apps.servers.models import RadCheck

        try:
            # Auth-Type := Reject যোগ/আপডেট করা
            RadCheck.objects.using(FreeRADIUSService.RADIUS_DB).update_or_create(
                username=username,
                attribute='Auth-Type',
                defaults={'op': ':=', 'value': 'Reject'},
            )

            logger.info(f"RADIUS user disabled: {username}")
            return {'success': True, 'message': f"'{username}' RADIUS-এ disable হয়েছে।"}

        except Exception as e:
            raise FreeRADIUSError(f"RADIUS user disable করা যায়নি: {e}")

    @staticmethod
    @transaction.atomic
    def enable_user(username: str) -> dict:
        """
        Disabled RADIUS user পুনরায় enable করে।
        'Auth-Type := Reject' attribute সরিয়ে দেয়।
        বিল পরিশোধের পর user restore করতে ব্যবহৃত।
        """
        from apps.servers.models import RadCheck

        try:
            # Auth-Type Reject attribute মুছে ফেলা
            RadCheck.objects.using(FreeRADIUSService.RADIUS_DB).filter(
                username=username,
                attribute='Auth-Type',
                value='Reject',
            ).delete()

            logger.info(f"RADIUS user enabled: {username}")
            return {'success': True, 'message': f"'{username}' RADIUS-এ enable হয়েছে।"}

        except Exception as e:
            raise FreeRADIUSError(f"RADIUS user enable করা যায়নি: {e}")

    # =============================================
    # Package / Group Change
    # =============================================

    @staticmethod
    @transaction.atomic
    def change_user_package(username: str, new_group: str) -> dict:
        """
        User-এর package/group পরিবর্তন করে।
        Package upgrade বা downgrade-এর সময় ব্যবহৃত।
        radusergroup table আপডেট করে নতুন package set করে।
        """
        from apps.servers.models import RadUserGroup

        try:
            # পুরনো group মুছে নতুন group দেওয়া
            RadUserGroup.objects.using(FreeRADIUSService.RADIUS_DB).filter(
                username=username
            ).delete()

            RadUserGroup.objects.using(FreeRADIUSService.RADIUS_DB).create(
                username=username,
                groupname=new_group,
                priority=1,
            )

            logger.info(f"RADIUS user package changed: {username} -> {new_group}")
            return {
                'success': True,
                'message': f"'{username}'-এর package '{new_group}'-এ পরিবর্তন হয়েছে।"
            }

        except Exception as e:
            raise FreeRADIUSError(f"Package পরিবর্তন করা যায়নি: {e}")

    @staticmethod
    @transaction.atomic
    def change_user_password(username: str, new_password: str) -> dict:
        """FreeRADIUS-এ user-এর password পরিবর্তন করে।"""
        from apps.servers.models import RadCheck

        try:
            updated = RadCheck.objects.using(FreeRADIUSService.RADIUS_DB).filter(
                username=username,
                attribute='Cleartext-Password',
            ).update(value=new_password)

            if updated == 0:
                raise FreeRADIUSError(f"'{username}' RADIUS-এ পাওয়া যায়নি।")

            return {'success': True, 'message': f"'{username}'-এর RADIUS password পরিবর্তন হয়েছে।"}

        except FreeRADIUSError:
            raise
        except Exception as e:
            raise FreeRADIUSError(f"Password পরিবর্তন করা যায়নি: {e}")

    # =============================================
    # Framed IP / Reply Attribute Management
    # =============================================

    @staticmethod
    def set_framed_ip(username: str, ip_address: str) -> dict:
        """
        User-কে static IP address দেওয়ার জন্য radreply-তে Framed-IP-Address set করে।
        Static IP package-এর client-দের জন্য ব্যবহৃত।
        """
        from apps.servers.models import RadReply

        try:
            RadReply.objects.using(FreeRADIUSService.RADIUS_DB).update_or_create(
                username=username,
                attribute='Framed-IP-Address',
                defaults={'op': '=', 'value': ip_address},
            )
            return {'success': True, 'message': f"'{username}'-এর IP '{ip_address}' set হয়েছে।"}

        except Exception as e:
            raise FreeRADIUSError(f"Framed IP set করা যায়নি: {e}")

    @staticmethod
    def remove_framed_ip(username: str) -> dict:
        """User-এর static IP assignment সরিয়ে dynamic IP-তে ফিরিয়ে দেওয়া।"""
        from apps.servers.models import RadReply

        RadReply.objects.using(FreeRADIUSService.RADIUS_DB).filter(
            username=username,
            attribute='Framed-IP-Address',
        ).delete()
        return {'success': True}

    # =============================================
    # CoA / Disconnect via radclient
    # =============================================

    @staticmethod
    def disconnect_user_via_coa(
        username: str,
        nas_ip: str,
        nas_secret: str,
        coa_port: int = 3799,
    ) -> dict:
        """
        FreeRADIUS CoA (Change of Authorization) ব্যবহার করে active session disconnect করে।
        Mikrotik NAS-এ Disconnect-Request পাঠানো হয়।
        radclient command-line tool ব্যবহার করা হয়।
        """
        # radclient command তৈরি করা
        command = [
            'radclient',
            '-x',
            f'{nas_ip}:{coa_port}',
            'disconnect',
            nas_secret,
        ]

        # Disconnect packet payload
        payload = f'User-Name = "{username}"'

        try:
            result = subprocess.run(
                command,
                input=payload,
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                logger.info(f"CoA disconnect sent for: {username} to NAS: {nas_ip}")
                return {
                    'success': True,
                    'message': f"'{username}'-কে disconnect packet পাঠানো হয়েছে।"
                }
            else:
                logger.warning(f"CoA disconnect failed for {username}: {result.stderr}")
                return {
                    'success': False,
                    'error': result.stderr or 'CoA disconnect failed.',
                }

        except subprocess.TimeoutExpired:
            return {'success': False, 'error': 'CoA request timeout হয়েছে।'}
        except FileNotFoundError:
            # radclient installed নেই
            return {'success': False, 'error': 'radclient tool পাওয়া যাচ্ছে না। FreeRADIUS install করুন।'}

    # =============================================
    # Group/Package Management in RADIUS
    # =============================================

    @staticmethod
    @transaction.atomic
    def create_radius_group(group_name: str, rate_limit: str) -> dict:
        """
        FreeRADIUS-এ নতুন group (package) তৈরি করে।
        radgroupreply-তে Mikrotik-Rate-Limit set করে।
        নতুন package তৈরির সময় RADIUS-এও group তৈরি হবে।
        """
        from apps.servers.models import RadGroupReply

        try:
            # Mikrotik Rate Limit set করা (format: 10M/10M)
            RadGroupReply.objects.using(FreeRADIUSService.RADIUS_DB).update_or_create(
                groupname=group_name,
                attribute='Mikrotik-Rate-Limit',
                defaults={'op': '=', 'value': rate_limit},
            )

            logger.info(f"RADIUS group created: {group_name}, rate: {rate_limit}")
            return {
                'success': True,
                'message': f"RADIUS group '{group_name}' rate-limit '{rate_limit}' দিয়ে তৈরি হয়েছে।"
            }

        except Exception as e:
            raise FreeRADIUSError(f"RADIUS group তৈরি করা যায়নি: {e}")

    @staticmethod
    def delete_radius_group(group_name: str) -> dict:
        """FreeRADIUS group মুছে ফেলা।"""
        from apps.servers.models import RadGroupCheck, RadGroupReply

        RadGroupCheck.objects.using(FreeRADIUSService.RADIUS_DB).filter(groupname=group_name).delete()
        RadGroupReply.objects.using(FreeRADIUSService.RADIUS_DB).filter(groupname=group_name).delete()
        return {'success': True}

    # =============================================
    # Status Check
    # =============================================

    @staticmethod
    def check_user_exists(username: str) -> bool:
        """User RADIUS-এ আছে কিনা check করে।"""
        from apps.servers.models import RadCheck
        return RadCheck.objects.using(FreeRADIUSService.RADIUS_DB).filter(
            username=username,
            attribute='Cleartext-Password'
        ).exists()

    @staticmethod
    def is_user_disabled(username: str) -> bool:
        """User disabled (Auth-Type := Reject) কিনা check করে।"""
        from apps.servers.models import RadCheck
        return RadCheck.objects.using(FreeRADIUSService.RADIUS_DB).filter(
            username=username,
            attribute='Auth-Type',
            value='Reject',
        ).exists()

    @staticmethod
    def get_user_info(username: str) -> dict:
        """User-এর সব RADIUS তথ্য একসাথে দেখা।"""
        from apps.servers.models import RadCheck, RadReply, RadUserGroup, RadAcct

        checks = list(
            RadCheck.objects.using(FreeRADIUSService.RADIUS_DB)
            .filter(username=username)
            .values('attribute', 'op', 'value')
        )
        replies = list(
            RadReply.objects.using(FreeRADIUSService.RADIUS_DB)
            .filter(username=username)
            .values('attribute', 'op', 'value')
        )
        groups = list(
            RadUserGroup.objects.using(FreeRADIUSService.RADIUS_DB)
            .filter(username=username)
            .values_list('groupname', flat=True)
        )

        # সর্বশেষ session তথ্য
        last_session = (
            RadAcct.objects.using(FreeRADIUSService.RADIUS_DB)
            .filter(username=username)
            .order_by('-acctstarttime')
            .first()
        )

        return {
            'username': username,
            'exists': len(checks) > 0,
            'is_disabled': FreeRADIUSService.is_user_disabled(username),
            'check_attributes': checks,
            'reply_attributes': replies,
            'groups': groups,
            'last_session': {
                'start': last_session.acctstarttime,
                'stop': last_session.acctstoptime,
                'ip': last_session.framedipaddress,
                'session_time': last_session.acctsessiontime,
                'download_bytes': last_session.acctinputoctets,
                'upload_bytes': last_session.acctoutputoctets,
            } if last_session else None,
        }

    @staticmethod
    def get_active_sessions() -> list:
        """FreeRADIUS radacct থেকে এখন active সব session দেখা।"""
        from apps.servers.models import RadAcct

        active = RadAcct.objects.using(FreeRADIUSService.RADIUS_DB).filter(
            acctstoptime__isnull=True
        ).order_by('-acctstarttime')

        return [
            {
                'username': s.username,
                'ip': str(s.framedipaddress),
                'nas_ip': str(s.nasipaddress),
                'start_time': s.acctstarttime,
                'session_time': s.acctsessiontime,
                'download_bytes': s.acctinputoctets,
                'upload_bytes': s.acctoutputoctets,
            }
            for s in active
        ]

    # =============================================
    # Bulk Operations
    # =============================================

    @staticmethod
    @transaction.atomic
    def bulk_disable_expired_users(usernames: list) -> dict:
        """
        মেয়াদোত্তীর্ণ সব user একসাথে disable করা।
        Celery scheduled task থেকে daily চালানো হয়।
        """
        from apps.servers.models import RadCheck

        disabled_count = 0
        errors = []

        for username in usernames:
            try:
                RadCheck.objects.using(FreeRADIUSService.RADIUS_DB).update_or_create(
                    username=username,
                    attribute='Auth-Type',
                    defaults={'op': ':=', 'value': 'Reject'},
                )
                disabled_count += 1
            except Exception as e:
                errors.append(f"{username}: {e}")

        logger.info(f"Bulk disable: {disabled_count} users disabled, {len(errors)} errors")
        return {
            'success': True,
            'disabled_count': disabled_count,
            'errors': errors,
        }

    # =============================================
    # Private Helpers
    # =============================================

    @staticmethod
    def _is_valid_username(username: str) -> bool:
        """Username-এ valid characters আছে কিনা check করা।"""
        import re
        pattern = r'^[a-zA-Z0-9._@-]{3,64}$'
        return bool(re.match(pattern, username))
