# -*- coding: utf-8 -*-
"""Modèles de l'espace Surveillant : pointage, présences, sorties, discipline."""
from django.conf import settings
from django.db import models

from academics.models import ClassRoom
from students.models import Student


class AttendanceSession(models.Model):
    """Une séance de pointage validée pour une classe à une date donnée."""

    PERIOD_CHOICES = [
        ('journee', 'Journée'),
        ('matin', 'Matin'),
        ('apres_midi', 'Après-midi'),
    ]
    classroom = models.ForeignKey(ClassRoom, on_delete=models.CASCADE, related_name='surv_sessions')
    date = models.DateField()
    period = models.CharField(max_length=12, choices=PERIOD_CHOICES, default='journee')
    validated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='surv_validated_sessions',
    )
    validated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['classroom', 'date', 'period'],
                name='surv_unique_session_class_date_period',
            )
        ]
        ordering = ['-date', 'classroom__name']

    def __str__(self):
        return f'{self.classroom} — {self.date} ({self.get_period_display()})'


class PresenceRecord(models.Model):
    """Présence d'un élève pour une date et une séance."""

    STATUS_CHOICES = [
        ('present', 'Présent'),
        ('absent', 'Absent'),
        ('retard', 'En retard'),
        ('sortie', 'Sortie anticipée'),
        ('exclu', 'Exclusion temporaire'),
    ]
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='surv_presences')
    classroom = models.ForeignKey(
        ClassRoom, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='surv_presences',
    )
    session = models.ForeignKey(
        AttendanceSession, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='records',
    )
    date = models.DateField(db_index=True)
    period = models.CharField(max_length=12, default='journee')
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='present')
    arrival_time = models.TimeField(null=True, blank=True, verbose_name='Heure d’arrivée')
    reason = models.TextField(blank=True, verbose_name='Motif')
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='surv_recorded_presences',
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='surv_updated_presences',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['student', 'date', 'period'],
                name='surv_unique_presence_student_date_period',
            )
        ]
        ordering = ['-date', 'student__last_name']

    def __str__(self):
        return f'{self.student} — {self.date} : {self.get_status_display()}'


class PresenceChange(models.Model):
    """Historique des modifications d'une présence (traçabilité)."""

    record = models.ForeignKey(PresenceRecord, on_delete=models.CASCADE, related_name='changes')
    old_status = models.CharField(max_length=12, blank=True)
    new_status = models.CharField(max_length=12, blank=True)
    old_reason = models.TextField(blank=True)
    new_reason = models.TextField(blank=True)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='surv_presence_changes',
    )
    changed_at = models.DateTimeField(auto_now_add=True)
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['-changed_at']


class StudentExit(models.Model):
    """Sortie anticipée d'un élève, avec personne venant le récupérer."""

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='surv_exits')
    classroom = models.ForeignKey(
        ClassRoom, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='surv_exits',
    )
    date = models.DateField()
    exit_time = models.TimeField(verbose_name='Heure de sortie')
    reason = models.TextField(blank=True, verbose_name='Motif')
    picked_up_by = models.CharField(max_length=150, blank=True, verbose_name='Récupéré par')
    return_time = models.TimeField(null=True, blank=True, verbose_name='Heure de retour')
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='surv_recorded_exits',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-exit_time']


class DisciplineIncident(models.Model):
    """Avertissement, observation ou sanction enregistré par le surveillant."""

    TYPE_CHOICES = [
        ('avertissement', 'Avertissement'),
        ('observation', 'Observation'),
        ('retenue', 'Retenue'),
        ('sanction', 'Sanction'),
        ('exclusion', 'Exclusion temporaire'),
    ]
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name='surv_incidents'
    )
    classroom = models.ForeignKey(
        ClassRoom, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='surv_incidents',
    )
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='observation')
    motif = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    comment = models.TextField(blank=True, verbose_name='Commentaire de suivi')
    date = models.DateField()
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='surv_incidents',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-id']
