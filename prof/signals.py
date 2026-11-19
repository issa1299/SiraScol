"""Notifications automatiques vers les portails (élève, parent, professeur)."""

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse

from core.notifications import notify, notify_role, notify_student_and_parents


@receiver(post_save, sender='grades.Grade')
def grade_saved(sender, instance, created, **kwargs):
    if not created or instance.is_absent:
        return
    student = instance.student
    assessment = instance.assessment
    subject = assessment.subject.name if assessment and assessment.subject_id else 'une matière'
    title = f'Nouvelle note en {subject}'
    message = f'{student.full_name} : {instance.score}/{assessment.max_score if assessment else 20}'
    link = reverse('eleve:notes')
    notify_student_and_parents(student, title, message, 'note', link)


@receiver(post_save, sender='attendance.Absence')
def absence_saved(sender, instance, created, **kwargs):
    if not created:
        return
    student = instance.student
    kind = 'Absence' if instance.type == 'absence' else 'Retard'
    notify_student_and_parents(
        student,
        f'{kind} enregistré(e)',
        f"{instance.date.strftime('%d/%m/%Y')} — {instance.reason or 'motif non précisé'}",
        'absence',
        reverse('eleve:absences'),
    )


@receiver(post_save, sender='communication.Announcement')
def announcement_saved(sender, instance, created, **kwargs):
    if not created or not instance.is_published:
        return
    for role in ('eleve', 'parent', 'enseignant'):
        notify_role(role, instance.title, 'Nouvelle annonce de l’établissement.', 'annonce', '/annonces/')


@receiver(post_save, sender='timetable.TimetableEntry')
def timetable_saved(sender, instance, created, **kwargs):
    if not created:
        return
    teacher = instance.teacher
    if teacher and teacher.user_id:
        notify(
            teacher.user,
            'Nouveau cours à votre emploi du temps',
            f"{instance.subject.name} — classe {instance.classroom.name}",
            'emploi',
            '/mon-espace-prof/emploi-du-temps/',
        )
