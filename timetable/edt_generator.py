# -*- coding: utf-8 -*-
"""Génération d'une grille d'emploi du temps de base, classe par classe."""

from django.db.models import Q

from academics.models import ClassSubject, Subject, SubjectAssignment
from timetable.models import TimetableEntry, TimeSlot


DEFAULT_DAYS = (1, 2, 3, 4, 5)  # Lundi → Vendredi


def _is_break_slot(slot):
    n = (slot.name or '').strip().lower()
    return n in ('récréation', 'recreation', 'récré', 'soir', 'pause', 'déjeuner', 'dejeuner') \
        or n.startswith('pause:')


def _usable_slots():
    slots = []
    for s in TimeSlot.objects.order_by('order'):
        if _is_break_slot(s):
            continue
        if s.start_time.hour == 0 and s.end_time.hour == 0 and s.start_time.minute == 0:
            continue
        slots.append(s)
    return slots


def _subject_pool(classroom):
    """Liste de matières pondérée par heures/semaine (ou tournée simple)."""
    pool = []
    cs = list(
        ClassSubject.objects.filter(classroom=classroom)
        .select_related('subject').order_by('order', 'subject__name')
    )
    for item in cs:
        hours = max(1, min(item.hours_per_week or 1, 6))
        pool.extend([item.subject] * hours)
    if pool:
        return pool

    cycle = getattr(classroom.level, 'cycle', None)
    qs = Subject.objects.filter(is_active=True)
    if cycle:
        cycle_qs = qs.filter(cycles=cycle)
        if cycle_qs.exists():
            qs = cycle_qs
    return list(qs.order_by('name'))


def generate_for_class(classroom, days=DEFAULT_DAYS, overwrite=False):
    """Remplit les créneaux vides d'une classe. Retourne un petit rapport."""
    from timetable.views import ensure_default_slots
    ensure_default_slots()

    slots = _usable_slots()
    pool = _subject_pool(classroom)
    if not slots:
        raise ValueError('Aucun créneau horaire utilisable (vérifiez la configuration).')
    if not pool:
        raise ValueError('Aucune matière disponible pour cette classe.')

    assignments = {
        a.subject_id: a.teacher_id
        for a in SubjectAssignment.objects.filter(classroom=classroom)
    }

    days = list(days)
    existing = {
        (e.day, e.time_slot_id): e
        for e in TimetableEntry.objects.filter(classroom=classroom)
    }
    busy = {
        (e.teacher_id, e.day, e.time_slot_id)
        for e in TimetableEntry.objects.filter(
            day__in=days, time_slot__in=slots
        ).exclude(teacher__isnull=True)
        if e.teacher_id
    }

    created = updated = skipped = 0
    for day in days:
        for index, slot in enumerate(slots):
            key = (day, slot.pk)
            old = existing.get(key)
            if old:
                if not overwrite:
                    skipped += 1
                    continue
                if old.teacher_id:
                    busy.discard((old.teacher_id, day, slot.pk))
                old.delete()

            subject = pool[(index + (day - 1) * 2) % len(pool)]
            teacher_id = assignments.get(subject.pk)
            if teacher_id and (teacher_id, day, slot.pk) in busy:
                teacher_id = None  # conflit : on laisse le prof vide

            TimetableEntry.objects.create(
                classroom=classroom,
                subject=subject,
                teacher_id=teacher_id,
                day=day,
                time_slot=slot,
            )
            if teacher_id:
                busy.add((teacher_id, day, slot.pk))
            if old:
                updated += 1
            else:
                created += 1

    return {
        'classroom': classroom, 'created': created,
        'updated': updated, 'skipped': skipped,
        'days': len(days), 'slots': len(slots),
    }
