# -*- coding: utf-8 -*-
"""Gestion des candidats aux examens nationaux : DEF et BAC."""
from django.conf import settings
from django.db import models

from academics.models import AcademicYear, ClassRoom
from students.models import Student


class ExamSession(models.Model):
    TYPE_CHOICES = [('def', 'DEF — Diplôme d’Études Fondamentales'),
                    ('bac', 'BAC — Baccalauréat')]
    SESSION_CHOICES = [('normal', 'Session normale'), ('rattrapage', 'Rattrapage')]

    type = models.CharField(max_length=5, choices=TYPE_CHOICES)
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE,
                                      related_name='exam_sessions')
    session = models.CharField(max_length=12, choices=SESSION_CHOICES, default='normal')
    date = models.DateField(verbose_name='Date de l’examen')
    center = models.CharField(max_length=150, blank=True, verbose_name='Centre d’examen')
    is_open = models.BooleanField(default=True, verbose_name='Inscriptions ouvertes')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['type', 'academic_year', 'session'],
                name='exam_unique_session',
            )
        ]
        ordering = ['-date']

    def __str__(self):
        return f'{self.get_type_display()} — {self.academic_year.name} ({self.get_session_display()})'


class Candidate(models.Model):
    STATUS_CHOICES = [
        ('inscrit', 'Inscrit'),
        ('valide', 'Validé'),
        ('absent', 'Absent'),
        ('admis', 'Admis'),
        ('eche', 'Échoué'),
        ('rattrapage', 'Rattrapage'),
    ]
    SERIES_CHOICES = [
        ('', '—'),
        ('scientifique', 'Scientifique'),
        ('litteraire', 'Littéraire'),
        ('stg', 'STG — Sciences et technologiques de gestion'),
        ('sti', 'STI — Sciences et techniques industrielles'),
    ]

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='exam_candidates')
    session = models.ForeignKey(ExamSession, on_delete=models.CASCADE, related_name='candidates')
    registration_number = models.CharField(max_length=30, unique=True, blank=True,
                                            verbose_name='Numéro de candidat')
    classroom = models.ForeignKey(ClassRoom, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='exam_candidates')
    series = models.CharField(max_length=20, choices=SERIES_CHOICES, blank=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='inscrit')
    exam_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                    verbose_name='Frais d’examen')
    fee_paid = models.BooleanField(default=False, verbose_name='Frais payés')
    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                    null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['student', 'session'], name='exam_unique_candidate',
            )
        ]
        ordering = ['registration_number', 'student__last_name']

    def __str__(self):
        return f'{self.registration_number} — {self.student.full_name}'

    def save(self, *args, **kwargs):
        if not self.registration_number:
            prefix = 'D' if self.session.type == 'def' else 'B'
            year = self.session.academic_year.name.replace('-', '')[-4:]
            last = Candidate.objects.filter(
                registration_number__startswith=f'{prefix}{year}'
            ).order_by('-registration_number').values_list('registration_number', flat=True).first()
            n = 1
            if last:
                try:
                    n = int(last[-4:]) + 1
                except ValueError:
                    n = Candidate.objects.count() + 1
            self.registration_number = f'{prefix}{year}{n:04d}'
        super().save(*args, **kwargs)
