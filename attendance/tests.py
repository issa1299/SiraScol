# -*- coding: utf-8 -*-
"""Tests de la pointeuse QR et de ses modales."""
from datetime import date

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User

from attendance.models import AttendancePunch
from students.models import Student
from teachers.models import Teacher


class ScanQrTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='test_scan', password='x')
        cls.user.profile.role = 'directeur'
        cls.user.profile.save()
        cls.student = Student.objects.create(
            first_name='Scan', last_name='Test', gender='M',
            date_of_birth=date(2012, 1, 1), enrollment_date=date.today(),
        )

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.user)

    def test_scan_page_renders_professional_ui(self):
        response = self.client.get(reverse('attendance:scan'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf8')
        for marker in ('scan-frame', 'scan-result-tpl', 'siraScanManual',
                       'btn-start', 'scan-result-status'):
            self.assertIn(marker, html)

    def test_modal_endpoints(self):
        for name in ('scan_manual', 'scan_camera_help'):
            response = self.client.get(reverse('attendance:' + name))
            self.assertEqual(response.status_code, 200, name)

    def test_punch_detail_modal(self):
        punch = AttendancePunch.objects.create(
            kind='eleve', action='arrivee', student=self.student,
            date=date.today(), recorded_by=self.user,
        )
        response = self.client.get(
            reverse('attendance:scan_punch_detail', args=[punch.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('Scan Test', response.content.decode('utf8'))

        teacher = Teacher.objects.create(
            matricule='TEST-SCAN-T', first_name='Prof', last_name='Scan',
            gender='M', category='enseignant',
        )
        tpunch = AttendancePunch.objects.create(
            kind='personnel', action='arrivee', teacher=teacher,
            date=date.today(), recorded_by=self.user,
        )
        response = self.client.get(
            reverse('attendance:scan_punch_detail', args=[tpunch.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('Prof Scan', response.content.decode('utf8'))
