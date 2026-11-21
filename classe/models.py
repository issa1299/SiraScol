from django.db import models

from academics.models import ClassRoom
from students.models import Student


class Sanction(models.Model):
    """Suivi disciplinaire d'un élève dans une classe."""

    TYPE_CHOICES = [
        ('retention', 'Retenue'),
        ('avertissement', 'Avertissement'),
        ('exclusion', 'Exclusion'),
        ('observation', 'Observation'),
    ]

    classroom = models.ForeignKey(
        ClassRoom, on_delete=models.CASCADE, related_name='sanctions',
    )
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name='sanctions',
    )
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='observation')
    motif = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    date = models.DateField()
    auteur = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True,
    )

    class Meta:
        verbose_name = 'Sanction disciplinaire'
        verbose_name_plural = 'Sanctions disciplinaires'
        ordering = ['-date', '-id']

    def __str__(self):
        return f'{self.get_type_display()} — {self.student.full_name} ({self.date})'
