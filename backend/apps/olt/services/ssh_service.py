# ফাইল: backend/apps/olt/services/ssh_service.py
# এই ফাইলটি SSH/Telnet CLI ব্যবহার করে OLT-এ ONU authorize, delete, reboot ও config করে।
# paramiko (SSH) এবং telnetlib (Telnet) উভয় প্রোটোকল support করে।

import time
import logging
import socket
import re
from typing import Optional

import paramiko

logger = logging.getLogger(__name__)


class OLTCLIError(Exception):
    """OLT CLI operation-এর জন্য custom exception।"""
    pass


class HuaweiCLI:
    """
    Huawei MA5600T / MA5800 OLT-এর SSH CLI automation।
    সব command এই class-এ — ONU authorize, delete, reboot, optical info।
    """

    def __init__(self, host: str, username: str, password: str,
                 enable_password: str = '', port: int = 22, timeout: int = 30):
        self.host            = host
        self.username        = username
        self.password        = password
        self.enable_password = enable_password
        self.port            = port
        self.timeout         = timeout
        self._client         = None
        self._shell          = None

    def connect(self):
        """SSH connection তৈরি করা এবং interactive shell খোলা।"""
        self._client = paramiko.SSHClient()
        self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self._client.connect(
            hostname=self.host,
            port=self.port,
            username=self.username,
            password=self.password,
            timeout=self.timeout,
            allow_agent=False,
            look_for_keys=False,
        )
        self._shell = self._client.invoke_shell(width=200, height=50)
        time.sleep(1)
        self._read_until_prompt()
        # Enable mode-এ যাওয়া (যদি enable password থাকে)
        if self.enable_password:
            self._send('enable')
            self._read_until_prompt(['Password:'])
            self._send(self.enable_password)
            self._read_until_prompt()

    def disconnect(self):
        """SSH connection বন্ধ করা।"""
        try:
            if self._shell:
                self._shell.close()
            if self._client:
                self._client.close()
        except Exception:
            pass

    def _send(self, command: str):
        """CLI-তে command পাঠানো।"""
        if self._shell:
            self._shell.send(command + '\n')
            time.sleep(0.5)

    def _read_until_prompt(self, prompts=None, timeout: int = 15) -> str:
        """
        OLT prompt আসা পর্যন্ত output পড়া।
        Huawei prompt: MA5600T(config)#, MA5600T#, etc.
        """
        if prompts is None:
            prompts = ['#', '>', 'Password:', '--More--', '(y/n)']

        output    = ''
        end_time  = time.time() + timeout

        while time.time() < end_time:
            if self._shell.recv_ready():
                chunk  = self._shell.recv(4096).decode('utf-8', errors='replace')
                output += chunk
                # কোনো prompt পাওয়া গেলে থামা
                for p in prompts:
                    if p in output:
                        # '--More--' হলে space পাঠিয়ে আরো নেওয়া
                        if '--More--' in output:
                            self._shell.send(' ')
                            time.sleep(0.5)
                            continue
                        return output
            time.sleep(0.2)
        return output

    def run_command(self, command: str, timeout: int = 15) -> str:
        """একটি command চালিয়ে output return করা।"""
        self._send(command)
        return self._read_until_prompt(timeout=timeout)

    # =============================================
    # ONU Authorization (Huawei)
    # =============================================

    def authorize_onu(self, frame: int, slot: int, port: int, onu_id: int,
                      serial: str, ont_lineprofile_id: int = 10,
                      ont_srvprofile_id: int = 10, desc: str = '') -> dict:
        """
        Unauthorized ONU-কে authorize করে।
        Huawei command: ont add <frame> <slot> <port> <onu_id> sn-auth <serial>
        """
        try:
            self.connect()
            # config mode-এ যাওয়া
            self.run_command('config')
            # interface gpon যাওয়া
            self.run_command(f'interface gpon {frame}/{slot}')

            # ONU add command
            cmd = (
                f'ont add {port} {onu_id} sn-auth {serial} omci '
                f'ont-lineprofile-id {ont_lineprofile_id} '
                f'ont-srvprofile-id {ont_srvprofile_id} '
                f'desc "{desc}"'
            )
            output = self.run_command(cmd, timeout=20)

            # Error check
            if 'error' in output.lower() or 'failure' in output.lower():
                return {'success': False, 'error': output.strip(), 'output': output}

            # quit interface
            self.run_command('quit')
            self.run_command('quit')

            logger.info(f"Huawei ONU authorized: {frame}/{slot}/{port}/{onu_id} SN:{serial}")
            return {'success': True, 'message': f'ONU {serial} authorized at {frame}/{slot}/{port}/{onu_id}', 'output': output}

        except Exception as e:
            raise OLTCLIError(f"ONU authorize failed: {e}")
        finally:
            self.disconnect()

    def delete_onu(self, frame: int, slot: int, port: int, onu_id: int) -> dict:
        """
        ONU delete করা।
        Huawei command: ont delete <frame> <slot> <port> <onu_id>
        """
        try:
            self.connect()
            self.run_command('config')
            self.run_command(f'interface gpon {frame}/{slot}')

            output = self.run_command(f'ont delete {port} {onu_id}', timeout=20)

            if 'error' in output.lower():
                return {'success': False, 'error': output.strip()}

            self.run_command('quit')
            self.run_command('quit')

            logger.info(f"Huawei ONU deleted: {frame}/{slot}/{port}/{onu_id}")
            return {'success': True, 'message': f'ONU {frame}/{slot}/{port}/{onu_id} deleted', 'output': output}

        except Exception as e:
            raise OLTCLIError(f"ONU delete failed: {e}")
        finally:
            self.disconnect()

    def reboot_onu(self, frame: int, slot: int, port: int, onu_id: int) -> dict:
        """ONU reboot করা।"""
        try:
            self.connect()
            self.run_command('config')
            self.run_command(f'interface gpon {frame}/{slot}')
            output = self.run_command(f'ont reset {port} {onu_id}')
            self.run_command('quit')
            self.run_command('quit')
            return {'success': True, 'output': output}
        except Exception as e:
            raise OLTCLIError(f"ONU reboot failed: {e}")
        finally:
            self.disconnect()

    def get_onu_optical_info(self, frame: int, slot: int, port: int, onu_id: Optional[int] = None) -> str:
        """
        ONU-র optical power info পড়া।
        Huawei command: display ont optical-info <frame> <slot> <port> [onu_id|all]
        """
        try:
            self.connect()
            target = str(onu_id) if onu_id is not None else 'all'
            output = self.run_command(f'display ont optical-info {frame} {slot} {port} {target}', timeout=30)
            return output
        except Exception as e:
            raise OLTCLIError(f"Optical info read failed: {e}")
        finally:
            self.disconnect()

    def get_onu_info(self, frame: int, slot: int, port: int, onu_id: Optional[int] = None) -> str:
        """ONU-র সব info পড়া।"""
        try:
            self.connect()
            target = str(onu_id) if onu_id is not None else 'all'
            output = self.run_command(f'display ont info {frame} {slot} {port} {target}', timeout=30)
            return output
        except Exception as e:
            raise OLTCLIError(f"ONU info read failed: {e}")
        finally:
            self.disconnect()

    def get_unregistered_onus(self, frame: int, slot: int) -> str:
        """Unauthorized / unregistered ONU list দেখা।"""
        try:
            self.connect()
            output = self.run_command(f'display ont autofind {frame} {slot} all', timeout=30)
            return output
        except Exception as e:
            raise OLTCLIError(f"Autofind failed: {e}")
        finally:
            self.disconnect()

    def parse_optical_info(self, raw_output: str) -> list:
        """
        Huawei 'display ont optical-info' output parse করে structured data তৈরি।
        return: [{onu_id, rx_power, tx_power, olt_rx, temperature, voltage}]
        """
        results = []
        # Huawei output pattern: ONU-ID Rx(dBm) Tx(dBm) OLT-Rx(dBm) Temp(℃) Volt(V)
        pattern = re.compile(
            r'(\d+)\s+([-\d.]+|N/A)\s+([-\d.]+|N/A)\s+([-\d.]+|N/A)\s+([-\d.]+|N/A)\s+([-\d.]+|N/A)'
        )
        for match in pattern.finditer(raw_output):
            onu_id, rx, tx, olt_rx, temp, volt = match.groups()

            def to_float(val):
                return float(val) if val != 'N/A' else None

            results.append({
                'onu_id':      int(onu_id),
                'rx_power':    to_float(rx),
                'tx_power':    to_float(tx),
                'olt_rx_power': to_float(olt_rx),
                'temperature': to_float(temp),
                'voltage':     to_float(volt),
            })
        return results


class ZTEcli:
    """
    ZTE C300/C320 OLT SSH CLI automation।
    ZTE-র command syntax Huawei থেকে আলাদা।
    """

    def __init__(self, host: str, username: str, password: str,
                 enable_password: str = '', port: int = 22, timeout: int = 30):
        self.host            = host
        self.username        = username
        self.password        = password
        self.enable_password = enable_password
        self.port            = port
        self.timeout         = timeout
        self._client         = None
        self._shell          = None

    def connect(self):
        self._client = paramiko.SSHClient()
        self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self._client.connect(
            hostname=self.host, port=self.port,
            username=self.username, password=self.password,
            timeout=self.timeout, allow_agent=False, look_for_keys=False,
        )
        self._shell = self._client.invoke_shell(width=200, height=50)
        time.sleep(1)
        output = self._read_output(timeout=5)
        if self.enable_password:
            self._send('enable')
            time.sleep(0.5)
            self._send(self.enable_password)
            time.sleep(1)

    def disconnect(self):
        try:
            if self._shell: self._shell.close()
            if self._client: self._client.close()
        except Exception:
            pass

    def _send(self, cmd: str):
        if self._shell:
            self._shell.send(cmd + '\n')
            time.sleep(0.5)

    def _read_output(self, timeout: int = 10) -> str:
        output   = ''
        end_time = time.time() + timeout
        while time.time() < end_time:
            if self._shell.recv_ready():
                output += self._shell.recv(4096).decode('utf-8', errors='replace')
                if '#' in output or '>' in output:
                    return output
            time.sleep(0.2)
        return output

    def run_command(self, command: str, timeout: int = 15) -> str:
        self._send(command)
        return self._read_output(timeout=timeout)

    def authorize_onu(self, chassis: int, slot: int, port: int, onu_id: int,
                      serial: str, profile_name: str = 'FTTH', desc: str = '') -> dict:
        """
        ZTE ONU authorize করা।
        ZTE command: gpon-onu <onu_id> type <profile>
        """
        try:
            self.connect()
            self.run_command('configure terminal')
            self.run_command(f'interface gpon-olt_{chassis}/{slot}/{port}')

            # ONU registration
            output = self.run_command(
                f'onu {onu_id} type {profile_name} sn {serial}',
                timeout=20
            )

            self.run_command('exit')
            self.run_command('exit')

            if 'error' in output.lower() or 'invalid' in output.lower():
                return {'success': False, 'error': output.strip()}

            logger.info(f"ZTE ONU authorized: {chassis}/{slot}/{port}/{onu_id} SN:{serial}")
            return {'success': True, 'message': f'ONU authorized', 'output': output}

        except Exception as e:
            raise OLTCLIError(f"ZTE ONU authorize failed: {e}")
        finally:
            self.disconnect()

    def delete_onu(self, chassis: int, slot: int, port: int, onu_id: int) -> dict:
        """ZTE ONU delete করা।"""
        try:
            self.connect()
            self.run_command('configure terminal')
            self.run_command(f'interface gpon-olt_{chassis}/{slot}/{port}')
            output = self.run_command(f'no onu {onu_id}', timeout=20)
            self.run_command('exit')
            self.run_command('exit')

            if 'error' in output.lower():
                return {'success': False, 'error': output.strip()}

            return {'success': True, 'output': output}
        except Exception as e:
            raise OLTCLIError(f"ZTE ONU delete failed: {e}")
        finally:
            self.disconnect()

    def get_onu_optical_info(self, chassis: int, slot: int, port: int) -> str:
        """ZTE optical power info।"""
        try:
            self.connect()
            output = self.run_command(
                f'show gpon remote-onu optical-transceiver gpon-olt_{chassis}/{slot}/{port}',
                timeout=30
            )
            return output
        except Exception as e:
            raise OLTCLIError(f"ZTE optical info failed: {e}")
        finally:
            self.disconnect()


def get_olt_cli(olt) -> 'HuaweiCLI | ZTEcli':
    """
    OLT vendor অনুযায়ী সঠিক CLI class return করে।
    Factory function হিসেবে ব্যবহৃত।
    """
    kwargs = dict(
        host=olt.ip_address,
        username=olt.ssh_username,
        password=olt.ssh_password,
        enable_password=olt.enable_password,
        port=olt.ssh_port,
    )
    if olt.vendor == 'zte':
        return ZTEcli(**kwargs)
    # Default: Huawei
    return HuaweiCLI(**kwargs)
