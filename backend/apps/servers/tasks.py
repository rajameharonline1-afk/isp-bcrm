# ফাইল: backend/apps/servers/tasks.py
# এই ফাইলটি Router backup, bulk import ও auto disable-এর Celery background tasks ধারণ করে।

import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def router_backup_task(self, router_id: int, user_id: int, note: str = ''):
    """
    Mikrotik Router-এর backup তৈরি করে database-এ save করে।
    Admin dashboard থেকে manually বা scheduled হিসেবে চালানো যায়।
    """
    from apps.servers.models import MikrotikRouter, RouterBackup
    from apps.servers.services import MikrotikService, MikrotikAPIError
    from apps.accounts.models import User

    try:
        router = MikrotikRouter.objects.get(id=router_id)
        user = User.objects.get(id=user_id)

        service = MikrotikService(**router.get_api_credentials())
        backup_name = f"{router.name.replace(' ', '_')}-{timezone.now().strftime('%Y%m%d-%H%M%S')}"

        result = service.create_backup(backup_name)

        if result['success']:
            # Router-এর SSH credentials থাকলে file download করা
            if router.ssh_username and router.ssh_password:
                try:
                    backup_data = service.download_backup_via_ssh(
                        ssh_username=router.ssh_username,
                        ssh_password=router.ssh_password,
                        backup_name=backup_name,
                        ssh_port=router.ssh_port,
                    )

                    from django.core.files.base import ContentFile
                    backup = RouterBackup.objects.create(
                        router=router,
                        file_name=f"{backup_name}.backup",
                        file_size=len(backup_data),
                        note=note,
                        created_by=user,
                    )
                    backup.backup_file.save(
                        f"{backup_name}.backup",
                        ContentFile(backup_data),
                        save=True,
                    )
                    logger.info(f"Router backup downloaded: {router.name} - {backup_name}")

                except Exception as e:
                    # SSH download না হলেও router-এ backup আছে
                    RouterBackup.objects.create(
                        router=router,
                        file_name=f"{backup_name}.backup",
                        note=f"{note} (SSH download failed: {e})",
                        created_by=user,
                    )
            else:
                RouterBackup.objects.create(
                    router=router,
                    file_name=f"{backup_name}.backup",
                    note=note or 'Backup created on router (SSH not configured)',
                    created_by=user,
                )

            # Last backup time আপডেট
            router.last_backup = timezone.now()
            router.save(update_fields=['last_backup'])

            return {'success': True, 'backup_name': backup_name}

    except MikrotikRouter.DoesNotExist:
        logger.error(f"Router not found: {router_id}")
        return {'success': False, 'error': 'Router পাওয়া যায়নি।'}
    except MikrotikAPIError as e:
        logger.error(f"Mikrotik backup error for router {router_id}: {e}")
        raise self.retry(exc=e, countdown=60)
    except Exception as e:
        logger.error(f"Backup task error: {e}")
        return {'success': False, 'error': str(e)}


@shared_task(bind=True)
def bulk_import_task(self, records: list, router_id, user_id: int, sync_to_radius: bool = True):
    """
    Excel বা Mikrotik থেকে bulk PPPoE user import করে।
    প্রতিটি record-এর জন্য Mikrotik ও RADIUS-এ user তৈরি করে।
    """
    from apps.servers.models import MikrotikRouter
    from apps.servers.services import MikrotikService, MikrotikAPIError, FreeRADIUSService, FreeRADIUSError

    results = {'success': 0, 'failed': 0, 'errors': []}

    router = None
    service = None

    if router_id:
        try:
            router = MikrotikRouter.objects.get(id=router_id)
            service = MikrotikService(**router.get_api_credentials())
        except MikrotikRouter.DoesNotExist:
            return {'success': False, 'error': 'Router পাওয়া যায়নি।'}

    for record in records:
        username = str(record.get('username', '')).strip()
        password = str(record.get('password', '')).strip()
        profile = str(record.get('profile', 'default')).strip()

        if not username or not password:
            results['failed'] += 1
            results['errors'].append(f"Invalid record: {record}")
            continue

        # Mikrotik-এ create
        if service:
            try:
                service.create_pppoe_secret(username=username, password=password, profile=profile)
                results['success'] += 1
            except MikrotikAPIError as e:
                results['failed'] += 1
                results['errors'].append(f"{username}: Mikrotik - {e}")
                continue

        # RADIUS-এ create
        if sync_to_radius:
            try:
                FreeRADIUSService.create_user(
                    username=username,
                    password=password,
                    group=record.get('radius_group', profile),
                )
            except FreeRADIUSError as e:
                results['errors'].append(f"{username}: RADIUS - {e}")

    logger.info(f"Bulk import completed: {results['success']} success, {results['failed']} failed")
    return results


@shared_task
def check_all_routers_status():
    """
    সব active router-এর connection status check করে।
    Celery Beat-এ প্রতি ৫ মিনিটে চলে।
    """
    from apps.servers.models import MikrotikRouter
    from apps.servers.services import MikrotikService

    routers = MikrotikRouter.objects.filter(is_active=True)
    online = 0
    offline = 0

    for router in routers:
        try:
            service = MikrotikService(**router.get_api_credentials())
            result = service.test_connection()
            new_status = MikrotikRouter.RouterStatus.ONLINE if result['success'] else MikrotikRouter.RouterStatus.OFFLINE

            if new_status != router.status:
                router.status = new_status
                router.last_checked = timezone.now()
                router.save(update_fields=['status', 'last_checked'])

            if result['success']:
                online += 1
            else:
                offline += 1
        except Exception:
            offline += 1

    logger.info(f"Router status check: {online} online, {offline} offline")
    return {'online': online, 'offline': offline}


@shared_task
def auto_backup_all_routers():
    """
    সব active router-এর daily automatic backup নেয়।
    Celery Beat-এ প্রতি রাত ২টায় চলে।
    """
    from apps.servers.models import MikrotikRouter

    routers = MikrotikRouter.objects.filter(is_active=True)
    for router in routers:
        # প্রতিটি router-এর জন্য আলাদা task queue করা
        router_backup_task.delay(router.id, None, 'Automatic daily backup')

    logger.info(f"Auto backup scheduled for {routers.count()} routers")


@shared_task
def sync_active_sessions_to_db():
    """
    FreeRADIUS radacct থেকে active session data DB-তে sync করে।
    Dashboard-এ live connected users দেখানোর জন্য।
    """
    from apps.servers.services import FreeRADIUSService

    try:
        sessions = FreeRADIUSService.get_active_sessions()
        logger.info(f"Active RADIUS sessions: {len(sessions)}")
        return {'active_sessions': len(sessions)}
    except Exception as e:
        logger.error(f"Session sync error: {e}")
        return {'error': str(e)}
