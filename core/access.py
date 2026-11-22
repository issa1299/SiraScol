# -*- coding: utf-8 -*-
"""
Contrôle d'accès aux objets (filtrages serveur).
À utiliser dans chaque vue métier pour empêcher l'accès par ID URL.
"""
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404

from core.permissions import (
    get_role,
    get_linked_student,
    get_parent_students,
    get_teacher_classrooms,
    get_linked_teacher,
)


def filter_students_for_user(user, queryset=None):
    """Restreint un QuerySet Student selon le rôle."""
    from students.models import Student
    qs = queryset if queryset is not None else Student.objects.all()
    role = get_role(user)
    if role in ('directeur', 'comptable', 'surveillant') or (user and user.is_superuser):
        return qs
    if role == 'secretaire':
        return qs
    if role == 'enseignant':
        classrooms = get_teacher_classrooms(user)
        return qs.filter(enrollments__classroom__in=classrooms).distinct()
    if role == 'parent':
        return get_parent_students(user)
    if role == 'eleve':
        st = get_linked_student(user)
        return qs.filter(pk=st.pk) if st else qs.none()
    return qs.none()


def get_student_for_user(user, student_id):
    """
    Récupère un élève UNIQUEMENT s'il est accessible à l'utilisateur.
    Lève Http404 si l'ID n'existe pas ou n'est pas autorisé (pas d'info-leak).
    """
    from students.models import Student
    qs = filter_students_for_user(user, Student.objects.all())
    return get_object_or_404(qs, pk=student_id)


def user_can_access_student(user, student):
    if not user or not student:
        return False
    return filter_students_for_user(user).filter(pk=student.pk).exists()


def filter_classrooms_for_user(user, queryset=None):
    from academics.models import ClassRoom
    qs = queryset if queryset is not None else ClassRoom.objects.all()
    role = get_role(user)
    if role in ('directeur', 'secretaire', 'comptable', 'surveillant') or (user and user.is_superuser):
        return qs
    if role == 'enseignant':
        return get_teacher_classrooms(user)
    if role in ('parent', 'eleve'):
        # classes de leurs enfants / eux-mêmes via inscriptions actives
        students = filter_students_for_user(user)
        return qs.filter(enrollments__student__in=students).distinct()
    return qs.none()


def get_classroom_for_user(user, classroom_id):
    from academics.models import ClassRoom
    qs = filter_classrooms_for_user(user, ClassRoom.objects.all())
    return get_object_or_404(qs, pk=classroom_id)


def assert_teacher_owns_classroom(user, classroom):
    role = get_role(user)
    if role == 'directeur' or user.is_superuser:
        return
    if role != 'enseignant':
        raise PermissionDenied('Accès réservé aux enseignants de cette classe.')
    if not get_teacher_classrooms(user).filter(pk=classroom.pk).exists():
        raise PermissionDenied('Cette classe ne vous est pas affectée.')


def assert_can_manage_grades(user):
    role = get_role(user)
    if role in ('directeur', 'enseignant') or user.is_superuser:
        return
    raise PermissionDenied('Vous ne pouvez pas gérer les notes.')


def assert_can_manage_finance(user):
    # Le secrétaire ne gère pas les transactions (voir PERMISSIONS['finance.*']).
    role = get_role(user)
    if role in ('directeur', 'comptable') or user.is_superuser:
        return
    raise PermissionDenied('Vous ne pouvez pas gérer les finances.')
