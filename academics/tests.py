# -*- coding: utf-8 -*-
"""Tests de la fenêtre « Sélectionner les classes » (Gestion des Classes)."""
from datetime import date

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from students.models import Enrollment, Student

from .models import AcademicYear, ClassRoom, Cycle, Level


class ClassroomBulkTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='acad_test', password='x')
        cls.user.profile.role = 'directeur'
        cls.user.profile.save()
        cls.year = AcademicYear.objects.create(
            name='TEST-CLASSES-2026', start_date=date(2026, 1, 1), is_current=True
        )
        cls.cycle = Cycle.objects.create(name='Lycée TEST', code='lycee', order=3)
        cls.level10 = Level.objects.create(name='10ème année', cycle=cls.cycle, order=1)
        cls.level11 = Level.objects.create(name='11ème année', cycle=cls.cycle, order=2)
        cls.level12 = Level.objects.create(name='12ème année', cycle=cls.cycle, order=3)
        # Classes du 1er cycle déjà présentes : elles doivent rester intactes.
        cls.existing = ClassRoom.objects.create(
            name='9ème A', level=cls.level12, academic_year=cls.year
        )

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.user)

    def test_window_still_lists_first_and_second_cycles(self):
        response = self.client.get(reverse('academics:classroom_bulk'))
        self.assertEqual(response.status_code, 200)
        for label in ('1er cycle', '2ème cycle', 'Lycée', '9ème A', 'Tout sélectionner'):
            self.assertContains(response, label)

    def test_window_lists_all_requested_lycee_classes(self):
        response = self.client.get(reverse('academics:classroom_bulk'))
        self.assertEqual(response.status_code, 200)
        expected = [
            '10ᵉ ANNÉE', '10ème Commune',
            '11ᵉ ANNÉE', '11ème L', '11ème SES', '11ème S',
            'TERMINALE (12ᵉ ANNÉE)', 'TLL', 'TAL', 'TSS', 'TSEco', 'TSExp', 'TSE',
            'FILIÈRES TECHNIQUES — STI',
            'GM', 'GC', 'GMI', 'GELN', 'GEN', 'GEL',
            'FILIÈRES TECHNIQUES — STG', 'CF', 'GCO',
            'Classes parallèles',
        ]
        for label in expected:
            self.assertContains(response, label, msg_prefix=label)
        # Un « Tout sélectionner » par groupe lycée (10ᵉ, 11ᵉ, Terminale, STI, STG).
        self.assertContains(response, 'data-section="lycee-sti"')
        self.assertContains(response, 'data-section="lycee-stg"')

    def test_create_parallel_classes_and_avoid_duplicates(self):
        data = {
            'classes': ['12ème année|TLL|Littéraire · TLL'],
            'parallel': 'A, B, C',
            'capacity': '35', 'inscription_fee': '0', 'tuition_fee': '0',
        }
        response = self.client.post(reverse('academics:classroom_bulk'), data)
        self.assertEqual(response.status_code, 302)
        created = list(ClassRoom.objects.filter(name__startswith='TLL').order_by('name'))
        self.assertEqual([c.name for c in created], ['TLL A', 'TLL B', 'TLL C'])
        self.assertTrue(all(c.level == self.level12 for c in created))
        self.assertTrue(all(c.serie == 'Littéraire · TLL' for c in created))
        self.assertTrue(all(c.capacity == 35 for c in created))
        # Deuxième envoi identique : aucun doublon.
        self.client.post(reverse('academics:classroom_bulk'), data)
        self.assertEqual(ClassRoom.objects.filter(name__startswith='TLL').count(), 3)

    def test_technical_series_and_specialities(self):
        response = self.client.post(reverse('academics:classroom_bulk'), {
            'classes': [
                '12ème année|TSTI GM|STI · GM',
                '12ème année|TSTG CF|STG · CF',
            ],
            'parallel': 'A',
            'capacity': '40', 'inscription_fee': '0', 'tuition_fee': '0',
        })
        self.assertEqual(response.status_code, 302)
        sti = ClassRoom.objects.get(name='TSTI GM A')
        stg = ClassRoom.objects.get(name='TSTG CF A')
        self.assertEqual((sti.level, sti.serie), (self.level12, 'STI · GM'))
        self.assertEqual((stg.level, stg.serie), (self.level12, 'STG · CF'))

    def test_existing_classes_are_preserved_and_marked(self):
        response = self.client.get(reverse('academics:classroom_bulk'))
        self.assertContains(response, 'disabled')  # cases des classes déjà créées
        before = ClassRoom.objects.get(pk=self.existing.pk)
        self.client.post(reverse('academics:classroom_bulk'), {
            'classes': ['10ème année|10ème Commune|Tronc commun'], 'parallel': 'A',
        })
        after = ClassRoom.objects.get(pk=self.existing.pk)
        self.assertEqual((before.name, before.level_id, before.serie),
                         (after.name, after.level_id, after.serie))
        self.assertTrue(ClassRoom.objects.filter(name='10ème Commune A', level=self.level10).exists())

    def test_created_classes_are_usable_for_enrollment_and_appear_in_list(self):
        self.client.post(reverse('academics:classroom_bulk'), {
            'classes': ['11ème année|11ème S|Scientifique'], 'parallel': 'A',
        })
        classroom = ClassRoom.objects.get(name='11ème S A')
        student = Student.objects.create(
            first_name='Élève', last_name='Test', gender='M',
            date_of_birth=date(2010, 1, 1), enrollment_date=date.today(),
        )
        Enrollment.objects.create(
            student=student, classroom=classroom, academic_year=self.year,
            enrollment_date=date.today(),
        )
        self.assertEqual(classroom.enrollments.filter(is_active=True).count(), 1)
        listing = self.client.get(reverse('academics:classroom_list'))
        self.assertEqual(listing.status_code, 200)
        self.assertContains(listing, '11ème S A')

    def test_terminale_level_resolution_and_empty_parallel(self):
        self.client.post(reverse('academics:classroom_bulk'), {
            'classes': ['Terminale|TSE|Scientifique · TSE'], 'parallel': '',
        })
        c = ClassRoom.objects.get(name='TSE')
        self.assertEqual(c.level, self.level12)
