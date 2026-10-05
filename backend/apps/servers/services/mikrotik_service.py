# ফাইল: backend/apps/servers/services/mikrotik_service.py
# এই ফাইলটি Mikrotik RouterOS API ব্যবহার করে PPPoE user, profile, traffic ও backup পরিচালনা করে।

import logging
from contextlib import contextmanager
from typing import Optional
import librouteros
from librouteros import connect
from librouteros.exceptions import ConnectionClosed, TrapError

logger = logging.getLogger(__name__)


class MikrotikAPIError(Exception):
    """Mikrotik API-সংক্রান্ত সব error-এর জন্য custom exception।"""
    pass


class MikrotikService:
    """
    Mikrotik RouterOS API-র সাথে সব ধরনের interaction এই class-এ।
    প্রতিটি method শেষে connection স্বয়ংক্রিয়ভাবে close হয়।
    """

    def __init__(self, host: str, username: str, password: str, port: int = 8728):
        # Router connection credentials
        self.host = host
        self.username = username
        self.password = password
        self.port = port

    @contextmanager
    def _get_connection(self):
        """
        RouterOS API-তে connect করে এবং কাজ শেষে disconnect করে।
        Context manager হিসেবে ব্যবহার করা হয় যাতে connection leak না হয়।
        """
        api = None
        try:
            api = connect(
                host=self.host,
                username=self.username,
                password=self.password,
                port=self.port,
                timeout=10,
            )
            yield api
        except ConnectionClosed as e:
            raise MikrotikAPIError(f"Router connection closed unexpectedly: {e}")
        except Exception as e:
            raise MikrotikAPIError(f"Router {self.host}-এ connect করা যাচ্ছে না: {e}")
        finally:
            if api:
                try:
                    api.close()
                except Exception:
                    pass

    def test_connection(self) -> dict:
        """
        Router connection test করে এবং system identity return করে।
        Router online আছে কিনা জানার জন্য ব্যবহৃত।
        """
        try:
            with self._get_connection() as api:
                # Router-এর identity ও version নেওয়া
                identity = list(api('/system/identity/print'))
                resource = list(api('/system/resource/print'))

                return {
                    'success': True,
                    'identity': identity[0].get('name', '') if identity else '',
                    'version': resource[0].get('version', '') if resource else '',
                    'uptime': resource[0].get('uptime', '') if resource else '',
                    'cpu_load': resource[0].get('cpu-load', '0') if resource else '0',
                    'memory_total': resource[0].get('total-memory', '0') if resource else '0',
                    'memory_free': resource[0].get('free-memory', '0') if resource else '0',
                }
        except MikrotikAPIError as e:
            return {'success': False, 'error': str(e)}

    # =============================================
    # PPPoE Secret Management (User CRUD)
    # =============================================

    def create_pppoe_secret(
        self,
        username: str,
        password: str,
        profile: str = 'default',
        service: str = 'pppoe',
        comment: str = '',
        local_address: str = '',
        remote_address: str = '',
    ) -> dict:
        """
        Mikrotik-এ নতুন PPPoE secret (user) তৈরি করে।
        নতুন client connection দেওয়ার সময় এই function call করা হয়।
        """
        try:
            with self._get_connection() as api:
                params = {
                    'name': username,
                    'password': password,
                    'profile': profile,
                    'service': service,
                    'comment': comment,
                    'disabled': 'no',
                }
                if local_address:
                    params['local-address'] = local_address
                if remote_address:
                    params['remote-address'] = remote_address

                api('/ppp/secret/add', **params)

                logger.info(f"PPPoE secret created: {username} on {self.host}")
                return {'success': True, 'message': f"PPPoE user '{username}' সফলভাবে তৈরি হয়েছে।"}

        except TrapError as e:
            if 'already have entry with such name' in str(e).lower():
                return {'success': False, 'error': f"'{username}' ইতিমধ্যে router-এ আছে।"}
            raise MikrotikAPIError(str(e))

    def enable_pppoe_secret(self, username: str) -> dict:
        """
        Disabled PPPoE user enable করে।
        বিল পরিশোধ করলে বা suspend তুলে দিলে ব্যবহৃত।
        """
        try:
            with self._get_connection() as api:
                # Username দিয়ে secret খোঁজা
                secrets = list(api('/ppp/secret/print', **{'?name': username}))
                if not secrets:
                    return {'success': False, 'error': f"'{username}' router-এ পাওয়া যায়নি।"}

                secret_id = secrets[0].get('.id')
                api('/ppp/secret/enable', **{'.id': secret_id})

                logger.info(f"PPPoE secret enabled: {username} on {self.host}")
                return {'success': True, 'message': f"'{username}' সফলভাবে enable হয়েছে।"}

        except MikrotikAPIError:
            raise

    def disable_pppoe_secret(self, username: str) -> dict:
        """
        PPPoE user disable করে।
        বিল বকেয়া থাকলে বা suspend করতে হলে ব্যবহৃত।
        """
        try:
            with self._get_connection() as api:
                secrets = list(api('/ppp/secret/print', **{'?name': username}))
                if not secrets:
                    return {'success': False, 'error': f"'{username}' router-এ পাওয়া যায়নি।"}

                secret_id = secrets[0].get('.id')
                api('/ppp/secret/disable', **{'.id': secret_id})

                # Active session থাকলে disconnect করা
                self._disconnect_active_session(api, username)

                logger.info(f"PPPoE secret disabled: {username} on {self.host}")
                return {'success': True, 'message': f"'{username}' সফলভাবে disable হয়েছে।"}

        except MikrotikAPIError:
            raise

    def delete_pppoe_secret(self, username: str) -> dict:
        """
        PPPoE user সম্পূর্ণ মুছে ফেলে।
        Client চলে গেলে অথবা connection বাতিল হলে ব্যবহৃত।
        """
        try:
            with self._get_connection() as api:
                secrets = list(api('/ppp/secret/print', **{'?name': username}))
                if not secrets:
                    return {'success': False, 'error': f"'{username}' router-এ পাওয়া যায়নি।"}

                secret_id = secrets[0].get('.id')
                # Active session থাকলে আগে disconnect করা
                self._disconnect_active_session(api, username)
                api('/ppp/secret/remove', **{'.id': secret_id})

                logger.info(f"PPPoE secret deleted: {username} on {self.host}")
                return {'success': True, 'message': f"'{username}' সফলভাবে মুছে গেছে।"}

        except MikrotikAPIError:
            raise

    def change_pppoe_password(self, username: str, new_password: str) -> dict:
        """PPPoE user-এর password পরিবর্তন করে।"""
        try:
            with self._get_connection() as api:
                secrets = list(api('/ppp/secret/print', **{'?name': username}))
                if not secrets:
                    return {'success': False, 'error': f"'{username}' router-এ পাওয়া যায়নি।"}

                secret_id = secrets[0].get('.id')
                api('/ppp/secret/set', **{'.id': secret_id, 'password': new_password})

                return {'success': True, 'message': f"'{username}'-এর password পরিবর্তন হয়েছে।"}

        except MikrotikAPIError:
            raise

    def change_pppoe_profile(self, username: str, new_profile: str) -> dict:
        """
        PPPoE user-এর profile (package/speed) পরিবর্তন করে।
        Package upgrade/downgrade-এর সময় ব্যবহৃত।
        """
        try:
            with self._get_connection() as api:
                secrets = list(api('/ppp/secret/print', **{'?name': username}))
                if not secrets:
                    return {'success': False, 'error': f"'{username}' router-এ পাওয়া যায়নি।"}

                secret_id = secrets[0].get('.id')
                api('/ppp/secret/set', **{'.id': secret_id, 'profile': new_profile})

                # Active session disconnect করা যাতে নতুন profile apply হয়
                self._disconnect_active_session(api, username)

                return {'success': True, 'message': f"'{username}'-এর profile '{new_profile}'-এ পরিবর্তন হয়েছে।"}

        except MikrotikAPIError:
            raise

    def disconnect_active_user(self, username: str) -> dict:
        """
        Currently connected PPPoE user-কে forcefully disconnect করে।
        নতুন IP নিতে বা re-authenticate করতে force করার জন্য।
        """
        try:
            with self._get_connection() as api:
                result = self._disconnect_active_session(api, username)
                if result:
                    return {'success': True, 'message': f"'{username}' disconnect হয়েছে।"}
                return {'success': False, 'message': f"'{username}' এখন connected নেই।"}

        except MikrotikAPIError:
            raise

    def _disconnect_active_session(self, api, username: str) -> bool:
        """Active PPPoE session খুঁজে disconnect করার internal helper।"""
        try:
            active = list(api('/ppp/active/print', **{'?name': username}))
            if active:
                session_id = active[0].get('.id')
                api('/ppp/active/remove', **{'.id': session_id})
                return True
        except Exception:
            pass
        return False

    def get_pppoe_secret(self, username: str) -> Optional[dict]:
        """একটি নির্দিষ্ট PPPoE secret-এর তথ্য নেওয়া।"""
        try:
            with self._get_connection() as api:
                secrets = list(api('/ppp/secret/print', **{'?name': username}))
                if secrets:
                    s = secrets[0]
                    return {
                        'username': s.get('name'),
                        'profile': s.get('profile'),
                        'service': s.get('service'),
                        'disabled': s.get('disabled') == 'true',
                        'comment': s.get('comment', ''),
                        'local_address': s.get('local-address', ''),
                        'remote_address': s.get('remote-address', ''),
                        'last_caller': s.get('last-caller', ''),
                        'last_logged_out': s.get('last-logged-out', ''),
                    }
                return None
        except MikrotikAPIError:
            raise

    def get_all_pppoe_secrets(self) -> list:
        """
        Router থেকে সব PPPoE secret import করে।
        'Import from Mikrotik' feature-এর জন্য ব্যবহৃত।
        """
        try:
            with self._get_connection() as api:
                secrets = list(api('/ppp/secret/print'))
                result = []
                for s in secrets:
                    result.append({
                        'username': s.get('name', ''),
                        'profile': s.get('profile', ''),
                        'service': s.get('service', 'pppoe'),
                        'disabled': s.get('disabled', 'false') == 'true',
                        'comment': s.get('comment', ''),
                        'local_address': s.get('local-address', ''),
                        'remote_address': s.get('remote-address', ''),
                        'last_caller': s.get('last-caller', ''),
                    })
                return result
        except MikrotikAPIError:
            raise

    def get_active_connections(self) -> list:
        """
        এখন connected সব PPPoE active session দেখা।
        Live monitoring-এর জন্য ব্যবহৃত।
        """
        try:
            with self._get_connection() as api:
                active = list(api('/ppp/active/print'))
                result = []
                for conn in active:
                    result.append({
                        'username': conn.get('name', ''),
                        'service': conn.get('service', ''),
                        'caller_id': conn.get('caller-id', ''),
                        'address': conn.get('address', ''),
                        'uptime': conn.get('uptime', ''),
                        'session_id': conn.get('.id', ''),
                        'encoding': conn.get('encoding', ''),
                    })
                return result
        except MikrotikAPIError:
            raise

    # =============================================
    # PPPoE Profile Management
    # =============================================

    def get_all_pppoe_profiles(self) -> list:
        """Router থেকে সব PPPoE profile নেওয়া।"""
        try:
            with self._get_connection() as api:
                profiles = list(api('/ppp/profile/print'))
                result = []
                for p in profiles:
                    result.append({
                        'name': p.get('name', ''),
                        'local_address': p.get('local-address', ''),
                        'remote_address': p.get('remote-address', ''),
                        'rate_limit': p.get('rate-limit', ''),
                        'dns_server': p.get('dns-server', ''),
                        'only_one': p.get('only-one', 'no'),
                    })
                return result
        except MikrotikAPIError:
            raise

    def create_pppoe_profile(
        self,
        name: str,
        rate_limit: str,
        local_address: str = '',
        remote_address: str = '',
        dns_server: str = '8.8.8.8,8.8.4.4',
        only_one: str = 'yes',
    ) -> dict:
        """
        Mikrotik-এ নতুন PPPoE profile তৈরি করে।
        নতুন package তৈরির সময় এই function call করা হয়।
        rate_limit format: '10M/10M' (download/upload)
        """
        try:
            with self._get_connection() as api:
                params = {
                    'name': name,
                    'rate-limit': rate_limit,
                    'dns-server': dns_server,
                    'only-one': only_one,
                }
                if local_address:
                    params['local-address'] = local_address
                if remote_address:
                    params['remote-address'] = remote_address

                api('/ppp/profile/add', **params)
                return {'success': True, 'message': f"Profile '{name}' সফলভাবে তৈরি হয়েছে।"}

        except TrapError as e:
            raise MikrotikAPIError(f"Profile তৈরি করা যায়নি: {e}")

    # =============================================
    # Traffic Monitoring
    # =============================================

    def get_interface_traffic(self, interface: str = 'all') -> list:
        """
        নির্দিষ্ট interface বা সব interface-এর live traffic data নেওয়া।
        Dashboard-এ live traffic chart দেখানোর জন্য।
        """
        try:
            with self._get_connection() as api:
                if interface == 'all':
                    interfaces = list(api('/interface/print'))
                else:
                    interfaces = list(api('/interface/print', **{'?name': interface}))

                result = []
                for iface in interfaces:
                    result.append({
                        'name': iface.get('name', ''),
                        'type': iface.get('type', ''),
                        'rx_byte': int(iface.get('rx-byte', 0)),
                        'tx_byte': int(iface.get('tx-byte', 0)),
                        'rx_packet': int(iface.get('rx-packet', 0)),
                        'tx_packet': int(iface.get('tx-packet', 0)),
                        'running': iface.get('running', 'false') == 'true',
                        'disabled': iface.get('disabled', 'false') == 'true',
                    })
                return result
        except MikrotikAPIError:
            raise

    def get_system_resource(self) -> dict:
        """Router-এর CPU, memory, uptime সহ system resource information।"""
        try:
            with self._get_connection() as api:
                resource = list(api('/system/resource/print'))
                if resource:
                    r = resource[0]
                    return {
                        'uptime': r.get('uptime', ''),
                        'version': r.get('version', ''),
                        'cpu_load': r.get('cpu-load', '0'),
                        'total_memory': int(r.get('total-memory', 0)),
                        'free_memory': int(r.get('free-memory', 0)),
                        'total_hdd': int(r.get('total-hdd-space', 0)),
                        'free_hdd': int(r.get('free-hdd-space', 0)),
                        'architecture': r.get('architecture-name', ''),
                        'board': r.get('board-name', ''),
                    }
                return {}
        except MikrotikAPIError:
            raise

    # =============================================
    # Router Backup
    # =============================================

    def create_backup(self, backup_name: str = '') -> dict:
        """
        Router-এ backup তৈরি করে এবং FTP/SCP দিয়ে download করে।
        Celery task-এ চালানো হয় daily automatic backup-এর জন্য।
        """
        import io
        import paramiko
        from datetime import datetime

        if not backup_name:
            backup_name = f"backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

        try:
            with self._get_connection() as api:
                # Router-এ backup file তৈরি করা
                api('/system/backup/save', **{'name': backup_name, 'dont-encrypt': 'yes'})

                # .backup file তৈরি হতে ৩ সেকেন্ড অপেক্ষা করা
                import time
                time.sleep(3)

            # SSH দিয়ে backup file download করা
            # (এটি SSH credentials প্রয়োজন করে)
            return {
                'success': True,
                'backup_name': f"{backup_name}.backup",
                'message': f"Backup '{backup_name}' router-এ save হয়েছে।",
            }

        except Exception as e:
            raise MikrotikAPIError(f"Backup তৈরি করা যায়নি: {e}")

    def download_backup_via_ssh(self, ssh_username: str, ssh_password: str, backup_name: str, ssh_port: int = 22) -> bytes:
        """
        SSH ব্যবহার করে Router থেকে backup file download করা।
        SFTP protocol ব্যবহার করা হয়।
        """
        import paramiko
        import io

        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(
                hostname=self.host,
                port=ssh_port,
                username=ssh_username,
                password=ssh_password,
                timeout=30,
            )

            sftp = ssh.open_sftp()
            file_buffer = io.BytesIO()
            sftp.getfo(f"/{backup_name}.backup", file_buffer)
            file_buffer.seek(0)
            backup_data = file_buffer.read()

            sftp.close()
            ssh.close()

            return backup_data

        except Exception as e:
            raise MikrotikAPIError(f"SSH backup download করা যায়নি: {e}")

    # =============================================
    # Address Pool Management
    # =============================================

    def get_address_pools(self) -> list:
        """Router-এর সব IP address pool নেওয়া।"""
        try:
            with self._get_connection() as api:
                pools = list(api('/ip/pool/print'))
                return [
                    {
                        'name': p.get('name', ''),
                        'ranges': p.get('ranges', ''),
                        'next_pool': p.get('next-pool', ''),
                    }
                    for p in pools
                ]
        except MikrotikAPIError:
            raise

    def get_log_entries(self, count: int = 50) -> list:
        """Router-এর recent log entries দেখা।"""
        try:
            with self._get_connection() as api:
                logs = list(api('/log/print'))[-count:]
                return [
                    {
                        'time': l.get('time', ''),
                        'topics': l.get('topics', ''),
                        'message': l.get('message', ''),
                    }
                    for l in logs
                ]
        except MikrotikAPIError:
            raise
