# -*- coding: utf-8 -*-
"""
SiraScol — Rôles & permissions (côté serveur).

5 rôles métier :
  1. directeur  — accès complet (admin technique inclus via is_superuser ou rôle admin)
  2. secretaire — dossiers élèves, paiements, reçus, impayés (PAS notes, PAS config)
  3. enseignant — uniquement ses classes / matières
  4. eleve      — lecture seule de ses données
  5. parent     — uniquement ses enfants

Compatibilité : 'admin' → droits directeur ; 'comptable' → droits secrétaire (finance renforcée).
"""
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

# Rôles affichés
ROLE_LABELS = {
    'directeur': 'Directeur',
    'secretaire': 'Secrétaire / Comptable',
    'enseignant': 'Enseignant',
    'parent': 'Parent',
    'eleve': 'Élève',
    # aliases historiques
    'admin': 'Administrateur',
    'comptable': 'Comptable',
}

# Rôles « canoniques » (les 5 demandés)
CANONICAL_ROLES = ('directeur', 'secretaire', 'enseignant', 'parent', 'eleve')

# Alias → rôle canonique
ROLE_ALIASES = {
    'admin': 'directeur',
    'comptable': 'secretaire',
}

# ── Matrice de permissions ───────────────────────────────────────────────────
# Format : permission → liste de rôles canoniques autorisés
# directeur a toujours accès via can() (sauf si on veut restreindre plus tard)

PERMISSIONS = {
    # Navigation
    'nav.dashboard': ['directeur', 'secretaire', 'enseignant', 'parent', 'eleve'],
    'nav.students': ['directeur', 'secretaire', 'enseignant', 'parent'],
    'nav.teachers': ['directeur', 'secretaire'],
    'nav.classrooms': ['directeur', 'secretaire', 'enseignant'],
    'nav.parents': ['directeur', 'secretaire'],
    'nav.promotion': ['directeur'],
    'nav.grades': ['directeur', 'enseignant', 'parent', 'eleve'],  # PAS secrétaire
    'nav.bulletins': ['directeur', 'enseignant', 'parent', 'eleve'],  # PAS secrétaire
    'nav.finance': ['directeur', 'secretaire', 'parent'],
    'nav.attendance': ['directeur', 'enseignant', 'parent', 'eleve'],
    'nav.timetable': ['directeur', 'enseignant', 'parent', 'eleve'],
    'nav.announcements': ['directeur', 'secretaire', 'enseignant', 'parent', 'eleve'],
    'nav.messages': ['directeur', 'secretaire', 'enseignant', 'parent', 'eleve'],
    'nav.config': ['directeur'],
    'nav.settings': ['directeur'],
    'nav.reports': ['directeur', 'secretaire'],
    'nav.admin_tech': ['directeur'],
    'nav.cards': ['directeur', 'secretaire'],
    'nav.cahier': ['directeur', 'enseignant'],

    # Élèves
    'students.view': ['directeur', 'secretaire', 'enseignant', 'parent'],
    'students.create': ['directeur', 'secretaire'],
    'students.edit': ['directeur', 'secretaire'],
    'students.delete': ['directeur'],

    # Personnel
    'personnel.dashboard': ['directeur', 'secretaire'],
    'personnel.list': ['directeur', 'secretaire'],
    'personnel.view': ['directeur', 'secretaire', 'enseignant'],
    'personnel.create': ['directeur', 'secretaire'],
    'personnel.edit': ['directeur', 'secretaire'],
    'personnel.delete': ['directeur'],
    'personnel.salaries': ['directeur', 'secretaire'],
    'personnel.contracts': ['directeur', 'secretaire'],
    'personnel.assign': ['directeur'],

    # Classes / année / matières / coefficients
    'academics.year': ['directeur'],
    'academics.classes': ['directeur', 'secretaire'],
    'academics.subjects': ['directeur'],
    'academics.coefficients': ['directeur'],
    'academics.assignments': ['directeur'],

    # Notes
    'grades.view': ['directeur', 'enseignant', 'parent', 'eleve'],
    'grades.entry': ['directeur', 'enseignant'],
    'grades.validate': ['directeur'],
    'grades.bulletin_view': ['directeur', 'enseignant', 'parent', 'eleve'],
    'grades.bulletin_validate': ['directeur'],

    # Finance
    'finance.view': ['directeur', 'secretaire', 'parent'],
    'finance.pay': ['directeur', 'secretaire'],
    'finance.receipts': ['directeur', 'secretaire'],
    'finance.unpaid': ['directeur', 'secretaire'],
    'finance.fees_config': ['directeur'],
    'finance.stats': ['directeur', 'secretaire'],

    # Présences
    'attendance.view': ['directeur', 'enseignant', 'parent', 'eleve'],
    'attendance.take': ['directeur', 'enseignant'],

    # Emploi du temps
    'timetable.view': ['directeur', 'enseignant', 'parent', 'eleve'],
    'timetable.edit': ['directeur'],

    # Communication
    'announcements.view': ['directeur', 'secretaire', 'enseignant', 'parent', 'eleve'],
    'announcements.publish': ['directeur', 'secretaire', 'enseignant'],
    'messages.send': ['directeur', 'secretaire', 'enseignant', 'parent', 'eleve'],

    # Config / utilisateurs
    'config.users': ['directeur'],
    'config.school': ['directeur'],

    'personnel.presences': ['directeur', 'secretaire'],
    'personnel.documents': ['directeur', 'secretaire'],
    'personnel.reports': ['directeur', 'secretaire'],
    'finance.expenses': ['directeur', 'secretaire'],
    'finance.reports': ['directeur', 'secretaire'],
}



def normalize_role(role):
    """Convertit un rôle stocké en rôle canonique."""
    if not role:
        return None
    role = role.strip().lower()
    return ROLE_ALIASES.get(role, role)


def get_role(user):
    """Rôle canonique de l'utilisateur (None si anonyme)."""
    if not user or not getattr(user, 'is_authenticated', False):
        return None
    if user.is_superuser:
        return 'directeur'
    try:
        raw = user.profile.role
    except Exception:
        return None
    return normalize_role(raw)


def get_role_label(user):
    role = get_role(user)
    return ROLE_LABELS.get(role, role or 'Utilisateur')


def can(user, permission):
    """Vérifie une permission. Directeur (et superuser) = toujours True pour les perms listées ou non."""
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    if user.is_superuser:
        return True
    role = get_role(user)
    if not role:
        return False
    # Directeur = accès complet
    if role == 'directeur':
        return True
    allowed = PERMISSIONS.get(permission)
    if allowed is None:
        # Permission inconnue → refus sauf directeur (déjà géré)
        return False
    return role in allowed


def is_staff_role(user):
    return get_role(user) in ('directeur', 'secretaire')


def is_config_role(user):
    return get_role(user) == 'directeur' or (user and user.is_superuser)


def is_teacher(user):
    return get_role(user) == 'enseignant'


def is_parent(user):
    return get_role(user) == 'parent'


def is_student(user):
    return get_role(user) == 'eleve'


# ── Décorateurs ──────────────────────────────────────────────────────────────

def role_required(*roles):
    """Exige un des rôles (canoniques ou alias). Directeur / superuser toujours OK."""
    normalized = {normalize_role(r) or r for r in roles}

    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            role = get_role(request.user)
            if role == 'directeur' or role in normalized:
                return view_func(request, *args, **kwargs)
            messages.error(request, "Vous n'avez pas l'autorisation d'accéder à cette page.")
            return redirect('core:dashboard')
        return _wrapped
    return decorator


def permission_required(permission):
    """Exige une permission précise (matrice PERMISSIONS)."""
    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if can(request.user, permission):
                return view_func(request, *args, **kwargs)
            messages.error(request, "Accès refusé pour votre rôle.")
            return redirect('core:dashboard')
        return _wrapped
    return decorator


# ── Liens profil métier ──────────────────────────────────────────────────────

def get_linked_teacher(user):
    if not user or not user.is_authenticated:
        return None
    try:
        return user.teacher
    except Exception:
        from teachers.models import Teacher
        return Teacher.objects.filter(user=user).first()


def get_linked_parent(user):
    if not user or not user.is_authenticated:
        return None
    try:
        return user.parent_profile
    except Exception:
        return None


def get_linked_student(user):
    if not user or not user.is_authenticated:
        return None
    try:
        return user.student
    except Exception:
        from students.models import Student
        return Student.objects.filter(user=user).first()


def get_parent_students(user):
    """QuerySet des élèves liés au parent connecté."""
    from students.models import Student, ParentStudent
    parent = get_linked_parent(user)
    if not parent:
        return Student.objects.none()
    ids = ParentStudent.objects.filter(parent=parent).values_list('student_id', flat=True)
    return Student.objects.filter(id__in=ids)


def get_teacher_classrooms(user):
    """Classes de l'enseignant (affectation matières + titulaire)."""
    from academics.models import ClassRoom, SubjectAssignment
    teacher = get_linked_teacher(user)
    if not teacher:
        return ClassRoom.objects.none()
    ids = set(SubjectAssignment.objects.filter(teacher=teacher).values_list('classroom_id', flat=True))
    ids |= set(ClassRoom.objects.filter(main_teacher=teacher).values_list('id', flat=True))
    return ClassRoom.objects.filter(id__in=ids)
