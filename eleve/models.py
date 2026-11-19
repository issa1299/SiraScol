from django.db import models

from academics.models import ClassRoom, Subject
from students.models import Student
from teachers.models import Teacher


class Homework(models.Model):
    """Devoir donné par un enseignant à une classe."""

    classroom = models.ForeignKey(
        ClassRoom, on_delete=models.CASCADE, related_name='homeworks',
        verbose_name='Classe',
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name='homeworks',
        verbose_name='Matière',
    )
    teacher = models.ForeignKey(
        Teacher, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='homeworks', verbose_name='Enseignant',
    )
    title = models.CharField(max_length=200, verbose_name='Titre')
    instructions = models.TextField(blank=True, verbose_name='Consignes')
    due_date = models.DateField(verbose_name='Date limite')
    document = models.FileField(
        upload_to='devoirs/%Y/%m/', blank=True, null=True,
        verbose_name='Document associé',
    )
    is_published = models.BooleanField(default=True, verbose_name='Publié')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Devoir'
        verbose_name_plural = 'Devoirs'
        ordering = ['due_date', '-created_at']

    def __str__(self):
        return f'{self.title} — {self.classroom.name}'


class HomeworkCompletion(models.Model):
    """Suivi individuel des devoirs marqués comme faits par un élève."""

    homework = models.ForeignKey(
        Homework, on_delete=models.CASCADE, related_name='completions',
    )
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name='homework_completions',
    )
    done_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Devoir effectué'
        verbose_name_plural = 'Devoirs effectués'
        unique_together = ['homework', 'student']

    def __str__(self):
        return f'{self.student.matricule} → {self.homework.title}'
