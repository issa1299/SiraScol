# -*- coding: utf-8 -*-
"""Tests du passage en classe supérieure / orientation du lycée."""
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from academics.models import AcademicYear, ClassRoom, Cycle, Level

from .models import Enrollment, PromotionDecision, PromotionOperation, Student
from . import orientation_rules


class OrientationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.director = User.objects.create_user(username='ori_dir', password='x')
        cls.director.profile.role = 'directeur'
        cls.director.profile.save()
        cls.secretary = User.objects.create_user(username='ori_sec', password='x')
        cls.secretary.profile.role = 'secretaire'
        cls.secretary.profile.save()

        cls.source = AcademicYear.objects.create(
            name='ORI-2026-2027', start_date=date(2026, 9, 1), is_current=True
        )
        cls.target = AcademicYear.objects.create(
            name='ORI-2027-2028', start_date=date(2027, 9, 1)
        )
        cls.cycle = Cycle.objects.create(name='Lycée ORI', code='lycee', order=3)
        cls.l10 = Level.objects.create(name='10ème année', cycle=cls.cycle, order=1)
        cls.l11 = Level.objects.create(name='11ème année', cycle=cls.cycle, order=2)
        cls.l12 = Level.objects.create(name='12ème année', cycle=cls.cycle, order=3)

        def room(name, level, year):
            return ClassRoom.objects.create(name=name, level=level, academic_year=year)

        cls.c10 = room('10ème Commune A', cls.l10, cls.source)
        cls.c11l = room('11ème L A', cls.l11, cls.source)
        cls.t11l_a = room('11ème L A', cls.l11, cls.target)
        cls.t11l_b = room('11ème L B', cls.l11, cls.target)
        cls.t11ses = room('11ème SES A', cls.l11, cls.target)
        cls.t11s = room('11ème S A', cls.l11, cls.target)
        cls.tll = room('TLL A', cls.l12, cls.target)
        cls.tal = room('TAL A', cls.l12, cls.target)
        cls.tss = room('TSS A', cls.l12, cls.target)
        cls.tseco = room('TSEco A', cls.l12, cls.target)
        cls.tsexp = room('TSExp A', cls.l12, cls.target)
        cls.tse = room('TSE A', cls.l12, cls.target)

        cls.student10 = cls._student('Dix', 'Élève', cls.c10)
        cls.student11 = cls._student('Onze', 'Élève', cls.c11l)
        cls.student11b = cls._student('OnzeB', 'Élève', cls.c11l)

    @classmethod
    def _student(cls, last, first, classroom):
        student = Student.objects.create(
            last_name=last, first_name=first, gender='M',
            date_of_birth=date(2010, 1, 1), enrollment_date=date.today(),
        )
        Enrollment.objects.create(
            student=student, classroom=classroom, academic_year=cls.source,
            enrollment_date=date.today(),
        )
        return student

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.director)
        session = self.client.session
        session['selected_academic_year_id'] = self.source.pk
        session.save()

    def _decision(self, student, decision, target, client=None):
        client = client or self.client
        enrollment = Enrollment.objects.get(student=student, academic_year=self.source)
        return client.post(reverse('students:orientation_class', args=[self.c11l.pk]), {
            f'select_{enrollment.pk}': 'on',
            f'decision_{enrollment.pk}': decision,
            f'target_{enrollment.pk}': target.pk if target else '',
            f'avg_{enrollment.pk}': '12,5',
            f'note_{enrollment.pk}': 'Décision en conseil',
            'action': 'save',
        })

    def test_rules_allow_only_official_destinations(self):
        self.assertEqual(
            {r.name for r in orientation_rules.destination_classrooms(self.c10, self.target)},
            {'11ème L A', '11ème L B', '11ème SES A', '11ème S A'},
        )
        self.assertEqual(
            {r.name for r in orientation_rules.destination_classrooms(self.c11l, self.target)},
            {'TLL A', 'TAL A'},
        )
        self.assertEqual(
            {r.name for r in orientation_rules.destination_classrooms(
                ClassRoom(name='11ème SES C'), self.target
            )},
            {'TSS A', 'TSEco A'},
        )
        self.assertEqual(
            {r.name for r in orientation_rules.destination_classrooms(
                ClassRoom(name='11ème S B'), self.target
            )},
            {'TSExp A', 'TSE A'},
        )
        self.assertEqual(orientation_rules.destination_classrooms(
            ClassRoom(name='9ème A'), self.target
        ), [])

    def test_pages_and_tab(self):
        # L'entrée est un onglet de « Passage / Redoublement », pas un bouton
        # dans Gestion des Classes.
        response = self.client.get(reverse('students:promotion_home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Passage en classe supérieure')

        response = self.client.get(reverse('students:promotion_home'), {'tab': 'orientation'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '11ème L A')
        self.assertContains(response, '10ème Commune A')

        response = self.client.get(reverse('students:orientation_home'))
        self.assertRedirects(
            response,
            reverse('students:promotion_home') + '?tab=orientation',
        )

        response = self.client.get(reverse('academics:classroom_list'))
        self.assertNotContains(response, 'Passage en classe supérieure')

        response = self.client.get(reverse('students:orientation_class', args=[self.c11l.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'TLL A')
        self.assertContains(response, 'TAL A')
        self.assertNotContains(response, '>TSE A<')

    def test_draft_correction_keeps_revisions(self):
        self._decision(self.student11, 'promoted', self.tll)
        first = PromotionDecision.objects.get(is_current=True, enrollment__student=self.student11)
        self.assertEqual(first.revision, 1)
        self.assertEqual(first.average, Decimal('12.50'))
        self._decision(self.student11, 'repeated', self.t11l_a)
        second = PromotionDecision.objects.get(is_current=True, enrollment__student=self.student11)
        self.assertEqual(second.revision, 2)
        self.assertEqual(second.decision, 'repeated')
        self.assertFalse(PromotionDecision.objects.filter(pk=first.pk).get().is_current)
        operation = PromotionOperation.objects.get(source_classroom=self.c11l)
        self.assertEqual(operation.status, 'brouillon')

    def test_forged_destination_rejected(self):
        response = self._decision(self.student11b, 'promoted', self.tse)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(PromotionDecision.objects.filter(
            enrollment__student=self.student11b
        ).exists())

    def test_director_validation_creates_enrollment_and_preserves_history(self):
        self._decision(self.student11, 'promoted', self.tll)
        operation = PromotionOperation.objects.get(source_classroom=self.c11l)
        response = self.client.post(reverse('students:orientation_validate', args=[operation.pk]))
        self.assertEqual(response.status_code, 302)
        operation.refresh_from_db()
        self.assertEqual(operation.status, 'valide')
        self.assertEqual(operation.validated_by, self.director)
        self.assertIsNotNone(operation.validated_at)

        old = Enrollment.objects.get(student=self.student11, academic_year=self.source)
        self.assertEqual(old.classroom, self.c11l)  # ancienne inscription conservée
        self.assertEqual(old.end_status, 'promoted')
        new = Enrollment.objects.get(student=self.student11, academic_year=self.target)
        self.assertEqual(new.classroom, self.tll)

        # Idempotence : une seconde validation ne recrée rien.
        self.client.post(reverse('students:orientation_validate', args=[operation.pk]))
        self.assertEqual(Enrollment.objects.filter(
            student=self.student11, academic_year=self.target
        ).count(), 1)
        summary = self.client.get(reverse('students:orientation_summary', args=[operation.pk]))
        self.assertEqual(summary.status_code, 200)
        self.assertContains(summary, 'verrouillée')

    def test_secretary_prepares_but_cannot_validate(self):
        secretary = Client()
        secretary.force_login(self.secretary)
        self._decision(self.student11, 'promoted', self.tll, client=secretary)
        self.assertTrue(PromotionDecision.objects.filter(
            enrollment__student=self.student11
        ).exists())
        operation = PromotionOperation.objects.get(source_classroom=self.c11l)
        response = secretary.post(reverse('students:orientation_validate', args=[operation.pk]))
        self.assertEqual(response.status_code, 302)
        operation.refresh_from_db()
        self.assertNotEqual(operation.status, 'valide')

    def test_average_never_orients_automatically(self):
        response = self.client.post(
            reverse('students:promotion_auto', args=[self.c11l.pk])
        )
        self.assertEqual(response.status_code, 302)
        enrollment = Enrollment.objects.get(student=self.student11, academic_year=self.source)
        self.assertEqual(enrollment.end_status, 'en_cours')
        self.assertFalse(PromotionDecision.objects.exists())

    def test_duplicate_target_enrollment_is_skipped(self):
        Enrollment.objects.create(
            student=self.student11, classroom=self.tal, academic_year=self.target,
            enrollment_date=date.today(),
        )
        self._decision(self.student11, 'promoted', self.tll)
        operation = PromotionOperation.objects.get(source_classroom=self.c11l)
        response = self.client.post(reverse('students:orientation_validate', args=[operation.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Enrollment.objects.filter(
            student=self.student11, academic_year=self.target
        ).count(), 1)
        operation.refresh_from_db()
        self.assertEqual(operation.status, 'valide')
