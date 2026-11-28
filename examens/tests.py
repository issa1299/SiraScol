# -*- coding: utf-8 -*-
"""Tests du module Examens nationaux : DEF (9ᵉ) et BAC (Terminale)."""
from datetime import date
from io import BytesIO

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from academics.models import AcademicYear, ClassRoom, Cycle, Level
from students.models import Enrollment, Student

from .models import Candidate, ExamSession


class ExamensTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='test_exam', password='x')
        cls.user.profile.role = 'directeur'
        cls.user.profile.save()
        cls.year = AcademicYear.objects.create(
            name='TEST-EXAM-2026', start_date=date(2026, 1, 1), is_current=True
        )
        cls.session_def = ExamSession.objects.create(
            type='def', academic_year=cls.year, date=date(2026, 6, 10), center='Centre Test'
        )
        cls.session_bac = ExamSession.objects.create(
            type='bac', academic_year=cls.year, date=date(2026, 6, 20), center='Centre Test'
        )
        cls.cycle = Cycle.objects.create(name='Lycée', code='lycee', order=3)
        cls.level9 = Level.objects.create(name='9ème', cycle=cls.cycle, order=9)
        cls.level12 = Level.objects.create(name='Terminale', cycle=cls.cycle, order=12)
        cls.class9 = ClassRoom.objects.create(name='9ème A TEST', level=cls.level9, academic_year=cls.year)
        cls.class12 = ClassRoom.objects.create(name='Terminale A TEST', level=cls.level12, academic_year=cls.year)
        cls.student9 = Student.objects.create(
            first_name='Neuf', last_name='Elève', gender='M',
            date_of_birth=date(2012, 1, 1), enrollment_date=date.today(),
        )
        cls.student12 = Student.objects.create(
            first_name='Terminal', last_name='Elève', gender='F',
            date_of_birth=date(2009, 1, 1), enrollment_date=date.today(),
        )
        Enrollment.objects.create(
            student=cls.student9, classroom=cls.class9, academic_year=cls.year,
            enrollment_date=date.today(),
        )
        Enrollment.objects.create(
            student=cls.student12, classroom=cls.class12, academic_year=cls.year,
            enrollment_date=date.today(),
        )

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.user)
        session = self.client.session
        session['selected_year_id'] = self.year.pk
        session.save()

    def test_menu_pages_load(self):
        for name in ('dashboard', 'sessions', 'candidats_def', 'candidats_bac',
                     'inscriptions', 'documents', 'lists_stats', 'transmission',
                     'results', 'session_create', 'excel_import'):
            response = self.client.get(reverse('examens:' + name))
            self.assertEqual(response.status_code, 200, name)

    def test_phase1_session_fields_and_status(self):
        response = self.client.post(reverse('examens:session_create'), {
            'type': 'bac',
            'academic_year': self.year.pk,
            'kind': 'Rattrapage spécial',
            'start_date': '10/06/2027',
            'end_date': '20/06/2027',
            'academy': 'Académie de Bamako',
            'center': 'Centre Test',
            'status': 'preparation',
        })
        self.assertEqual(response.status_code, 302)
        session = ExamSession.objects.get(kind='Rattrapage spécial')
        self.assertEqual(session.start_date, date(2027, 6, 10))
        self.assertEqual(session.end_date, date(2027, 6, 20))
        self.assertEqual(session.academy, 'Académie de Bamako')
        self.assertEqual(session.status, 'preparation')
        self.assertFalse(session.is_open)
        self.client.post(reverse('examens:session_status', args=[session.pk]),
                         {'status': 'ouverte'})
        session.refresh_from_db()
        self.assertEqual(session.status, 'ouverte')
        self.assertTrue(session.is_open)
        html = self.client.get(reverse('examens:sessions')).content.decode('utf8')
        self.assertIn('Académie de Bamako', html)
        self.assertIn('Rattrapage spécial', html)

    def test_single_sidebar_entry_for_exams(self):
        html = self.client.get(reverse('examens:dashboard')).content.decode('utf8')
        # Une seule entrée « Examens nationaux » dans la barre latérale, et les
        # rubriques ne subsistent que dans les onglets internes du module.
        self.assertEqual(html.count('Candidats DEF (9ᵉ année)'), 1)
        self.assertEqual(html.count('Candidats BAC (12ᵉ année)'), 1)
        self.assertIn('Examens nationaux', html)

    def test_candidate_number_generation(self):
        d = Candidate.objects.create(student=self.student9, session=self.session_def)
        b = Candidate.objects.create(student=self.student12, session=self.session_bac)
        self.assertTrue(d.registration_number.startswith('D2026'))
        self.assertTrue(b.registration_number.startswith('B2026'))

    def test_registration_status_and_filters(self):
        c = Candidate.objects.create(student=self.student9, session=self.session_def,
                                     registration_status='a_verifier')
        response = self.client.get(reverse('examens:candidats_def') + '?registration_status=a_verifier')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, c.registration_number)
        response = self.client.get(reverse('examens:candidats_def') + '?q=Elève')
        self.assertContains(response, c.registration_number)

    def test_create_external_candidate(self):
        response = self.client.post(reverse('examens:candidate_create'), {
            'session': self.session_def.pk,
            'is_external': 'on',
            'external_last_name': 'Externe', 'external_first_name': 'Candidat',
            'external_gender': 'M', 'external_date_of_birth': '12/02/2010',
            'registration_status': 'brouillon',
        })
        self.assertEqual(response.status_code, 302)
        c = Candidate.objects.get(is_external=True)
        self.assertEqual(c.candidate_name, 'Externe Candidat')
        self.assertTrue(c.external_matricule.startswith('EXT2026'))
        self.assertEqual(c.candidate_birth_date, date(2010, 2, 12))

    def test_official_number_director_only_and_search(self):
        response = self.client.post(reverse('examens:candidate_create'), {
            'session': self.session_def.pk, 'student': self.student9.pk,
            'candidate_kind': 'regulier', 'official_number': 'PLACE-001',
            'registration_status': 'a_verifier',
        })
        self.assertEqual(response.status_code, 302)
        candidate = Candidate.objects.get(student=self.student9)
        self.assertEqual(candidate.official_number, 'PLACE-001')
        self.assertEqual(candidate.candidate_kind, 'regulier')
        html = self.client.get(
            reverse('examens:candidats_def') + '?q=PLACE-001'
        ).content.decode('utf8')
        self.assertIn(candidate.candidate_name, html)
        # Un numéro officiel en doublon est refusé.
        response = self.client.post(reverse('examens:candidate_create'), {
            'session': self.session_def.pk, 'student': self.student12.pk,
            'candidate_kind': 'regulier', 'official_number': 'PLACE-001',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Candidate.objects.filter(student=self.student12).exists())

    def test_secretary_cannot_set_official_number(self):
        secretary = User.objects.create_user(username='exam_sec', password='x')
        secretary.profile.role = 'secretaire'
        secretary.profile.save()
        client = Client()
        client.force_login(secretary)
        form = client.get(reverse('examens:candidate_create')).context['form']
        self.assertTrue(form.fields['official_number'].disabled)
        response = client.post(reverse('examens:candidate_create'), {
            'session': self.session_def.pk, 'student': self.student9.pk,
            'candidate_kind': 'regulier', 'official_number': 'FAKE-001',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Candidate.objects.get(student=self.student9).official_number, '')

    def test_candidate_kind_rules(self):
        # Un candidat libre ne peut pas être un élève de l'établissement.
        response = self.client.post(reverse('examens:candidate_create'), {
            'session': self.session_def.pk, 'student': self.student9.pk,
            'candidate_kind': 'libre',
            'external_last_name': 'Libre', 'external_first_name': 'Faux',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Candidate.objects.filter(student=self.student9).exists())
        # Un candidat externe doit être déclaré comme libre.
        response = self.client.post(reverse('examens:candidate_create'), {
            'session': self.session_def.pk, 'is_external': 'on',
            'candidate_kind': 'regulier',
            'external_last_name': 'Externe', 'external_first_name': 'Régulier',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Candidate.objects.exists())

    def test_import_uses_class_series_and_session_academy(self):
        self.class9.serie = 'Littéraire'
        self.class9.save()
        self.session_def.academy = 'Académie Test'
        self.session_def.save()
        response = self.client.post(reverse('examens:import_confirm'), {
            'session': self.session_def.pk, 'students': [self.student9.pk],
        })
        self.assertEqual(response.status_code, 302)
        candidate = Candidate.objects.get(student=self.student9)
        self.assertEqual(candidate.series, 'Littéraire')
        self.assertEqual(candidate.academy, 'Académie Test')
        self.assertEqual(candidate.candidate_kind, 'regulier')

    def test_import_from_class_9_and_terminale(self):
        for section, expected in (('candidats_def', 'Neuf'), ('candidats_bac', 'Terminal')):
            response = self.client.get(reverse('examens:import_from_class') + '?section=' + section)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, expected)
        response = self.client.post(reverse('examens:import_confirm'), {
            'session': self.session_def.pk, 'students': [self.student9.pk],
        })
        self.assertEqual(response.status_code, 302)
        c = Candidate.objects.get(student=self.student9)
        self.assertEqual(c.registration_status, 'a_verifier')
        self.assertEqual(c.classroom, self.class9)

    def test_documents_page_and_fiche_pdf(self):
        c = Candidate.objects.create(student=self.student9, session=self.session_def)
        response = self.client.get(reverse('examens:documents'))
        self.assertContains(response, c.registration_number)
        response = self.client.get(reverse('examens:candidate_fiche_pdf', args=[c.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b'%PDF'))

    def test_excel_import(self):
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.append(['Matricule', 'Nom', 'Prénom', 'Sexe', 'Date', 'Lieu', 'Établissement',
                   'Parent', 'Téléphone'])
        ws.append([self.student9.matricule, 'Elève', 'Neuf', 'M', '', '', '', '', ''])
        ws.append(['', 'Externe', 'Importé', 'F', '', '', '', '', ''])
        buf = BytesIO()
        wb.save(buf)
        buf.seek(0)
        upload = SimpleUploadedFile('import.xlsx', buf.getvalue(),
                                    content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response = self.client.post(reverse('examens:excel_import'), {
            'session': self.session_def.pk, 'file': upload,
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Candidate.objects.count(), 2)

    def test_exports(self):
        Candidate.objects.create(student=self.student9, session=self.session_def)
        for fmt, magic in (('pdf', b'%PDF'), ('excel', b'PK')):
            response = self.client.get(reverse('examens:export') + f'?format={fmt}')
            self.assertEqual(response.status_code, 200, fmt)
            self.assertTrue(response.content.startswith(magic), fmt)

    def test_role_access(self):
        other = User.objects.create_user(username='test_parent', password='x')
        other.profile.role = 'parent'
        other.profile.save()
        client = Client()
        client.force_login(other)
        response = client.get(reverse('examens:candidats_def'))
        self.assertEqual(response.status_code, 302)
