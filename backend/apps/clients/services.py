# ফাইল: backend/apps/clients/services.py
# এই ফাইলটি Client management-এর সব business logic ধারণ করে।
# Mikrotik + FreeRADIUS sync, enable/disable, renew সব এখানে।

import logging
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from django.db import transaction
from django.utils import timezone

from apps.servers.services import MikrotikService, MikrotikAPIError, FreeRADIUSService, FreeRADIUSError

logger = logging.getLogger(__name__)


class ClientService:
    """
    Client-এর সব business logic এই class-এ।
    Mikrotik ও RADIUS-এ sync করা, status পরিবর্তন করা সব এখানে।
    """

    @staticmethod
    @transaction.atomic
    def create_client(validated_data: dict, created_by, sync_mikrotik=True, sync_radius=True) -> tuple:
        """
        নতুন client তৈরি করে এবং Mikrotik ও RADIUS-এ PPPoE user তৈরি করে।
        return: (client_instance, sync_results_dict)
        """
        from apps.clients.models import Client

        # Package থেকে monthly_bill নেওয়া (override না থাকলে)
        if not validated_data.get('monthly_bill') and validated_data.get('package'):
            validated_data['monthly_bill'] = validated_data['package'].monthly_price

        # Expiry date calculate করা
        if not validated_data.get('expiry_date'):
            validated_data['expiry_date'] = ClientService.calculate_expiry_date(
                connection_date=validated_data.get('connection_date', date.today()),
                bill_date=validated_data.get('bill_date', 1),
                expiry_days=validated_data.get('expiry_day', 30),
            )

        # Client DB-তে save করা
        client = Client.objects.create(**validated_data, created_by=created_by)

        sync_results = {}

        # Mikrotik-এ PPPoE secret তৈরি করা
        if sync_mikrotik and client.router:
            try:
                svc = MikrotikService(**client.router.get_api_credentials())
                result = svc.create_pppoe_secret(
                    username=client.username,
                    password=client.password,
                    profile=client.pppoe_profile or (client.package.mikrotik_profile if client.package else 'default'),
                    comment=f"{client.full_name} | {client.phone}",
                )
                sync_results['mikrotik'] = result
            except MikrotikAPIError as e:
                sync_results['mikrotik'] = {'success': False, 'error': str(e)}
                logger.error(f"Mikrotik sync failed for {client.username}: {e}")

        # FreeRADIUS-এ user তৈরি করা
        if sync_radius:
            try:
                radius_group = client.pppoe_profile or (client.package.mikrotik_profile if client.package else 'default')
                result = FreeRADIUSService.create_user(
                    username=client.username,
                    password=client.password,
                    group=radius_group,
                )
                sync_results['radius'] = result
            except FreeRADIUSError as e:
                sync_results['radius'] = {'success': False, 'error': str(e)}
                logger.error(f"RADIUS sync failed for {client.username}: {e}")

        return client, sync_results

    @staticmethod
    @transaction.atomic
    def enable_client(client, performed_by=None, reason='') -> dict:
        """
        Client connection enable করে (বিল পরিশোধ বা renewal-এর পর)।
        Mikrotik enable + RADIUS Auth-Type Reject সরানো হয়।
        """
        from apps.clients.models import Client, ClientStatusLog

        old_status = client.status
        results    = {}

        # Mikrotik enable
        if client.router:
            try:
                svc = MikrotikService(**client.router.get_api_credentials())
                results['mikrotik'] = svc.enable_pppoe_secret(client.username)
            except MikrotikAPIError as e:
                results['mikrotik'] = {'success': False, 'error': str(e)}

        # RADIUS enable
        try:
            results['radius'] = FreeRADIUSService.enable_user(client.username)
        except FreeRADIUSError as e:
            results['radius'] = {'success': False, 'error': str(e)}

        # Client status আপডেট
        client.status = Client.Status.ACTIVE
        client.save(update_fields=['status', 'updated_at'])

        ClientStatusLog.objects.create(
            client=client, action=ClientStatusLog.Action.ACTIVATED,
            from_status=old_status, to_status=Client.Status.ACTIVE,
            reason=reason, performed_by=performed_by,
        )

        logger.info(f"Client enabled: {client.username}")
        return results

    @staticmethod
    @transaction.atomic
    def disable_client(client, performed_by=None, reason='Auto expired') -> dict:
        """
        Client connection disable করে (বিল বকেয়া বা মেয়াদ শেষ)।
        Mikrotik disable + RADIUS Auth-Type Reject যোগ করা হয়।
        """
        from apps.clients.models import Client, ClientStatusLog

        old_status = client.status
        results    = {}

        # Mikrotik disable (active session-ও disconnect হবে)
        if client.router:
            try:
                svc = MikrotikService(**client.router.get_api_credentials())
                results['mikrotik'] = svc.disable_pppoe_secret(client.username)
            except MikrotikAPIError as e:
                results['mikrotik'] = {'success': False, 'error': str(e)}

        # RADIUS disable
        try:
            results['radius'] = FreeRADIUSService.disable_user(client.username)
        except FreeRADIUSError as e:
            results['radius'] = {'success': False, 'error': str(e)}

        # Client status আপডেট
        new_status = Client.Status.EXPIRED if reason == 'Auto expired' else Client.Status.SUSPENDED
        client.status = new_status
        client.save(update_fields=['status', 'updated_at'])

        ClientStatusLog.objects.create(
            client=client,
            action=ClientStatusLog.Action.SUSPENDED if new_status == Client.Status.SUSPENDED else ClientStatusLog.Action.EXPIRED,
            from_status=old_status, to_status=new_status,
            reason=reason, performed_by=performed_by,
        )

        logger.info(f"Client disabled: {client.username} reason: {reason}")
        return results

    @staticmethod
    @transaction.atomic
    def renew_client(client, months=1, performed_by=None, advance_used=0) -> dict:
        """
        Client renewal করা — expiry date বাড়ানো হয়।
        Advance balance ব্যবহার করার option আছে।
        """
        from apps.clients.models import Client, ClientStatusLog

        old_expiry = client.expiry_date

        # নতুন expiry date calculate করা
        base_date = max(client.expiry_date or date.today(), date.today())
        new_expiry = base_date + relativedelta(months=months)
        client.expiry_date = new_expiry
        client.is_renewed  = True
        client.renewed_at  = timezone.now()

        # Advance balance deduct করা
        if advance_used > 0:
            client.advance_balance = max(0, client.advance_balance - advance_used)

        # Status Active করা
        if client.status in (Client.Status.EXPIRED, Client.Status.SUSPENDED):
            old_status = client.status
            client.status = Client.Status.ACTIVE
            ClientStatusLog.objects.create(
                client=client, action=ClientStatusLog.Action.RENEWED,
                from_status=old_status, to_status=Client.Status.ACTIVE,
                reason=f'Renewed for {months} month(s)', performed_by=performed_by,
            )
            # Mikrotik ও RADIUS enable করা
            ClientService.enable_client(client, performed_by=performed_by, reason='Renewed')

        client.save()
        logger.info(f"Client renewed: {client.username} expiry: {old_expiry} → {new_expiry}")

        return {
            'success': True,
            'old_expiry': str(old_expiry),
            'new_expiry': str(new_expiry),
            'months': months,
        }

    @staticmethod
    def change_package(client, new_package, performed_by=None) -> dict:
        """
        Client-এর package পরিবর্তন করে।
        Mikrotik profile ও RADIUS group আপডেট করা হয়।
        """
        results = {}
        old_package = client.package

        # Mikrotik profile change
        if client.router and new_package.mikrotik_profile:
            try:
                svc = MikrotikService(**client.router.get_api_credentials())
                results['mikrotik'] = svc.change_pppoe_profile(client.username, new_package.mikrotik_profile)
            except MikrotikAPIError as e:
                results['mikrotik'] = {'success': False, 'error': str(e)}

        # RADIUS group change
        if new_package.mikrotik_profile:
            try:
                results['radius'] = FreeRADIUSService.change_user_package(client.username, new_package.mikrotik_profile)
            except FreeRADIUSError as e:
                results['radius'] = {'success': False, 'error': str(e)}

        # Client আপডেট
        client.package       = new_package
        client.monthly_bill  = new_package.monthly_price
        client.pppoe_profile = new_package.mikrotik_profile
        client.save(update_fields=['package', 'monthly_bill', 'pppoe_profile', 'updated_at'])

        logger.info(f"Package changed: {client.username} {old_package} → {new_package}")
        return results

    @staticmethod
    def calculate_expiry_date(connection_date: date, bill_date: int, expiry_days: int = 30) -> date:
        """
        Client-এর expiry date calculate করা।
        bill_date = প্রতি মাসে যে তারিখে বিল generate হবে।
        expiry_days = বিল generate-র কত দিন পরে expire হবে।
        """
        today = connection_date or date.today()
        # এই মাসের bill_date খোঁজা
        try:
            this_month_bill = today.replace(day=bill_date)
        except ValueError:
            # মাসে ২৮/২৯/৩০ দিন থাকলে শেষ দিন ব্যবহার করা
            import calendar
            last_day = calendar.monthrange(today.year, today.month)[1]
            this_month_bill = today.replace(day=min(bill_date, last_day))

        # আজ bill_date-এর আগে হলে এই মাসের বিল, নইলে পরের মাসের
        if today <= this_month_bill:
            return this_month_bill + timedelta(days=expiry_days)
        else:
            next_month = this_month_bill + relativedelta(months=1)
            return next_month + timedelta(days=expiry_days)
