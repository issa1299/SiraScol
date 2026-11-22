# -*- coding: utf-8 -*-
"""Tests financiers : cohérence des soldes et validation des paiements."""
from datetime import date
from decimal import Decimal

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User

from academics.models import AcademicYear
from finance.models import FeeType, Invoice, Payment
from students.models import Student


class FinanceFunctionalTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='test_fin', password='x')
        cls.user.profile.role = 'comptable'
        cls.user.profile.save()
        cls.year = AcademicYear.objects.create(name='TEST-FIN-2026')
        cls.student = Student.objects.create(
            first_name='Finance', last_name='Test', gender='M',
            date_of_birth=date(2012, 1, 1), enrollment_date=date.today(),
        )
        cls.fee = FeeType.objects.create(name='TEST Scolarité', default_amount=100000)
        cls.invoice = Invoice.objects.create(
            student=cls.student, academic_year=cls.year, fee_type=cls.fee,
            amount=Decimal('100000'), due_date=date.today(), status='en_attente',
        )

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.user)

    def test_cancelled_payment_excluded_from_balance(self):
        Payment.objects.create(
            invoice=self.invoice, amount=Decimal('40000'),
            payment_date=date.today(), method='especes',
        )
        cancelled = Payment.objects.create(
            invoice=self.invoice, amount=Decimal('30000'),
            payment_date=date.today(), method='especes',
        )
        Payment.objects.filter(pk=cancelled.pk).update(is_cancelled=True)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.amount_paid, Decimal('40000'))
        self.assertEqual(self.invoice.balance, Decimal('60000'))

    def test_payment_create_rejects_negative_amount(self):
        response = self.client.post(reverse('finance:payment_create'), {
            'invoice': self.invoice.pk, 'amount': '-50',
            'payment_date': date.today().isoformat(), 'method': 'especes',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Payment.objects.count(), 0)

    def test_payment_create_rejects_amount_above_balance(self):
        response = self.client.post(reverse('finance:payment_create'), {
            'invoice': self.invoice.pk, 'amount': '150000',
            'payment_date': date.today().isoformat(), 'method': 'especes',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Payment.objects.count(), 0)

    def test_payment_create_accepts_valid_amount(self):
        response = self.client.post(reverse('finance:payment_create'), {
            'invoice': self.invoice.pk, 'amount': '25000',
            'payment_date': date.today().isoformat(), 'method': 'especes',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Payment.objects.count(), 1)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, 'partiel')
