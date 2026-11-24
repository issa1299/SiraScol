# -*- coding: utf-8 -*-
"""Tests de la gestion des candidats DEF / BAC."""
from datetime import date

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User

from academics.models import AcademicYear
from students.models import Student
from .models import Candidate, ExamSession


class ExamensTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='test_exam', password='x')
        cls.user.profile.role = 'directeur'
        cls.user.profile.save()
        cls.year = AcademicYear.objects.create(name='TEST-EXAM-2026', start_date=date(2026, 1, 1))
        cls.session = ExamSession.objects.create(
            type='def', academic_year=cls.year, date=date(2026, 6, 10), center='Centre Test'
        )
        cls.student = Student.objects.create(
            first_name='Candidat', last_name='Test', gender='M',
            date_of_birth=date(2012, 1, 1), enrollment_date=date.today(),
        )

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.user)

    def test_pages_load(self):
        for name in ('dashboard', 'candidate_list', 'session_create'):
            response = self.client.get(reverse('examens:' + name))
            self.assertEqual(response.status_code, 200, name)

    def test_candidate_registration_number_is_generated(self):
        candidate = Candidate.objects.create(student=self.student, session=self.session)
        self.assertTrue(candidate.registration_number.startswith('D2026'))
        self.assertEqual(len(candidate.registration_number), 9)

    def test_create_candidate_via_post(self):
        response = self.client.post(reverse('examens:candidate_create'), {
            'student': self.student.pk, 'session': self.session.pk,
            'series': '', 'exam_fee': '0',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Candidate.objects.count(), 1)

    def test_duplicate_candidate_not_created(self):
        Candidate.objects.create(student=self.student, session=self.session)
        self.client.post(reverse('examens:candidate_create'), {
            'student': self.student.pk, 'session': self.session.pk,
        })
        self.assertEqual(Candidate.objects.count(), 1)

    def test_exports(self):
        Candidate.objects.create(student=self.student, session=self.session)
        for fmt, magic in (('pdf', b'%PDF'), ('excel', b'PK')):
            response = self.client.get(reverse('examens:export') + f'?format={fmt}')
            self.assertEqual(response.status_code, 200, fmt)
            self.assertTrue(response.content.startswith(magic), fmt)
