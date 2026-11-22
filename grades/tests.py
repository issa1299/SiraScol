# -*- coding: utf-8 -*-
"""Tests des calculs de notes et de moyennes."""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from academics.models import AcademicYear, ClassRoom, ClassSubject, Cycle, Level, Subject
from grades.bulletin_views import _subject_coefficient
from grades.views import _bound_score
from students.models import Enrollment, Student


class GradeCalculationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.year = AcademicYear.objects.create(name='TEST-GRADE-2026')
        cycle = Cycle.objects.create(name='Test', code='test-grade', order=98)
        level = Level.objects.create(name='Test', cycle=cycle, order=98)
        cls.classroom = ClassRoom.objects.create(
            name='Grade A', level=level, academic_year=cls.year
        )
        cls.student = Student.objects.create(
            first_name='Note', last_name='Test', gender='M',
            date_of_birth=date(2012, 1, 1), enrollment_date=date.today(),
        )
        Enrollment.objects.create(
            student=cls.student, classroom=cls.classroom,
            academic_year=cls.year, enrollment_date=date.today(),
        )
        cls.subject = Subject.objects.create(
            name='Maths Test', code='MATH-TEST', coefficient=Decimal('2')
        )

    def test_class_coefficient_overrides_subject_coefficient(self):
        ClassSubject.objects.create(
            classroom=self.classroom, subject=self.subject, coefficient=Decimal('5')
        )
        result = _subject_coefficient(self.subject, self.student, self.year)
        self.assertEqual(result, Decimal('5'))

    def test_fallback_to_subject_coefficient(self):
        result = _subject_coefficient(self.subject, self.student, self.year)
        self.assertEqual(result, Decimal('2'))

    def test_score_is_bounded_between_zero_and_max(self):
        self.assertEqual(_bound_score(Decimal('-5'), Decimal('20')), Decimal('0'))
        self.assertEqual(_bound_score(Decimal('25'), Decimal('20')), Decimal('20'))
        self.assertEqual(_bound_score(Decimal('12.5'), Decimal('20')), Decimal('12.5'))
