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
