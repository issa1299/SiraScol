# -*- coding: utf-8 -*-
"""Règles de messagerie privée, vérifiées côté serveur.

Toute création de Message passe par `can_message()`, quelle que soit l'interface
(portails dédiés, messagerie générale, commandes, signaux).
"""

from django.contrib.auth.models import User

from core.permissions import get_role, get_linked_teacher, get_linked_parent, get_parent_students
from students.models import Enrollment, ParentStudent


# Rôles avec lesquels chaque rôle peut communiquer (hors restrictions par élève/classe).
ROLE_RULES = {
    'directeur': {'directeur', 'secretaire', 'comptable', 'surveillant', 'enseignant', 'parent', 'eleve'},
    'secretaire': {'directeur', 'comptable', 'surveillant', 'enseignant', 'parent'},
    'comptable': {'directeur', 'secretaire', 'parent'},
    'surveillant': {'directeur', 'secretaire', 'enseignant', 'eleve', 'parent'},
    'enseignant': {'directeur', 'secretaire', 'surveillant', 'parent', 'eleve'},
    'eleve': {'enseignant', 'surveillant'},
    'parent': {'directeur', 'secretaire', 'comptable', 'enseignant', 'surveillant'},
}


def _teacher_student_ids(user):
    teacher = get_linked_teacher(user)
    if not teacher:
        return set()
    from academics.models import SubjectAssignment, ClassRoom
    from timetable.models import TimetableEntry
    classroom_ids = set(
        SubjectAssignment.objects.filter(teacher=teacher).values_list('classroom_id', flat=True)
    )
    classroom_ids |= set(ClassRoom.objects.filter(main_teacher=teacher).values_list('id', flat=True))
    classroom_ids |= set(
        TimetableEntry.objects.filter(teacher=teacher).values_list('classroom_id', flat=True)
    )
    if not classroom_ids:
        return set()
    return set(
        Enrollment.objects.filter(classroom_id__in=classroom_ids, is_active=True)
        .values_list('student_id', flat=True)
    )


def _student_teacher_ids(student):
    if not student:
        return set()
    classroom_ids = list(
        Enrollment.objects.filter(student=student, is_active=True).values_list('classroom_id', flat=True)
    )
    if not classroom_ids:
        return set()
    from academics.models import ClassRoom, SubjectAssignment
    from timetable.models import TimetableEntry
    ids = set(
        SubjectAssignment.objects.filter(classroom_id__in=classroom_ids)
        .values_list('teacher__user_id', flat=True)
    )
    ids |= set(
        ClassRoom.objects.filter(id__in=classroom_ids, main_teacher__user__isnull=False)
        .values_list('main_teacher__user_id', flat=True)
    )
    # Les affectations ne sont pas toujours renseignées : les cours planifiés
    # sont aussi une source fiable pour trouver les professeurs de la classe.
    ids |= set(
        TimetableEntry.objects.filter(
            classroom_id__in=classroom_ids, teacher__user__isnull=False
        ).values_list('teacher__user_id', flat=True)
    )
    return {x for x in ids if x}


def _parent_user_ids(student_ids):
    if not student_ids:
        return set()
    return {
        ps.parent.user_id for ps in ParentStudent.objects.filter(
            student_id__in=student_ids
        ).select_related('parent') if ps.parent and ps.parent.user_id
    }


def allowed_recipient_ids(user):
    """IDs des utilisateurs que `user` a le droit de contacter."""
    if not user or not getattr(user, 'is_authenticated', False):
        return set()
    role = get_role(user)
    if not role:
        return set()

    roles = ROLE_RULES.get(role, set())
    # On normalise le rôle de chaque compte (gère les anciennes valeurs
    # 'admin' / 'comptable' stockées en base et les superutilisateurs).
    allowed = set()
    for other in User.objects.filter(is_active=True).exclude(pk=user.pk).select_related('profile'):
        if get_role(other) in roles:
            allowed.add(other.pk)

    if role == 'enseignant':
        student_ids = _teacher_student_ids(user)
        allowed |= student_ids and set(
            User.objects.filter(is_active=True, student__id__in=student_ids)
            .values_list('id', flat=True)
        ) or set()
        allowed |= _parent_user_ids(student_ids)

    elif role == 'eleve':
        student = getattr(user, 'student', None)
        allowed |= _student_teacher_ids(student)
        # Le surveillant est déjà inclus par les règles de rôle.

    elif role == 'parent':
        parent = get_linked_parent(user)
        children = get_parent_students(user)
        child_ids = list(children.values_list('id', flat=True))
        for child in children:
            allowed |= _student_teacher_ids(child)
        # Sécurité : un parent ne contacte que les profs de SES enfants.

    return {i for i in allowed if i != user.pk}


def allowed_recipients(user):
    """Queryset ordonné des destinataires autorisés."""
    return User.objects.filter(id__in=allowed_recipient_ids(user)).order_by(
        'last_name', 'first_name', 'username'
    )


def can_message(sender, recipient):
    if not sender or not recipient or not getattr(recipient, 'pk', None):
        return False
    if sender.pk == recipient.pk:
        return False
    if not getattr(sender, 'is_active', False) or not getattr(recipient, 'is_active', False):
        return False
    role = get_role(sender)
    if role == 'directeur' or getattr(sender, 'is_superuser', False):
        return True
    return recipient.pk in allowed_recipient_ids(sender)
