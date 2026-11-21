# -*- coding: utf-8 -*-
"""Actions et rapports PDF de la fiche classe (onglets intégrés à academics:classroom_detail)."""

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from academics.models import AcademicYear, ClassRoom, ClassSubject, SubjectAssignment
from attendance.models import Absence
from core.permissions import role_required
from grades.bulletin_views import _build_bulletin_context
from students.models import Student
from teachers.models import Teacher

from .models import Sanction
from secretariat.pdf import document_pdf


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
    return redirect(f'/classes/{pk}/?tab=matieres')


@require_POST
@role_required('directeur', 'secretaire')
def sanction_delete(request, pk, sanction_id):
    Sanction.objects.filter(pk=sanction_id, classroom_id=pk).delete()
    messages.success(request, 'Sanction supprimée.')
    return redirect(f'/classes/{pk}/?tab=discipline')
