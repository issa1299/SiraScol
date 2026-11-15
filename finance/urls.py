from django.urls import path
from . import views

app_name = 'finance'

urlpatterns = [
    path('', views.finance_dashboard, name='dashboard'),
    path('classes/', views.finance_classes, name='classes'),
    path('classes/<int:classroom_id>/', views.finance_class_students, name='class_students'),
    path('eleve/<int:student_id>/paiement/', views.student_payment_modal, name='student_payment'),
    path('factures/', views.invoice_list, name='invoices'),
    path('factures/ajouter/', views.invoice_create, name='invoice_create'),
    path('paiement/', views.payment_create, name='payment_create'),
    path('recu/<int:pk>/', views.payment_receipt, name='receipt'),
    path('depense/', views.expense_create, name='expense_create'),
    path('rapport/', views.finance_report, name='report'),
    path('eleve/<int:student_id>/carte/', views.student_finance_card, name='student_card'),
]
