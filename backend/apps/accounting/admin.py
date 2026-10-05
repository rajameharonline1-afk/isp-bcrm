# ফাইল: backend/apps/accounting/admin.py
from django.contrib import admin
from .models import AccountType, Account, JournalEntry, TransactionLine, AccountBalance


@admin.register(AccountType)
class AccountTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'nature', 'sort_order']


class TransactionLineInline(admin.TabularInline):
    model  = TransactionLine
    extra  = 0
    fields = ['account', 'type', 'amount', 'description']


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display  = ['code', 'name', 'account_type', 'parent', 'is_group', 'is_active']
    list_filter   = ['account_type', 'is_group', 'is_active']
    search_fields = ['code', 'name']
    ordering      = ['code']


@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    list_display  = ['entry_no', 'date', 'entry_type', 'description', 'is_posted', 'created_at']
    list_filter   = ['entry_type', 'is_posted']
    search_fields = ['entry_no', 'description', 'reference']
    readonly_fields = ['entry_no', 'is_posted', 'posted_by', 'posted_at', 'created_at']
    inlines       = [TransactionLineInline]
    date_hierarchy = 'date'


@admin.register(AccountBalance)
class AccountBalanceAdmin(admin.ModelAdmin):
    list_display  = ['account', 'period_month', 'opening_balance', 'total_debit',
                     'total_credit', 'closing_balance']
    list_filter   = ['period_month']
    raw_id_fields = ['account']
