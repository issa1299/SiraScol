from django.db import models
from students.models import Student
from academics.models import ClassRoom, AcademicYear
from teachers.models import Teacher


class Absence(models.Model):
    """Absence ou retard d'un élève"""
    TYPE_CHOICES = [
        ('absence', 'Absence'),
        ('retard', 'Retard'),
    ]
    STATUS_CHOICES = [
        ('non_justifiee', 'Non justifiée'),
        ('justifiee', 'Justifiée'),
        ('en_attente', 'En attente'),
    ]

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='absences')
    classroom = models.ForeignKey(ClassRoom, on_delete=models.SET_NULL, null=True, blank=True)
    date = models.DateField(verbose_name='Date')
    type = models.CharField(max_length=10, choices=TYPE_CHOICES, default='absence')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='non_justifiee')
    reason = models.TextField(blank=True, verbose_name='Motif')
    justification_file = models.FileField(upload_to='justificatifs/', blank=True, null=True)
    recorded_by = models.ForeignKey(Teacher, on_delete=models.SET_NULL, null=True, blank=True)
    notified_parent = models.BooleanField(default=False, verbose_name='Parent notifié')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Absence / Retard'
        verbose_name_plural = 'Absences / Retards'
        ordering = ['-date']
        unique_together = ['student', 'date', 'type']

    def __str__(self):
        return f"{self.student} - {self.get_type_display()} le {self.date}"


class AttendancePunch(models.Model):
    """Pointage QR — arrivée / départ (élève ou personnel)."""
    KIND_CHOICES = [
        ('eleve', 'Élève'),
        ('personnel', 'Personnel'),
    ]
    ACTION_CHOICES = [
        ('arrivee', 'Arrivée'),
        ('depart', 'Départ'),
    ]

    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default='eleve')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, null=True, blank=True, related_name='punches'
    )
    teacher = models.ForeignKey(
        Teacher, on_delete=models.CASCADE, null=True, blank=True, related_name='punches'
    )
    punched_at = models.DateTimeField(auto_now_add=True)
    date = models.DateField(db_index=True)
    notes = models.CharField(max_length=255, blank=True)
    recorded_by = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='recorded_punches'
    )

    class Meta:
        verbose_name = 'Pointage'
        verbose_name_plural = 'Pointages'
        ordering = ['-punched_at']
        # Un seul pointage (arrivée OU départ) par personne et par jour
        constraints = [
            models.UniqueConstraint(
                fields=['kind', 'student', 'date', 'action'],
                condition=models.Q(student__isnull=False),
                name='uniq_punch_student_day_action',
            ),
            models.UniqueConstraint(
                fields=['kind', 'teacher', 'date', 'action'],
                condition=models.Q(teacher__isnull=False),
                name='uniq_punch_teacher_day_action',
            ),
        ]

    def __str__(self):
        who = self.student or self.teacher
        return f"{who} — {self.get_action_display()} {self.punched_at}"

    @property
    def person_name(self):
        if self.student_id:
            return f"{self.student.last_name} {self.student.first_name}"
        if self.teacher_id:
            return f"{self.teacher.last_name} {self.teacher.first_name}"
        return '—'

    @property
    def code(self):
        if self.student_id:
            return self.student.matricule
        if self.teacher_id:
            return self.teacher.matricule
        return ''
