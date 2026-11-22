from django.db import models
from core.validators import validate_upload

from academics.models import ClassRoom, Subject
from grades.models import Period
from students.models import Student
from teachers.models import Teacher


class TeachingMaterial(models.Model):
    """Support de cours PDF publié par un enseignant."""

    teacher = models.ForeignKey(
        Teacher, on_delete=models.CASCADE, related_name='materials',
    )
    classroom = models.ForeignKey(
        ClassRoom, on_delete=models.CASCADE, related_name='materials',
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name='materials',
    )
    title = models.CharField(max_length=200, verbose_name='Titre')
    description = models.TextField(blank=True, verbose_name='Description')
    file = models.FileField(validators=[validate_upload], 
        upload_to='supports/%Y/%m/', verbose_name='Fichier (PDF, exercice…)',
    )
    is_published = models.BooleanField(default=True, verbose_name='Publié')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Support de cours'
        verbose_name_plural = 'Supports de cours'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.title} — {self.subject.name} ({self.classroom.name})'


class BulletinAppreciation(models.Model):
    """Appréciation proposée par un enseignant pour un élève."""

    teacher = models.ForeignKey(
        Teacher, on_delete=models.CASCADE, related_name='appreciations',
    )
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name='teacher_appreciations',
    )
    period = models.ForeignKey(
        Period, on_delete=models.CASCADE, null=True, blank=True,
        related_name='teacher_appreciations',
    )
    appreciation = models.TextField(verbose_name='Appréciation')
    is_general = models.BooleanField(default=False, verbose_name='Appréciation générale')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Appréciation'
        verbose_name_plural = 'Appréciations'
        ordering = ['-updated_at']


class Appointment(models.Model):
    """Demande de rendez-vous parent ↔ enseignant/direction."""

    STATUS_CHOICES = [
        ('en_attente', 'En attente'),
        ('accepte', 'Accepté'),
        ('refuse', 'Refusé'),
        ('traite', 'Traité'),
    ]

    parent = models.ForeignKey(
        'students.Parent', on_delete=models.CASCADE, related_name='appointments',
    )
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name='appointments',
    )
    teacher = models.ForeignKey(
        Teacher, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='appointments',
    )
    motif = models.CharField(max_length=200, verbose_name='Motif')
    message = models.TextField(blank=True, verbose_name='Message')
    proposed_date = models.DateField(null=True, blank=True, verbose_name='Date souhaitée')
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='en_attente',
    )
    response = models.TextField(blank=True, verbose_name='Réponse')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Rendez-vous'
        verbose_name_plural = 'Rendez-vous'
        ordering = ['-created_at']
