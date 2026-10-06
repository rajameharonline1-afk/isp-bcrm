# ফাইল: backend/apps/system_config/services.py
# এই ফাইলটি database-এর setting থেকে email connection ও gateway credentials পড়ার service ধারণ করে।

from django.core.mail import EmailMessage, get_connection

from .models import EmailSetting, PaymentGateway, SystemSetting, CompanySetting


class SystemConfigService:
    """Database-এ রাখা settings অন্য module-এর কাছে সহজে পৌঁছে দেয়।"""

    @staticmethod
    def system():
        return SystemSetting.load()

    @staticmethod
    def company():
        return CompanySetting.load()

    @staticmethod
    def get_email_connection():
        """
        Database-এর EmailSetting থেকে SMTP connection তৈরি করে।
        Email setup চালু না থাকলে None ফেরত দেয়।
        """
        cfg = EmailSetting.load()
        if not (cfg.is_active and cfg.host):
            return None
        return get_connection(
            backend='django.core.mail.backends.smtp.EmailBackend',
            host=cfg.host, port=cfg.port,
            username=cfg.username, password=cfg.password,
            use_tls=cfg.use_tls, use_ssl=cfg.use_ssl,
            timeout=15,
        )

    @staticmethod
    def send_email(subject, body, to):
        """Database setting ব্যবহার করে email পাঠায়। সফল হলে পাঠানো সংখ্যা ফেরত দেয়।"""
        cfg = EmailSetting.load()
        connection = SystemConfigService.get_email_connection()
        if connection is None:
            raise ValueError('Email setup is not active.')
        sender = f"{cfg.from_name} <{cfg.from_email}>" if cfg.from_name else cfg.from_email
        message = EmailMessage(subject, body, sender or cfg.username,
                               [to] if isinstance(to, str) else list(to),
                               connection=connection)
        return message.send(fail_silently=False)

    @staticmethod
    def get_gateway(provider):
        """Active gateway ফেরত দেয়; না থাকলে None।"""
        return PaymentGateway.objects.filter(provider=provider, is_active=True).first()
