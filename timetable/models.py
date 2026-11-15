from django.db import models
from academics.models import ClassRoom, Subject
from teachers.models import Teacher


class Room(models.Model):
    """Salle de classe"""
    name = models.CharField(max_length=50, unique=True, verbose_name='Nom')
    capacity = models.PositiveIntegerField(default=40)
    building = models.CharField(max_length=50, blank=True, verbose_name='Bâtiment')

    class Meta:
        verbose_name = 'Salle'
        verbose_name_plural = 'Salles'
        ordering = ['name']

    def __str__(self):
        return self.name


class TimeSlot(models.Model):
    """Créneau horaire (ex: 8h-9h, 9h-10h...)"""
    name = models.CharField(max_length=30)  # ex: "1ère heure"
    start_time = models.TimeField()
    end_time = models.TimeField()
    order = models.PositiveIntegerField(default=1)

    class Meta:
        verbose_name = 'Créneau'
        verbose_name_plural = 'Créneaux'
        ordering = ['order']

    def __str__(self):
        return f"{self.name} ({self.start_time.strftime('%H:%M')}-{self.end_time.strftime('%H:%M')})"


class TimetableEntry(models.Model):
    """Une entrée d'emploi du temps"""
    DAY_CHOICES = [
        (1, 'Lundi'),
        (2, 'Mardi'),
        (3, 'Mercredi'),
        (4, 'Jeudi'),
        (5, 'Vendredi'),
        (6, 'Samedi'),
    ]

    classroom = models.ForeignKey(ClassRoom, on_delete=models.CASCADE, related_name='timetable_entries')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='timetable_entries')
    teacher = models.ForeignKey(Teacher, on_delete=models.SET_NULL, null=True, related_name='timetable_entries')
    room = models.ForeignKey(Room, on_delete=models.SET_NULL, null=True, blank=True)
    day = models.PositiveSmallIntegerField(choices=DAY_CHOICES)
    time_slot = models.ForeignKey(TimeSlot, on_delete=models.CASCADE, related_name='entries')

    class Meta:
        verbose_name = "Entrée d'emploi du temps"
        verbose_name_plural = "Emploi du temps"
        unique_together = [
            ['classroom', 'day', 'time_slot'],  # Une classe ne peut pas avoir 2 cours en même temps
            ['teacher', 'day', 'time_slot'],    # Un enseignant non plus
        ]
        ordering = ['day', 'time_slot__order']

    def __str__(self):
        return f"{self.get_day_display()} {self.time_slot} - {self.classroom} : {self.subject}"
