# -*- coding: utf-8 -*-
"""Formulaires du module Examens nationaux."""
from decimal import Decimal, InvalidOperation

from django import forms

from core.permissions import get_role
from core.widgets import SmartDateInput
from students.models import Student

from .models import Candidate, ExamSession


class SessionForm(forms.ModelForm):
    """Création / modification d'une session DEF ou BAC."""

    class Meta:
        model = ExamSession
        fields = ['type', 'academic_year', 'kind', 'start_date', 'end_date',
                  'academy', 'center', 'status']
        widgets = {
            'start_date': SmartDateInput(),
            'end_date': SmartDateInput(),
            'academy': forms.TextInput(attrs={'placeholder': 'Académie d’enseignement'}),
            'center': forms.TextInput(attrs={'placeholder': 'Centre d’examen'}),
            'kind': forms.TextInput(attrs={'placeholder': 'ex. normale, rattrapage'}),
        }
        labels = {
            'kind': 'Type de session',
            'academy': 'Académie d’enseignement',
            'status': 'Statut de la session',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            current = field.widget.attrs.get('class', '')
            if 'smart-date-text' not in current:
                field.widget.attrs['class'] = (current + ' form-input').strip()

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get('start_date'), cleaned.get('end_date')
        if start and end and end < start:
            self.add_error('end_date', 'La date de fin doit être postérieure au début.')
        return cleaned


class CandidateForm(forms.ModelForm):
    """Inscription / modification d'un candidat DEF ou BAC (élève ou externe)."""

    class Meta:
        model = Candidate
        fields = [
            'session', 'student', 'is_external', 'candidate_kind',
            'official_number', 'academy',
            'external_matricule', 'external_last_name', 'external_first_name',
            'external_gender', 'external_date_of_birth',
            'birth_place', 'school_name', 'parent_name', 'parent_phone',
            'photo', 'birth_certificate', 'other_document',
            'registration_status', 'exam_center',
            'series', 'speciality', 'terminale_class', 'living_language',
            'subjects_options', 'exam_fee', 'fee_paid', 'notes', 'status',
        ]
        widgets = {
            'external_date_of_birth': SmartDateInput(),
            'notes': forms.Textarea(attrs={'rows': 3}),
            'subjects_options': forms.Textarea(attrs={'rows': 3}),
        }
        labels = {
            'session': 'Session d’examen',
            'student': 'Élève de l’établissement',
            'is_external': 'Candidat externe (hors établissement)',
            'candidate_kind': 'Type de candidature',
            'official_number': 'Numéro officiel de place (attribué par l’administration)',
            'academy': 'Académie d’enseignement',
            'registration_status': 'Statut d’inscription',
            'status': 'Résultat / présence',
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        role = get_role(self.user)
        if role not in ('directeur', 'admin'):
            # Le numéro officiel est attribué par l'administration compétente :
            # le secrétariat ne peut ni l'inventer ni le modifier.
            self.fields['official_number'].disabled = True
        self.fields['student'].required = False
        self.fields['student'].queryset = Student.objects.filter(status='actif').order_by(
            'last_name', 'first_name'
        )
        for name in ('external_matricule', 'external_last_name', 'external_first_name',
                     'external_gender', 'external_date_of_birth', 'birth_place', 'school_name',
                     'parent_name', 'parent_phone', 'photo', 'birth_certificate',
                     'other_document', 'series', 'speciality', 'terminale_class',
                     'living_language', 'subjects_options', 'notes', 'academy',
                     'candidate_kind', 'official_number', 'exam_fee', 'fee_paid',
                     'registration_status', 'status'):
            self.fields[name].required = False
        for name, cls in self.fields.items():
            current = cls.widget.attrs.get('class', '')
            if 'smart-date-text' not in current:
                cls.widget.attrs['class'] = (current + ' form-input').strip()

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get('status'):
            cleaned['status'] = 'inscrit'
        if not cleaned.get('registration_status'):
            cleaned['registration_status'] = 'brouillon'
        if cleaned.get('exam_fee') in (None, ''):
            cleaned['exam_fee'] = Decimal('0')
        kind = cleaned.get('candidate_kind')
        if not kind:
            kind = 'libre' if cleaned.get('is_external') else 'regulier'
            cleaned['candidate_kind'] = kind

        if kind == 'libre':
            # Un candidat libre est un dossier spécifique : jamais un élève régulier.
            if cleaned.get('student') or not cleaned.get('is_external'):
                self.add_error(
                    'candidate_kind',
                    'Un candidat libre ne peut pas être rattaché à un élève de l’établissement.',
                )
            if not cleaned.get('external_last_name') or not cleaned.get('external_first_name'):
                self.add_error('external_last_name', 'Nom et prénom du candidat libre requis.')
        else:
            if cleaned.get('is_external'):
                self.add_error(
                    'candidate_kind', 'Un candidat externe doit être déclaré comme candidat libre.'
                )
            if not cleaned.get('student'):
                self.add_error('student', 'Sélectionnez un élève pour un candidat régulier.')
        return cleaned
