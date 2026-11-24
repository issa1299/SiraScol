# -*- coding: utf-8 -*-
"""Tests des formulaires personnel et des matricules."""
from datetime import date

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User

from teachers.models import Teacher
from teachers.views import _next_matricule, prefix_for_category


class PersonnelFormTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='test_hr', password='x')
        cls.user.profile.role = 'directeur'
        cls.user.profile.save()

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.user)

    def test_prefix_depends_on_category(self):
        self.assertEqual(prefix_for_category('enseignant'), 'ENS')
        self.assertEqual(prefix_for_category('admin'), 'ADM')
        self.assertEqual(prefix_for_category('service'), 'SRV')
        self.assertEqual(prefix_for_category('autre'), 'PER')

    def test_matricule_sequence_numeric_not_lexicographic(self):
        year = date.today().year
        Teacher.objects.create(
            matricule=f'ENS-{year}-0999', first_name='A', last_name='B',
            gender='M', category='enseignant',
        )
        self.assertEqual(_next_matricule('ENS'), f'ENS-{year}-1000')

    def test_two_forms_render(self):
        for value, marker in (
            ('1', 'Ajout avec compte de connexion'),
            ('0', 'Ajout sans compte de connexion'),
        ):
            response = self.client.get(reverse('teachers:create') + f'?with_account={value}')
            self.assertEqual(response.status_code, 200)
            html = response.content.decode('utf8')
            self.assertIn(marker, html)
            self.assertIn('teacher-form-modal', html)

    def test_with_account_creates_user(self):
        payload = {
            'with_account': '1', 'matricule': f'ADM-{date.today().year}-9001',
            'last_name': 'Comptable', 'first_name': 'Nouveau', 'gender': 'M',
            'category': 'admin', 'function': 'Comptable',
            'email': 'nouveau@example.com', 'base_salary': '0',
            'status': 'actif', 'hire_date': date.today().isoformat(),
        }
        response = self.client.post(reverse('teachers:create') + '?with_account=1', payload)
        self.assertEqual(response.status_code, 302)
        teacher = Teacher.objects.get(matricule=payload['matricule'])
        self.assertIsNotNone(teacher.user_id)

    def test_without_account_does_not_create_user(self):
        payload = {
            'with_account': '0', 'matricule': f'SRV-{date.today().year}-9002',
            'last_name': 'Gardien', 'first_name': 'Nouveau', 'gender': 'M',
            'category': 'service', 'function': 'Gardien',
            'base_salary': '0', 'status': 'actif',
            'hire_date': date.today().isoformat(),
        }
        response = self.client.post(reverse('teachers:create') + '?with_account=0', payload)
        self.assertEqual(response.status_code, 302)
        teacher = Teacher.objects.get(matricule=payload['matricule'])
        self.assertIsNone(teacher.user_id)

    def test_wrong_prefix_matricule_is_corrected(self):
        payload = {
            'with_account': '0', 'matricule': 'ENS-2000-7777',
            'last_name': 'Comptable', 'first_name': 'Corrige', 'gender': 'M',
            'category': 'admin', 'function': 'Secrétaire',
            'base_salary': '0', 'status': 'actif',
            'hire_date': date.today().isoformat(),
        }
        self.client.post(reverse('teachers:create') + '?with_account=0', payload)
        teacher = Teacher.objects.get(first_name='Corrige')
        self.assertTrue(teacher.matricule.startswith('ADM-'))
