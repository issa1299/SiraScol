from django.contrib import admin
from .models import FeeType, Invoice, Payment, Expense


@admin.register(FeeType)
class FeeTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'default_amount', 'is_active')


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('student', 'fee_type', 'amount', 'status', 'academic_year')
    list_filter = ('status', 'academic_year')


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('invoice', 'amount', 'payment_date', 'method')


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ('date', 'category', 'amount', 'motif', 'academic_year')
    list_filter = ('category', 'academic_year')
