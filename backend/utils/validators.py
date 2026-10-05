# ফাইল: backend/utils/validators.py
# এই ফাইলটি ISP-BCRM প্রজেক্টের common validation functions ধারণ করে।

import re
from django.core.exceptions import ValidationError


def validate_bd_phone(value):
    """বাংলাদেশের phone number validate করা (01XXXXXXXXX format)।"""
    pattern = r'^(?:\+88|88)?01[3-9]\d{8}$'
    if not re.match(pattern, str(value)):
        raise ValidationError('Valid Bangladesh phone number দিন (যেমন: 01712345678)')


def validate_nid(value):
    """জাতীয় পরিচয়পত্র নম্বর validate করা (10 বা 17 digit)।"""
    cleaned = str(value).replace('-', '').replace(' ', '')
    if not (len(cleaned) == 10 or len(cleaned) == 17):
        raise ValidationError('Valid NID number দিন (10 বা 17 সংখ্যার)।')
    if not cleaned.isdigit():
        raise ValidationError('NID number শুধুমাত্র সংখ্যা দিয়ে হতে হবে।')


def validate_ip_address(value):
    """IPv4 address validate করা।"""
    pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
    if not re.match(pattern, str(value)):
        raise ValidationError('Valid IP address দিন (যেমন: 192.168.1.1)।')
    parts = str(value).split('.')
    for part in parts:
        if int(part) > 255:
            raise ValidationError('Valid IP address দিন।')


def validate_mac_address(value):
    """MAC address validate করা (XX:XX:XX:XX:XX:XX format)।"""
    pattern = r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$'
    if value and not re.match(pattern, str(value)):
        raise ValidationError('Valid MAC address দিন (যেমন: 00:1A:2B:3C:4D:5E)।')
