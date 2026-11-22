# -*- coding: utf-8 -*-
"""Tests de l'espace Surveillant (pointage, unicité, traçabilité)."""
from datetime import date

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User

from academics.models import AcademicYear, ClassRoom, Cycle, Level
from students.models import Student, Enrollment
from surveillant.models import PresenceRecord, PresenceChange


class SurveillantPointageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='test_surv', password='x')
        cls.user.profile.role = 'surveillant'
        cls.user.profile.save()
        year = AcademicYear.objects.create(name='TEST-2026', start_date=date(2026, 1, 1))
        cycle = Cycle.objects.create(name='Test', code='test', order=1)
        level = Level.objects.create(name='Test', cycle=cycle, order=1)
        cls.cls = ClassRoom.objects.create(name='Test A', level=level, academic_year=year)
        cls.students = []
        for i in range(2):
            s = Student.objects.create(
                first_name='Eleve', last_name=f'Test{i}', gender='M',
                date_of_birth=date(2012, 1, 1),
                enrollment_date=date(2026, 1, 1),
            )
            Enrollment.objects.create(
                student=s, classroom=cls.cls, academic_year=year,
                enrollment_date=date(2026, 1, 1),
            )
            cls.students.append(s)

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.user)

    def test_all_portal_pages_load(self):
        for name in ('dashboard', 'pointage', 'presences', 'absences', 'retards',
                     'discipline', 'sorties', 'historique', 'rapports',
                     'notifications', 'profil'):
            response = self.client.get(reverse('surveillant:' + name))
            self.assertEqual(response.status_code, 200, name)

    def test_pointage_no_duplicate_on_second_validation(self):
        payload = {'classroom': str(self.cls.pk), 'date': '2026-11-22', 'period': 'journee'}
        for s in self.students:
            payload[f'status_{s.pk}'] = 'present'
        self.client.post(reverse('surveillant:pointage'), payload)
        first = PresenceRecord.objects.filter(date='2026-11-22').count()
        self.client.post(reverse('surveillant:pointage'), payload)
        second = PresenceRecord.objects.filter(date='2026-11-22').count()
        self.assertEqual(first, len(self.students))
        self.assertEqual(second, first)

    def test_presence_edit_is_traced(self):
        rec = PresenceRecord.objects.create(
            student=self.students[0], classroom=self.cls,
            date=date(2026, 11, 22), status='present',
        )
        self.client.post(
            reverse('surveillant:presence_edit', args=[rec.pk]),
            {'status': 'absent', 'reason': 'malade', 'note': 'test'},
        )
        rec.refresh_from_db()
        self.assertEqual(rec.status, 'absent')
        self.assertEqual(rec.changes.count(), 1)
        change = rec.changes.first()
        self.assertEqual(change.old_status, 'present')
        self.assertEqual(change.new_status, 'absent')
