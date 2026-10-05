# ফাইল: backend/apps/olt/services/snmp_service.py
# এই ফাইলটি SNMP protocol ব্যবহার করে OLT থেকে ONU RX power ও status data collect করে।
# pysnmp library ব্যবহার করে SNMP v1/v2c/v3 সব version support করে।

import logging
from typing import Optional
from pysnmp.hlapi import (
    SnmpEngine, CommunityData, UsmUserData,
    UdpTransportTarget, ContextData,
    ObjectType, ObjectIdentity,
    getCmd, nextCmd, bulkCmd,
    usmHMACSHAAuthProtocol, usmAesCfb128Protocol,
    usmHMACMD5AuthProtocol, usmDESPrivProtocol,
)
from pysnmp.error import PySnmpError

logger = logging.getLogger(__name__)


# =============================================
# Vendor-specific SNMP OID mappings
# =============================================

OID_PROFILES = {
    'huawei': {
        # Huawei MA5600T / MA5800 GPON OID
        # ONU operational state: 1=online, 2=offline
        'onu_status':       '1.3.6.1.4.1.2011.6.128.1.1.2.51.1.4',
        # ONU serial number
        'onu_serial':       '1.3.6.1.4.1.2011.6.128.1.1.2.43.1.3',
        # ONU RX power (OLT-side, unit: 0.01 dBm, need /100)
        'onu_rx_power':     '1.3.6.1.4.1.2011.6.128.1.1.2.223.1.1',
        # ONU TX power (unit: 0.01 dBm)
        'onu_tx_power':     '1.3.6.1.4.1.2011.6.128.1.1.2.223.1.2',
        # OLT RX power
        'olt_rx_power':     '1.3.6.1.4.1.2011.6.128.1.1.2.223.1.3',
        # ONU temperature
        'onu_temperature':  '1.3.6.1.4.1.2011.6.128.1.1.2.223.1.5',
        # ONU voltage (unit: 0.001 V)
        'onu_voltage':      '1.3.6.1.4.1.2011.6.128.1.1.2.223.1.6',
        # Scale factor for power OIDs
        'power_scale':      100.0,
        'voltage_scale':    1000.0,
        'temp_scale':       1.0,
    },
    'zte': {
        # ZTE C300 / C320 GPON OID
        'onu_status':       '1.3.6.1.4.1.3902.1012.3.28.1.1.3',
        'onu_serial':       '1.3.6.1.4.1.3902.1012.3.28.2.1.2',
        # ZTE RX power (unit: 0.01 dBm)
        'onu_rx_power':     '1.3.6.1.4.1.3902.1012.3.50.12.1.1.10',
        'onu_tx_power':     '1.3.6.1.4.1.3902.1012.3.50.12.1.1.11',
        'olt_rx_power':     '1.3.6.1.4.1.3902.1012.3.50.12.1.1.12',
        'onu_temperature':  '1.3.6.1.4.1.3902.1012.3.50.12.1.1.13',
        'power_scale':      100.0,
        'voltage_scale':    1000.0,
        'temp_scale':       1.0,
    },
    'fiberhome': {
        # FiberHome AN5516 OID
        'onu_status':       '1.3.6.1.4.1.5875.91.1.8.4.1.4',
        'onu_serial':       '1.3.6.1.4.1.5875.91.1.8.4.1.2',
        'onu_rx_power':     '1.3.6.1.4.1.5875.91.1.8.4.1.12',
        'onu_tx_power':     '1.3.6.1.4.1.5875.91.1.8.4.1.13',
        'olt_rx_power':     '1.3.6.1.4.1.5875.91.1.8.4.1.14',
        'onu_temperature':  '1.3.6.1.4.1.5875.91.1.8.4.1.15',
        'power_scale':      100.0,
        'voltage_scale':    1000.0,
        'temp_scale':       1.0,
    },
    'bdcom': {
        # BDCOM GP3600 EPON/GPON OID
        'onu_status':       '1.3.6.1.4.1.3320.101.3.1.1.3',
        'onu_serial':       '1.3.6.1.4.1.3320.101.3.1.1.2',
        'onu_rx_power':     '1.3.6.1.4.1.3320.101.3.1.1.10',
        'onu_tx_power':     '1.3.6.1.4.1.3320.101.3.1.1.11',
        'olt_rx_power':     '1.3.6.1.4.1.3320.101.3.1.1.12',
        'onu_temperature':  '1.3.6.1.4.1.3320.101.3.1.1.13',
        'power_scale':      100.0,
        'voltage_scale':    1000.0,
        'temp_scale':       1.0,
    },
}

# ONU status code mapping (vendor-specific integer → text)
ONU_STATUS_MAP = {
    'huawei': {1: 'online', 2: 'offline', 3: 'los', 4: 'dying_gasp', 5: 'offline'},
    'zte':    {1: 'online', 2: 'offline', 3: 'los', 6: 'dying_gasp'},
    'fiberhome': {1: 'online', 2: 'offline', 3: 'los'},
    'bdcom':  {1: 'online', 2: 'offline', 3: 'los'},
}


class SNMPService:
    """
    SNMP protocol ব্যবহার করে OLT থেকে ONU signal data collect করার service।
    প্রতি ৫ মিনিটে Celery task এই service call করে।
    """

    def __init__(self, host: str, community: str, port: int = 161,
                 timeout: int = 10, retries: int = 2, version: str = 'v2c',
                 v3_username: str = '', v3_auth_key: str = '', v3_priv_key: str = '',
                 v3_auth_proto: str = 'SHA', v3_priv_proto: str = 'AES'):
        self.host      = host
        self.community = community
        self.port      = port
        self.timeout   = timeout
        self.retries   = retries
        self.version   = version
        # SNMPv3 credentials
        self.v3_username  = v3_username
        self.v3_auth_key  = v3_auth_key
        self.v3_priv_key  = v3_priv_key
        self.v3_auth_proto = v3_auth_proto
        self.v3_priv_proto = v3_priv_proto

    def _get_auth_data(self):
        """SNMP version অনুযায়ী authentication data তৈরি করা।"""
        if self.version == 'v3':
            auth_proto = usmHMACSHAAuthProtocol if self.v3_auth_proto == 'SHA' else usmHMACMD5AuthProtocol
            priv_proto = usmAesCfb128Protocol if self.v3_priv_proto == 'AES' else usmDESPrivProtocol
            return UsmUserData(
                self.v3_username,
                authKey=self.v3_auth_key,
                privKey=self.v3_priv_key,
                authProtocol=auth_proto,
                privProtocol=priv_proto,
            )
        # v1 বা v2c
        mp_model = 1 if self.version == 'v2c' else 0
        return CommunityData(self.community, mpModel=mp_model)

    def _get_transport(self):
        """UDP transport target তৈরি করা।"""
        return UdpTransportTarget(
            (self.host, self.port),
            timeout=self.timeout,
            retries=self.retries,
        )

    def snmp_get(self, oid: str) -> Optional[str]:
        """একটি নির্দিষ্ট OID-এর value নেওয়া (SNMP GET)।"""
        try:
            engine = SnmpEngine()
            error_indication, error_status, error_index, var_binds = next(
                getCmd(
                    engine,
                    self._get_auth_data(),
                    self._get_transport(),
                    ContextData(),
                    ObjectType(ObjectIdentity(oid)),
                )
            )
            if error_indication:
                logger.warning(f"SNMP GET error [{self.host}]: {error_indication}")
                return None
            if error_status:
                logger.warning(f"SNMP GET error status [{self.host}]: {error_status}")
                return None
            for var_bind in var_binds:
                return str(var_bind[1])
        except PySnmpError as e:
            logger.error(f"SNMP GET exception [{self.host}]: {e}")
            return None

    def snmp_walk(self, oid: str) -> dict:
        """
        একটি OID subtree walk করে সব values dictionary হিসেবে return করে।
        ONU list, RX power সব data এইভাবে collect করা হয়।
        key: OID index (শেষ অংশ), value: data
        """
        result = {}
        try:
            engine = SnmpEngine()
            for error_indication, error_status, error_index, var_binds in nextCmd(
                engine,
                self._get_auth_data(),
                self._get_transport(),
                ContextData(),
                ObjectType(ObjectIdentity(oid)),
                lexicographicMode=False,
            ):
                if error_indication:
                    logger.warning(f"SNMP WALK error [{self.host}]: {error_indication}")
                    break
                if error_status:
                    logger.warning(f"SNMP WALK error status [{self.host}]: {error_status}")
                    break
                for var_bind in var_binds:
                    oid_str = str(var_bind[0])
                    value   = str(var_bind[1])
                    # OID-এর base prefix সরিয়ে index নেওয়া
                    if oid in oid_str:
                        index = oid_str[len(oid):].lstrip('.')
                        result[index] = value
        except PySnmpError as e:
            logger.error(f"SNMP WALK exception [{self.host}]: {e}")
        return result

    def test_connection(self) -> dict:
        """SNMP connection test — sysDescr OID read করে।"""
        sys_descr = self.snmp_get('1.3.6.1.2.1.1.1.0')
        sys_name  = self.snmp_get('1.3.6.1.2.1.1.5.0')
        if sys_descr is not None:
            return {'success': True, 'sys_descr': sys_descr, 'sys_name': sys_name}
        return {'success': False, 'error': f'SNMP connection failed to {self.host}'}

    # =============================================
    # ONU Data Collection (Vendor-specific)
    # =============================================

    def collect_onu_rx_powers(self, vendor: str, custom_oids: dict = None) -> dict:
        """
        OLT থেকে সব ONU-র RX power data SNMP walk করে collect করে।
        return: {onu_index: {'rx_power': float, 'tx_power': float, ...}}
        """
        oids = custom_oids or OID_PROFILES.get(vendor, OID_PROFILES['huawei'])
        power_scale = oids.get('power_scale', 100.0)

        result = {}

        # RX power walk
        rx_raw = self.snmp_walk(oids['onu_rx_power'])
        for index, raw_val in rx_raw.items():
            try:
                int_val = int(raw_val)
                # 0x7FFFFFFF বা 0x80000000 = invalid reading
                if int_val in (0x7FFFFFFF, -2147483648, 0):
                    rx_dbm = None
                else:
                    rx_dbm = round(int_val / power_scale, 2)
                result.setdefault(index, {})['rx_power'] = rx_dbm
            except (ValueError, ZeroDivisionError):
                result.setdefault(index, {})['rx_power'] = None

        # TX power walk
        if oids.get('onu_tx_power'):
            tx_raw = self.snmp_walk(oids['onu_tx_power'])
            for index, raw_val in tx_raw.items():
                try:
                    int_val = int(raw_val)
                    tx_dbm = None if int_val in (0x7FFFFFFF, -2147483648, 0) else round(int_val / power_scale, 2)
                    result.setdefault(index, {})['tx_power'] = tx_dbm
                except ValueError:
                    result.setdefault(index, {})['tx_power'] = None

        # OLT-side RX power
        if oids.get('olt_rx_power'):
            olt_rx_raw = self.snmp_walk(oids['olt_rx_power'])
            for index, raw_val in olt_rx_raw.items():
                try:
                    int_val = int(raw_val)
                    olt_rx = None if int_val in (0x7FFFFFFF, -2147483648, 0) else round(int_val / power_scale, 2)
                    result.setdefault(index, {})['olt_rx_power'] = olt_rx
                except ValueError:
                    result.setdefault(index, {})['olt_rx_power'] = None

        # Temperature
        if oids.get('onu_temperature'):
            temp_scale = oids.get('temp_scale', 1.0)
            temp_raw = self.snmp_walk(oids['onu_temperature'])
            for index, raw_val in temp_raw.items():
                try:
                    result.setdefault(index, {})['temperature'] = round(int(raw_val) / temp_scale, 1)
                except ValueError:
                    pass

        # Voltage
        if oids.get('onu_voltage'):
            volt_scale = oids.get('voltage_scale', 1000.0)
            volt_raw = self.snmp_walk(oids['onu_voltage'])
            for index, raw_val in volt_raw.items():
                try:
                    result.setdefault(index, {})['voltage'] = round(int(raw_val) / volt_scale, 3)
                except ValueError:
                    pass

        logger.info(f"SNMP collected {len(result)} ONU power readings from {self.host}")
        return result

    def collect_onu_statuses(self, vendor: str, custom_oids: dict = None) -> dict:
        """
        OLT থেকে সব ONU-র operational status collect করে।
        return: {onu_index: 'online'/'offline'/'los'/...}
        """
        oids      = custom_oids or OID_PROFILES.get(vendor, OID_PROFILES['huawei'])
        status_map = ONU_STATUS_MAP.get(vendor, ONU_STATUS_MAP['huawei'])
        result    = {}

        status_raw = self.snmp_walk(oids.get('onu_status', ''))
        for index, raw_val in status_raw.items():
            try:
                code = int(raw_val)
                result[index] = status_map.get(code, 'offline')
            except ValueError:
                result[index] = 'unknown'

        return result

    def collect_onu_serials(self, vendor: str, custom_oids: dict = None) -> dict:
        """ONU serial number তালিকা collect করা।"""
        oids = custom_oids or OID_PROFILES.get(vendor, OID_PROFILES['huawei'])
        raw  = self.snmp_walk(oids.get('onu_serial', ''))
        result = {}
        for index, val in raw.items():
            # Hex string থেকে readable serial তৈরি
            try:
                # pysnmp OctetString → hex format হতে পারে
                clean = val.replace('0x', '').replace(' ', '')
                if len(clean) >= 8:
                    result[index] = clean.upper()
                else:
                    result[index] = val
            except Exception:
                result[index] = val
        return result

    def full_poll(self, vendor: str, custom_oids: dict = None) -> dict:
        """
        একটি OLT-এর সব ONU data একসাথে collect করে।
        return: {index: {rx_power, tx_power, olt_rx_power, temperature, voltage, status, serial}}
        """
        powers   = self.collect_onu_rx_powers(vendor, custom_oids)
        statuses = self.collect_onu_statuses(vendor, custom_oids)
        serials  = self.collect_onu_serials(vendor, custom_oids)

        # সব data merge করা
        all_indices = set(powers) | set(statuses) | set(serials)
        merged = {}
        for idx in all_indices:
            merged[idx] = {
                **powers.get(idx, {}),
                'status': statuses.get(idx, 'unknown'),
                'serial_number': serials.get(idx, ''),
            }
        return merged
