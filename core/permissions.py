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
    'secretaire': 'Secrétaire',
    'enseignant': 'Enseignant',
    'parent': 'Parent',
    'eleve': 'Élève',
    # aliases historiques
    'admin': 'Administrateur',
    'comptable': 'Comptable',
}

# Rôles « canoniques » (les 5 demandés)
CANONICAL_ROLES = ('directeur', 'secretaire', 'comptable', 'enseignant', 'parent', 'eleve')

# Alias → rôle canonique (le comptable est désormais un rôle distinct)
ROLE_ALIASES = {
    'admin': 'directeur',
}

# ── Matrice de permissions ───────────────────────────────────────────────────
# Format : permission → liste de rôles canoniques autorisés
# directeur a toujours accès via can() (sauf si on veut restreindre plus tard)

PERMISSIONS = {
    # Navigation
    'nav.dashboard': ['directeur', 'secretaire', 'comptable', 'enseignant', 'parent', 'eleve'],
    'nav.students': ['directeur', 'secretaire', 'enseignant', 'parent'],
    'nav.teachers': ['directeur', 'secretaire'],
    'nav.classrooms': ['directeur', 'secretaire', 'enseignant'],
    'nav.parents': ['directeur', 'secretaire'],
    'nav.promotion': ['directeur'],
    'nav.grades': ['directeur', 'enseignant', 'parent', 'eleve'],  # PAS secrétaire
    'nav.bulletins': ['directeur', 'enseignant', 'parent', 'eleve'],  # PAS secrétaire
    'nav.finance': ['directeur', 'comptable'],
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

    # Devoirs
    'homework.view': ['directeur', 'enseignant', 'eleve'],
    'homework.manage': ['directeur', 'enseignant'],

    # Finance — rôle comptable dédié (le secrétaire ne gère pas les transactions)
    'finance.view': ['directeur', 'comptable'],
    'finance.pay': ['directeur', 'comptable'],
    'finance.receipts': ['directeur', 'comptable'],
    'finance.unpaid': ['directeur', 'comptable'],
    'finance.fees_config': ['directeur', 'comptable'],
    'finance.stats': ['directeur', 'comptable'],
    'finance.expenses': ['directeur', 'comptable'],
    'finance.reports': ['directeur', 'comptable'],

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
}


# ── Groupes de permissions pour la matrice d'administration ─────────────────
PERMISSION_GROUPS = [
    {
        'title': 'Navigation & Menus',
        'items': [
            ('nav.dashboard', 'Tableau de bord'),
            ('nav.students', 'Menu Élèves'),
            ('nav.teachers', 'Menu Personnel / Enseignants'),
            ('nav.classrooms', 'Menu Classes'),
            ('nav.parents', 'Menu Parents'),
            ('nav.promotion', 'Fin d\'année & Passage'),
            ('nav.grades', 'Menu Notes'),
            ('nav.bulletins', 'Menu Bulletins'),
            ('nav.finance', 'Menu Finances'),
            ('nav.attendance', 'Menu Présences & Absences'),
            ('nav.timetable', 'Menu Emploi du temps'),
            ('nav.announcements', 'Menu Annonces'),
            ('nav.messages', 'Menu Messages'),
            ('nav.config', 'Menu Configuration'),
            ('nav.settings', 'Paramètres de l\'établissement'),
            ('nav.reports', 'Rapports & Statistiques'),
            ('nav.cards', 'Cartes scolaires'),
        ],
    },
    {
        'title': 'Gestion des Élèves',
        'items': [
            ('students.view', 'Consulter la liste et fiches élèves'),
            ('students.create', 'Inscrire un nouvel élève'),
            ('students.edit', 'Modifier les informations d\'un élève'),
            ('students.delete', 'Supprimer un élève'),
        ],
    },
    {
        'title': 'Personnel & Enseignants',
        'items': [
            ('personnel.dashboard', 'Tableau de bord personnel'),
            ('personnel.list', 'Consulter la liste du personnel'),
            ('personnel.create', 'Ajouter un membre du personnel'),
            ('personnel.edit', 'Modifier une fiche personnel'),
            ('personnel.delete', 'Supprimer un membre du personnel'),
            ('personnel.salaries', 'Gestion des salaires et paiements'),
            ('personnel.contracts', 'Gestion des contrats de travail'),
            ('personnel.assign', 'Affectation des enseignants aux classes'),
        ],
    },
    {
        'title': 'Structure Scolaire & Matières',
        'items': [
            ('academics.year', 'Gestion des années scolaires'),
            ('academics.classes', 'Gestion des classes'),
            ('academics.subjects', 'Gestion des matières'),
            ('academics.coefficients', 'Configuration des coefficients'),
            ('academics.assignments', 'Affectations des matières'),
        ],
    },
    {
        'title': 'Notes & Évaluations',
        'items': [
            ('grades.view', 'Consulter les notes'),
            ('grades.entry', 'Saisir les notes et évaluations'),
            ('grades.validate', 'Valider et verrouiller les notes'),
            ('grades.bulletin_view', 'Consulter et imprimer les bulletins'),
            ('grades.bulletin_validate', 'Validation définitive des bulletins'),
            ('homework.view', 'Consulter les devoirs'),
            ('homework.manage', 'Publier et gérer les devoirs'),
        ],
    },
    {
        'title': 'Finances & Frais de Scolarité',
        'items': [
            ('finance.view', 'Consulter les finances et factures'),
            ('finance.pay', 'Enregistrer un encaissement / paiement'),
            ('finance.receipts', 'Éditer et imprimer les reçus'),
            ('finance.unpaid', 'Suivi des impayés et relances'),
            ('finance.fees_config', 'Configuration des types de frais'),
            ('finance.expenses', 'Gestion des dépenses de l\'école'),
            ('finance.reports', 'Rapports financiers et état de caisse'),
        ],
    },
    {
        'title': 'Présences & Absences',
        'items': [
            ('attendance.view', 'Consulter les absences et pointages'),
            ('attendance.take', 'Pointer les présences / marquer absent'),
        ],
    },
    {
        'title': 'Emploi du temps',
        'items': [
            ('timetable.view', 'Consulter l\'emploi du temps'),
            ('timetable.edit', 'Modifier et générer les créneaux'),
        ],
    },
    {
        'title': 'Communication',
        'items': [
            ('announcements.view', 'Lire les annonces'),
            ('announcements.publish', 'Publier des annonces officielles'),
            ('messages.send', 'Envoyer et recevoir des messages'),
        ],
    },
    {
        'title': 'Administration & Configuration',
        'items': [
            ('config.users', 'Gestion des utilisateurs et rôles'),
            ('config.school', 'Configuration générale de l\'école'),
        ],
    },
]



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
    return get_role(user) in ('directeur', 'secretaire', 'comptable')


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
