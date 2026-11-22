# -*- coding: utf-8 -*-
"""Tests de sécurité et de configuration (régression)."""
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from core.validators import validate_upload


class UploadValidatorTests(TestCase):
    class _File:
        def __init__(self, name, size):
            self.name = name
            self.size = size

    def test_rejects_executable_extension(self):
        with self.assertRaises(ValidationError):
            validate_upload(self._File('evil.exe', 100))

    def test_rejects_oversized_file(self):
        with self.assertRaises(ValidationError):
            validate_upload(self._File('note.pdf', 11 * 1024 * 1024))

    def test_accepts_valid_pdf(self):
        self.assertEqual(validate_upload(self._File('note.pdf', 1024)).name, 'note.pdf')


class PermissionMatrixTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.parent = User.objects.create_user(username='test_parent', password='x')
        cls.parent.profile.role = 'parent'
        cls.parent.profile.save()
        cls.secretaire = User.objects.create_user(username='test_sec_user', password='x')
        cls.secretaire.profile.role = 'secretaire'
        cls.secretaire.profile.save()

    def test_parent_denied_global_settings_and_parent_directory(self):
        c = Client(); c.force_login(self.parent)
        for name in ('core:set_year', 'students:parent_list', 'students:cards_home',
                     'grades:saisie_classe', 'attendance:scan'):
            self.assertEqual(c.get(reverse(name)).status_code, 302, name)

    def test_secretary_allowed_parent_directory_but_not_finance(self):
        c = Client(); c.force_login(self.secretaire)
        self.assertEqual(c.get(reverse('students:parent_list')).status_code, 200)
        self.assertEqual(c.get(reverse('finance:classes')).status_code, 302)

    def test_logout_requires_post(self):
        c = Client(); c.force_login(self.parent)
        self.assertEqual(c.get(reverse('accounts:logout')).status_code, 405)
        self.assertEqual(c.post(reverse('accounts:logout')).status_code, 302)

    def test_shared_enrollment_stays_in_current_space(self):
        from datetime import date
        from students.models import Student
        from academics.models import AcademicYear, ClassRoom, Cycle, Level

        year = AcademicYear.objects.create(name='TEST-SPACE-2026')
        cycle = Cycle.objects.create(name='Test', code='test-space', order=99)
        level = Level.objects.create(name='Test', cycle=cycle, order=99)
        classroom = ClassRoom.objects.create(name='Test A', level=level, academic_year=year)
        student = Student.objects.create(
            first_name='Espace', last_name='Test', gender='M',
            date_of_birth=date(2012, 1, 1), enrollment_date=date.today(),
        )
        payload = {
            'student': student.pk,
            'classroom': classroom.pk,
            'academic_year': year.pk,
        }

        # Directeur : interface administration et retour vers son tableau de bord.
        directeur = User.objects.create_user(username='test_dir_space', password='x')
        directeur.profile.role = 'directeur'
        directeur.profile.save()
        c = Client(); c.force_login(directeur)
        response = c.get(reverse('students:enroll_existing'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf8')
        self.assertIn('Gestion des élèves', html)
        self.assertNotIn('Espace Secrétaire', html)
        response = c.post(reverse('students:enroll_existing'), payload)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/')

        # Secrétaire : interface secrétariat et retour vers ses inscriptions.
        c2 = Client(); c2.force_login(self.secretaire)
        response = c2.get(reverse('students:enroll_existing'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf8')
        self.assertIn('Secrétariat', html)
        response = c2.post(reverse('students:enroll_existing'), payload)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('secretariat:inscriptions'))

    def test_each_role_dashboard_stays_in_own_portal(self):
        expected = {
            'directeur': (200, None),
            'secretaire': (302, '/mon-espace-secretaire/'),
            'comptable': (302, '/mon-espace-comptable/'),
            'enseignant': (302, '/mon-espace-prof/'),
            'surveillant': (302, '/mon-espace-surveillant/'),
            'parent': (302, '/mon-espace-parent/'),
            'eleve': (302, '/mon-espace/'),
        }
        for role, (status, location) in expected.items():
            user = User.objects.create_user(username=f'space_{role}', password='x')
            user.profile.role = role
            user.profile.save()
            c = Client(); c.force_login(user)
            response = c.get('/')
            self.assertEqual(response.status_code, status, role)
            if location:
                self.assertEqual(response['Location'], location, role)

    def test_teacher_password_initial_requires_change(self):
        from core.account_sync import ensure_user_for_teacher
        from teachers.models import Teacher
        t = Teacher.objects.create(
            matricule='TEST-T-999', first_name='Test', last_name='Prof', gender='M',
        )
        from accounts.models import Profile
        user, _created, _ = ensure_user_for_teacher(t)
        self.assertIsNotNone(user)
        profile = Profile.objects.get(user=user)
        profile.refresh_from_db()
        self.assertTrue(profile.must_change_password)
