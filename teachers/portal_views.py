"""Portail enseignant — interface dédiée (pas l'admin)."""
from datetime import date

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Count, Q

from core.permissions import get_role, get_linked_teacher, get_teacher_classrooms
from core.year_context import get_selected_year
from academics.models import SubjectAssignment
from students.models import Enrollment


def _require_teacher(request):
    role = get_role(request.user)
    teacher = get_linked_teacher(request.user)
    if request.user.is_superuser:
        return teacher
    if role != 'enseignant' and not teacher:
        messages.error(request, "Accès réservé aux enseignants.")
        return None
    if not teacher:
        messages.warning(request, "Aucune fiche enseignant liée à votre compte.")
    return teacher


@login_required
def portal_home(request):
    """Redirige vers le tableau de bord (déjà adapté)."""
    return redirect('core:dashboard')


@login_required
def portal_classes(request):
    """Liste des classes affectées + matières."""
    teacher = _require_teacher(request)
    year = get_selected_year(request)
    classrooms = get_teacher_classrooms(request.user)
    if year:
        classrooms = classrooms.filter(academic_year=year)
    classrooms = classrooms.select_related('level', 'level__cycle').annotate(
        n_eleves=Count('enrollments', filter=Q(enrollments__is_active=True))
    ).order_by('level__cycle__order', 'level__order', 'name')

    # matières par classe
    assign_map = {}
    if teacher:
        qs = SubjectAssignment.objects.filter(teacher=teacher).select_related('subject', 'classroom')
        if year:
            qs = qs.filter(classroom__academic_year=year)
        for a in qs:
            assign_map.setdefault(a.classroom_id, []).append(a.subject)

    rows = []
    for c in classrooms:
        rows.append({
            'classroom': c,
            'subjects': assign_map.get(c.id, []),
            'n_eleves': getattr(c, 'n_eleves', 0),
            'is_main': c.main_teacher_id == (teacher.id if teacher else None),
        })

    return render(request, 'teachers/portal_classes.html', {
        'teacher': teacher,
        'rows': rows,
        'selected_year': year,
        'today': date.today(),
    })


@login_required
def portal_class(request, classroom_id):
    """Détail d'une classe : élèves + actions notes / appel."""
    teacher = _require_teacher(request)
    year = get_selected_year(request)
    classrooms = get_teacher_classrooms(request.user)
    classroom = get_object_or_404(
        classrooms.select_related('level', 'level__cycle'), pk=classroom_id
    )
    enrollments = Enrollment.objects.filter(
        classroom=classroom, is_active=True
    ).select_related('student').order_by('student__last_name', 'student__first_name')
    if year:
        enrollments = enrollments.filter(academic_year=year)

    subjects = []
    if teacher:
        subjects = list(
            SubjectAssignment.objects.filter(
                teacher=teacher, classroom=classroom
            ).select_related('subject')
        )

    return render(request, 'teachers/portal_class.html', {
        'teacher': teacher,
        'classroom': classroom,
        'enrollments': enrollments,
        'subjects': subjects,
        'selected_year': year,
        'n_students': enrollments.count(),
        'is_main': classroom.main_teacher_id == (teacher.id if teacher else None),
    })
