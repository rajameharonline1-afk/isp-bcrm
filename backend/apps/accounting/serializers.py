# ফাইল: backend/apps/accounting/serializers.py
# Accounting module-এর সব serializer।

from rest_framework import serializers
from .models import AccountType, Account, JournalEntry, TransactionLine, AccountBalance


class AccountTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model  = AccountType
        fields = '__all__'


class AccountSerializer(serializers.ModelSerializer):
    account_type_name = serializers.CharField(source='account_type.name', read_only=True)
    parent_name       = serializers.CharField(source='parent.name', read_only=True, default='')
    current_balance   = serializers.DecimalField(max_digits=14, decimal_places=2,
                                                   source='balance', read_only=True)

    class Meta:
        model  = Account
        fields = [
            'id', 'code', 'name', 'account_type', 'account_type_name',
            'parent', 'parent_name', 'description', 'is_group', 'is_system',
            'opening_balance', 'current_balance', 'is_active', 'created_at',
        ]


class AccountCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Account
        fields = ['code', 'name', 'account_type', 'parent', 'description',
                  'is_group', 'opening_balance', 'is_active']

    def validate_code(self, value):
        if Account.objects.filter(code=value).exists():
            raise serializers.ValidationError("Account code already exists.")
        return value


class TransactionLineSerializer(serializers.ModelSerializer):
    account_name = serializers.CharField(source='account.name', read_only=True)
    account_code = serializers.CharField(source='account.code', read_only=True)

    class Meta:
        model  = TransactionLine
        fields = ['id', 'account', 'account_code', 'account_name', 'type', 'amount', 'description']


class TransactionLineCreateSerializer(serializers.Serializer):
    """Journal line create-এর জন্য nested serializer।"""
    account_code = serializers.CharField(max_length=20)
    type         = serializers.ChoiceField(choices=['debit', 'credit'])
    amount       = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=0.01)
    desc         = serializers.CharField(max_length=200, required=False, default='', allow_blank=True)


class JournalEntryListSerializer(serializers.ModelSerializer):
    total_debit  = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    total_credit = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    is_balanced  = serializers.BooleanField(read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True, default='')

    class Meta:
        model  = JournalEntry
        fields = [
            'id', 'entry_no', 'date', 'entry_type', 'description',
            'reference', 'is_posted', 'total_debit', 'total_credit',
            'is_balanced', 'created_by_name', 'created_at',
        ]


class JournalEntryDetailSerializer(serializers.ModelSerializer):
    lines        = TransactionLineSerializer(many=True, read_only=True)
    total_debit  = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    total_credit = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    is_balanced  = serializers.BooleanField(read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True, default='')
    posted_by_name  = serializers.CharField(source='posted_by.get_full_name', read_only=True, default='')

    class Meta:
        model  = JournalEntry
        fields = '__all__'


class JournalEntryCreateSerializer(serializers.Serializer):
    """Manual journal entry তৈরির serializer।"""
    date        = serializers.DateField()
    description = serializers.CharField(max_length=500)
    entry_type  = serializers.ChoiceField(choices=JournalEntry.EntryType.choices,
                                           default=JournalEntry.EntryType.MANUAL)
    reference   = serializers.CharField(max_length=100, required=False, default='', allow_blank=True)
    lines       = TransactionLineCreateSerializer(many=True, min_length=2)
    auto_post   = serializers.BooleanField(default=False)

    def validate_lines(self, lines):
        total_debit  = sum(l['amount'] for l in lines if l['type'] == 'debit')
        total_credit = sum(l['amount'] for l in lines if l['type'] == 'credit')
        if abs(total_debit - total_credit) > 0.01:
            raise serializers.ValidationError(
                f"Lines not balanced: Debit={total_debit} Credit={total_credit}"
            )
        return lines


class AccountBalanceSerializer(serializers.ModelSerializer):
    account_name = serializers.CharField(source='account.name', read_only=True)
    account_code = serializers.CharField(source='account.code', read_only=True)

    class Meta:
        model  = AccountBalance
        fields = '__all__'
