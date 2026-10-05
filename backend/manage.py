#!/usr/bin/env python
# ফাইল: backend/manage.py
# এই ফাইলটি Django management commands চালানোর জন্য ব্যবহৃত হয় (runserver, migrate, etc.)

import os
import sys


def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Django import করা যাচ্ছে না। Django installed আছে কিনা এবং "
            "virtual environment activate করা আছে কিনা নিশ্চিত করুন।"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
