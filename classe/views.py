# -*- coding: utf-8 -*-
"""Espace Classe — toute la vie scolaire d'une classe dans un seul espace."""

from datetime import date

from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from academics.models import AcademicYear, ClassRoom, ClassSubject, Subject, SubjectAssignment
from attendance.models import Absence
from core.permissions import role_required
from core.year_context import get_selected_year
from grades.bulletin_views import _build_bulletin_context
from grades.models import Period
from students.models import Enrollment, Student
from teachers.models import Teacher
from timetable.models import TimeSlot, TimetableEntry

from .models import Sanction
from secretariat.pdf import document_pdf

DAYS = [(1, 'Lundi'), (2, 'Mardi'), (3, 'Mercredi'), (4, 'Jeudi'), (5, 'Vendredi'), (6, 'Samedi')]
TABS = [
    ('general', 'Vue générale', 'fa-gauge-high'),
    ('eleves', 'Élèves', 'fa-user-graduate'),
    ('matieres', 'Matières', 'fa-book'),
    ('enseignants', 'Enseignants', 'fa-chalkboard-user'),
    ('emploi', 'Emploi du temps', 'fa-calendar-days'),
    ('presences', 'Présences', 'fa-calendar-day'),
    ('notes', 'Notes', 'fa-chart-line'),
    ('discipline', 'Discipline', 'fa-shield-halved'),
    ('bulletins', 'Bulletins', 'fa-file-invoice'),
    ('rapports', 'Rapports', 'fa-file-lines'),
]


def _year():
    return get_selected_year(None) or AcademicYear.objects.filter(is_current=True).first() or \
        AcademicYear.objects.order_by('-start_date', '-id').first()


@role_required('directeur', 'secretaire')
def classes_list(request):
    """Onglet Gestion des classes : toutes les classes avec effectifs."""
    year = _year()
    qs = ClassRoom.objects.filter(academic_year=year).annotate(
        n_students=Count('enrollments', filter=Q(enrollments__is_active=True), distinct=True),
        n_subjects=Count('class_subjects', distinct=True),
        n_teachers=Count('assignments', distinct=True),
    ).select_related('level', 'level__cycle', 'main_teacher').order_by(
        'level__cycle__order', 'level__order', 'name'
    )
    return render(request, 'classe/classes.html', {
        'classes': qs, 'year': year, 'tab': 'gestion', 'tabs': TABS,
    })


@role_required('directeur', 'secretaire')
def class_space(request, pk):
    classroom = get_object_or_404(
        ClassRoom.objects.select_related('level', 'level__cycle', 'academic_year', 'main_teacher'),
        pk=pk,
    )
    tab = request.GET.get('tab', 'general')
    if tab not in [t[0] for t in TABS]:
        tab = 'general'
    year = classroom.academic_year
    students = list(Student.objects.filter(
        enrollments__classroom=classroom, enrollments__is_active=True
    ).select_related('user').order_by('last_name', 'first_name'))
    student_ids = [s.pk for s in students]

    ctx = {
        'classroom': classroom, 'year': year, 'tab': tab, 'tabs': TABS,
        'students': students, 'nb_students': len(students),
        'today': date.today(),
        'rapports': [
            ('effectif', 'Liste officielle des élèves', 'fa-users'),
            ('presence', 'Liste de présence / absences', 'fa-calendar-day'),
            ('enseignants', 'Liste des enseignants', 'fa-chalkboard-user'),
            ('resultats', 'Statistiques & résultats', 'fa-chart-pie'),
        ],
    }

    if tab == 'general':
        ctx['nb_boys'] = sum(1 for s in students if s.gender == 'M')
        ctx['nb_girls'] = sum(1 for s in students if s.gender == 'F')
        ctx['nb_subjects'] = ClassSubject.objects.filter(classroom=classroom).count()
        ctx['nb_teachers'] = SubjectAssignment.objects.filter(classroom=classroom).count() + (
            1 if classroom.main_teacher_id else 0
        )
        ctx['nb_absences'] = Absence.objects.filter(student_id__in=student_ids).count()
        avgs = []
        for s in students:
            b = _build_bulletin_context(s, None, year)
            if b.get('general_avg') is not None:
                avgs.append(float(b['general_avg']))
        ctx['class_avg'] = round(sum(avgs) / len(avgs), 2) if avgs else None
        ctx['recent_enrollments'] = Enrollment.objects.filter(
            classroom=classroom
        ).select_related('student').order_by('-created_at')[:6]

    elif tab == 'eleves':
        from students.models import ParentStudent
        rows = []
        for s in students:
            ps = ParentStudent.objects.filter(student=s).select_related('parent').first()
            enr = s.enrollments.filter(classroom=classroom, is_active=True).first()
            rows.append({
                'student': s,
                'parent_phone': ps.parent.phone if ps and ps.parent else '—',
                'enrollment': enr,
            })
        ctx['rows'] = rows

    elif tab == 'matieres':
        if request.method == 'POST' and request.POST.get('action') == 'add':
            subject_id = request.POST.get('subject')
            if subject_id:
                ClassSubject.objects.get_or_create(
                    classroom=classroom, subject_id=subject_id,
                    defaults={
                        'coefficient': request.POST.get('coefficient') or None,
                        'hours_per_week': request.POST.get('hours') or 2,
                    },
                )
                teacher_id = request.POST.get('teacher')
                if teacher_id:
                    SubjectAssignment.objects.get_or_create(
                        teacher_id=teacher_id, subject_id=subject_id, classroom=classroom,
                        defaults={'hours_per_week': request.POST.get('hours') or 2},
                    )
                messages.success(request, 'Matière ajoutée à la classe.')
            return redirect(f'/classe/{classroom.pk}/?tab=matieres')
        rows = []
        for cs in ClassSubject.objects.filter(classroom=classroom).select_related('subject'):
            assignment = SubjectAssignment.objects.filter(
                classroom=classroom, subject=cs.subject
            ).select_related('teacher').first()
            rows.append({'cs': cs, 'teacher': assignment.teacher if assignment else None})
        ctx['rows'] = rows
        ctx['all_subjects'] = Subject.objects.filter(is_active=True).order_by('name')
        ctx['teachers'] = Teacher.objects.filter(is_active=True).order_by('last_name')

    elif tab == 'enseignants':
        ctx['assignments'] = SubjectAssignment.objects.filter(
            classroom=classroom
        ).select_related('teacher', 'subject').order_by('teacher__last_name')
        ctx['main_teacher'] = classroom.main_teacher

    elif tab == 'emploi':
        entries = {
            (e.day, e.time_slot_id): e for e in TimetableEntry.objects.filter(
                classroom=classroom
            ).select_related('subject', 'teacher', 'room', 'time_slot')
        }
        slots = []
        for slot in TimeSlot.objects.order_by('order'):
            name = (slot.name or '').lower()
            if name in ('récréation', 'recreation', 'soir', 'pause', 'déjeuner') or (
                slot.start_time.hour == 0 and slot.end_time.hour == 0
            ):
                continue
            cells = []
            for d, label in DAYS:
                e = entries.get((d, slot.pk))
                cells.append({'day': d, 'label': label, 'entry': e})
            slots.append({'slot': slot, 'cells': cells})
        ctx['slots'] = slots
        ctx['days'] = DAYS

    elif tab == 'presences':
        ctx['absences'] = Absence.objects.filter(
            student_id__in=student_ids
        ).select_related('student').order_by('-date')[:120]

    elif tab == 'notes':
        rows = []
        for s in students:
            b = _build_bulletin_context(s, None, year)
            rows.append({
                'student': s,
                'average': b.get('general_avg'),
                'rank': b.get('rank'), 'rank_total': b.get('rank_total'),
            })
        rows.sort(key=lambda r: -(r['average'] or 0))
        for i, r in enumerate(rows, 1):
            r['position'] = i
        ctx['rows'] = rows
        ctx['periods'] = Period.objects.filter(academic_year=year).order_by('order')

    elif tab == 'discipline':
        if request.method == 'POST' and request.POST.get('action') == 'sanction':
            if request.POST.get('student') and request.POST.get('motif'):
                Sanction.objects.create(
                    classroom=classroom,
                    student_id=request.POST['student'],
                    type=request.POST.get('type', 'observation'),
                    motif=request.POST['motif'],
                    description=request.POST.get('description', ''),
                    date=request.POST.get('date') or date.today().isoformat(),
                    auteur=request.user,
                )
                messages.success(request, 'Sanction enregistrée.')
            return redirect(f'/classe/{classroom.pk}/?tab=discipline')
        ctx['sanctions'] = Sanction.objects.filter(
            classroom=classroom
        ).select_related('student').order_by('-date')[:100]

    elif tab == 'bulletins':
        rows = []
        for s in students:
            b = _build_bulletin_context(s, None, year)
            rows.append({'student': s, 'average': b.get('general_avg'), 'rank': b.get('rank')})
        ctx['rows'] = rows

    elif tab == 'rapports':
        ctx['periods'] = Period.objects.filter(academic_year=year).order_by('order')

    return render(request, 'classe/space.html', ctx)


@role_required('directeur', 'secretaire')
def rapport_pdf(request, pk, kind):
    classroom = get_object_or_404(ClassRoom, pk=pk)
    students = Student.objects.filter(
        enrollments__classroom=classroom, enrollments__is_active=True
    ).order_by('last_name', 'first_name')
    if kind == 'effectif':
        lines = [f'Classe : {classroom.name}', f'Année : {classroom.academic_year.name}', '',
                 f'Effectif : {students.count()} élèves', '']
        for i, s in enumerate(students, 1):
            lines.append(f'{i:2}. {s.last_name} {s.first_name} — {s.matricule}')
    elif kind == 'presence':
        lines = [f'Classe : {classroom.name}', '', 'Historique des absences et retards', '']
        for a in Absence.objects.filter(student__in=students).select_related('student').order_by('-date')[:100]:
            lines.append(f"{a.date.strftime('%d/%m/%Y')} — {a.student.full_name} — {a.get_type_display()} — {a.reason or ''}")
    elif kind == 'enseignants':
        lines = [f'Classe : {classroom.name}', '', 'Enseignants intervenants', '']
        for a in SubjectAssignment.objects.filter(classroom=classroom).select_related('teacher', 'subject'):
            lines.append(f'{a.teacher.get_full_name()} — {a.subject.name} — {a.hours_per_week} h/sem')
    elif kind == 'resultats':
        lines = [f'Classe : {classroom.name}', '', 'Résultats', '']
        for s in students:
            b = _build_bulletin_context(s, None, classroom.academic_year)
            lines.append(f'{s.full_name} ({s.matricule}) — moyenne {b.get("general_avg") or "—"} — rang {b.get("rank") or "—"}')
    else:
        lines = ['Rapport indisponible.']
    return document_pdf(f'Rapport — {classroom.name}', lines, f'rapport_{kind}_{classroom.pk}.pdf')


@require_POST
@role_required('directeur', 'secretaire')
def matiere_delete(request, pk, subject_id):
    ClassSubject.objects.filter(classroom_id=pk, subject_id=subject_id).delete()
    SubjectAssignment.objects.filter(classroom_id=pk, subject_id=subject_id).delete()
    messages.success(request, 'Matière retirée de la classe.')
    return redirect(f'/classe/{pk}/?tab=matieres')


@require_POST
@role_required('directeur', 'secretaire')
def sanction_delete(request, pk, sanction_id):
    Sanction.objects.filter(pk=sanction_id, classroom_id=pk).delete()
    messages.success(request, 'Sanction supprimée.')
    return redirect(f'/classe/{pk}/?tab=discipline')
