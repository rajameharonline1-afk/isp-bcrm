# ফাইল: backend/apps/accounting/management/commands/setup_chart_of_accounts.py
# ISP-BCRM-এর জন্য default Chart of Accounts সেটআপ করার management command।
# চালানোর উপায়: python manage.py setup_chart_of_accounts

from django.core.management.base import BaseCommand
from apps.accounting.models import AccountType, Account


# ISP-এর জন্য standard Chart of Accounts
DEFAULT_ACCOUNTS = [
    # =========== ASSETS (সম্পদ) ===========
    {'type': 'Asset',    'code': '1000', 'name': 'Current Assets',           'group': True,  'parent': None},
    {'type': 'Asset',    'code': '1001', 'name': 'Cash in Hand',              'group': False, 'parent': '1000', 'system': True},
    {'type': 'Asset',    'code': '1002', 'name': 'Petty Cash',                'group': False, 'parent': '1000'},
    {'type': 'Asset',    'code': '1010', 'name': 'bKash Account',             'group': False, 'parent': '1000', 'system': True},
    {'type': 'Asset',    'code': '1011', 'name': 'Nagad Account',             'group': False, 'parent': '1000', 'system': True},
    {'type': 'Asset',    'code': '1012', 'name': 'Rocket Account',            'group': False, 'parent': '1000'},
    {'type': 'Asset',    'code': '1020', 'name': 'Bank Account',              'group': False, 'parent': '1000', 'system': True},
    {'type': 'Asset',    'code': '1100', 'name': 'Accounts Receivable',       'group': False, 'parent': '1000', 'system': True},
    {'type': 'Asset',    'code': '1200', 'name': 'Inventory / Equipment',     'group': False, 'parent': '1000'},
    {'type': 'Asset',    'code': '1300', 'name': 'Prepaid Expenses',          'group': False, 'parent': '1000'},
    {'type': 'Asset',    'code': '1500', 'name': 'Fixed Assets',              'group': True,  'parent': None},
    {'type': 'Asset',    'code': '1510', 'name': 'Network Equipment',         'group': False, 'parent': '1500'},
    {'type': 'Asset',    'code': '1520', 'name': 'Office Equipment',          'group': False, 'parent': '1500'},
    {'type': 'Asset',    'code': '1530', 'name': 'Accumulated Depreciation',  'group': False, 'parent': '1500'},

    # =========== LIABILITIES (দায়) ===========
    {'type': 'Liability','code': '2000', 'name': 'Current Liabilities',       'group': True,  'parent': None},
    {'type': 'Liability','code': '2001', 'name': 'Accounts Payable',          'group': False, 'parent': '2000'},
    {'type': 'Liability','code': '2010', 'name': 'Salary Payable',            'group': False, 'parent': '2000'},
    {'type': 'Liability','code': '2020', 'name': 'Tax Payable',               'group': False, 'parent': '2000'},
    {'type': 'Liability','code': '2030', 'name': 'Advance from Clients',      'group': False, 'parent': '2000'},
    {'type': 'Liability','code': '2500', 'name': 'Long-term Liabilities',     'group': True,  'parent': None},
    {'type': 'Liability','code': '2510', 'name': 'Bank Loan',                 'group': False, 'parent': '2500'},

    # =========== EQUITY (মালিকানা) ===========
    {'type': 'Equity',   'code': '3000', 'name': 'Owner Equity',              'group': True,  'parent': None},
    {'type': 'Equity',   'code': '3001', 'name': 'Capital',                   'group': False, 'parent': '3000'},
    {'type': 'Equity',   'code': '3100', 'name': 'Retained Earnings',         'group': False, 'parent': '3000', 'system': True},
    {'type': 'Equity',   'code': '3200', 'name': 'Drawings',                  'group': False, 'parent': '3000'},

    # =========== INCOME (আয়) ===========
    {'type': 'Income',   'code': '4000', 'name': 'Operating Income',          'group': True,  'parent': None},
    {'type': 'Income',   'code': '4001', 'name': 'ISP Service Income',        'group': False, 'parent': '4000', 'system': True},
    {'type': 'Income',   'code': '4002', 'name': 'Connection Fee Income',     'group': False, 'parent': '4000', 'system': True},
    {'type': 'Income',   'code': '4003', 'name': 'OLT Service Income',        'group': False, 'parent': '4000'},
    {'type': 'Income',   'code': '4004', 'name': 'Late Fee / Penalty',        'group': False, 'parent': '4000'},
    {'type': 'Income',   'code': '4500', 'name': 'Other Income',              'group': True,  'parent': None},
    {'type': 'Income',   'code': '4501', 'name': 'Miscellaneous Income',      'group': False, 'parent': '4500'},

    # =========== EXPENSE (ব্যয়) ===========
    {'type': 'Expense',  'code': '5000', 'name': 'Operating Expenses',        'group': True,  'parent': None},
    {'type': 'Expense',  'code': '5001', 'name': 'Salary Expense',            'group': False, 'parent': '5000', 'system': True},
    {'type': 'Expense',  'code': '5002', 'name': 'Office Rent',               'group': False, 'parent': '5000'},
    {'type': 'Expense',  'code': '5003', 'name': 'Bandwidth Cost',            'group': False, 'parent': '5000'},
    {'type': 'Expense',  'code': '5004', 'name': 'Equipment Maintenance',     'group': False, 'parent': '5000'},
    {'type': 'Expense',  'code': '5005', 'name': 'Electricity Bill',          'group': False, 'parent': '5000'},
    {'type': 'Expense',  'code': '5006', 'name': 'Internet Backbone Cost',    'group': False, 'parent': '5000'},
    {'type': 'Expense',  'code': '5010', 'name': 'Office & Admin Expense',    'group': False, 'parent': '5000', 'system': True},
    {'type': 'Expense',  'code': '5011', 'name': 'Transport & Conveyance',    'group': False, 'parent': '5000'},
    {'type': 'Expense',  'code': '5012', 'name': 'Telephone & Internet',      'group': False, 'parent': '5000'},
    {'type': 'Expense',  'code': '5020', 'name': 'Field Technician Expense',  'group': False, 'parent': '5000'},
    {'type': 'Expense',  'code': '5500', 'name': 'Financial Expenses',        'group': True,  'parent': None},
    {'type': 'Expense',  'code': '5501', 'name': 'Bank Charges',              'group': False, 'parent': '5500'},
    {'type': 'Expense',  'code': '5502', 'name': 'Payment Gateway Fee',       'group': False, 'parent': '5500'},
    {'type': 'Expense',  'code': '5503', 'name': 'Depreciation',              'group': False, 'parent': '5500'},
]

# Account Type definitions
DEFAULT_TYPES = [
    {'name': 'Asset',     'nature': 'debit',  'sort_order': 1},
    {'name': 'Liability', 'nature': 'credit', 'sort_order': 2},
    {'name': 'Equity',    'nature': 'credit', 'sort_order': 3},
    {'name': 'Income',    'nature': 'credit', 'sort_order': 4},
    {'name': 'Expense',   'nature': 'debit',  'sort_order': 5},
]


class Command(BaseCommand):
    help = 'ISP-BCRM-এর জন্য default Chart of Accounts সেটআপ করা'

    def handle(self, *args, **options):
        self.stdout.write('Setting up Chart of Accounts...')

        # Account types তৈরি করা
        type_map = {}
        for t in DEFAULT_TYPES:
            obj, created = AccountType.objects.get_or_create(
                name=t['name'],
                defaults={'nature': t['nature'], 'sort_order': t['sort_order']}
            )
            type_map[t['name']] = obj
            if created:
                self.stdout.write(self.style.SUCCESS(f"  Created type: {t['name']}"))

        # Accounts তৈরি করা (parent আগে তৈরি হতে হবে)
        code_map = {}
        for acc_data in DEFAULT_ACCOUNTS:
            parent = code_map.get(acc_data.get('parent')) if acc_data.get('parent') else None
            obj, created = Account.objects.get_or_create(
                code=acc_data['code'],
                defaults={
                    'name':            acc_data['name'],
                    'account_type':    type_map[acc_data['type']],
                    'parent':          parent,
                    'is_group':        acc_data.get('group', False),
                    'is_system':       acc_data.get('system', False),
                    'opening_balance': 0,
                }
            )
            code_map[acc_data['code']] = obj
            if created:
                self.stdout.write(f"  [{acc_data['code']}] {acc_data['name']}")

        self.stdout.write(self.style.SUCCESS(
            f'\nChart of Accounts setup complete! {len(DEFAULT_ACCOUNTS)} accounts defined.'
        ))
