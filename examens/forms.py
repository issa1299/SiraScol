# -*- coding: utf-8 -*-
"""Formulaires du module Examens nationaux."""
from decimal import Decimal, InvalidOperation

from django import forms

from core.widgets import SmartDateInput
from students.models import Student

from .models import Candidate


class CandidateForm(forms.ModelForm):
    """Inscription / modification d'un candidat DEF ou BAC (élève ou externe)."""

    class Meta:
        model = Candidate
        fields = [
            'session', 'student', 'is_external',
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
            'registration_status': 'Statut d’inscription',
            'status': 'Résultat / présence',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['student'].required = False
        self.fields['student'].queryset = Student.objects.filter(status='actif').order_by(
            'last_name', 'first_name'
        )
        for name in ('external_matricule', 'external_last_name', 'external_first_name',
                     'external_gender', 'external_date_of_birth', 'birth_place', 'school_name',
                     'parent_name', 'parent_phone', 'photo', 'birth_certificate',
                     'other_document', 'series', 'speciality', 'terminale_class',
                     'living_language', 'subjects_options', 'notes',
                     'exam_fee', 'fee_paid', 'registration_status', 'status'):
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
        if cleaned.get('is_external'):
            if not cleaned.get('external_last_name') or not cleaned.get('external_first_name'):
                self.add_error('external_last_name', 'Nom et prénom du candidat externe requis.')
        elif not cleaned.get('student'):
            self.add_error('student', 'Sélectionnez un élève ou cochez « candidat externe ».')
        return cleaned
