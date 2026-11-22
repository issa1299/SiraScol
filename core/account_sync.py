"""
Création automatique de comptes de connexion pour
enseignants, élèves et parents de l'école.
"""
import re
import unicodedata
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


def _slug(text, fallback='user'):
    if not text:
        return fallback
    text = unicodedata.normalize('NFKD', str(text))
    text = text.encode('ascii', 'ignore').decode('ascii')
    text = re.sub(r'[^a-zA-Z0-9]+', '.', text.lower()).strip('.')
    return text or fallback


def _unique_username(base):
    base = (base or 'user')[:40]
    username = base
    n = 1
    while User.objects.filter(username=username).exists():
        username = f'{base}{n}'
        n += 1
        if n > 9999:
            break
    return username


def _role_for_teacher(teacher):
    """Map catégorie/fonction personnel → rôle Profile."""
    cat = (getattr(teacher, 'category', None) or 'enseignant').lower()
    fn = (getattr(teacher, 'function', None) or '').lower()
    if cat == 'admin':
        if 'directeur' in fn and 'adjoint' not in fn:
            return 'directeur'
        if 'comptab' in fn:
            return 'comptable'
        if 'secr' in fn:
            return 'secretaire'
        return 'admin'
    if cat == 'service':
        return 'admin'  # accès limité via permissions plus tard
    return 'enseignant'


def ensure_user_for_teacher(teacher):
    from accounts.models import Profile

    role = _role_for_teacher(teacher)
    if teacher.user_id:
        user = teacher.user
        user.first_name = teacher.first_name or user.first_name
        user.last_name = teacher.last_name or user.last_name
        if teacher.email:
            user.email = teacher.email
        user.is_active = bool(teacher.is_active)
        user.save()
        Profile.objects.update_or_create(
            user=user, defaults={'role': role, 'phone': teacher.phone or ''}
        )
        return user, False, None

    base = _slug(teacher.matricule) if teacher.matricule else _slug(
        f'{teacher.last_name}.{teacher.first_name}'
    )
    username = _unique_username(base or 'ens')
    raw_password = (teacher.matricule or username).strip() or 'enseignant'
    user = User.objects.create_user(
        username=username,
        password=raw_password,
        first_name=teacher.first_name or '',
        last_name=teacher.last_name or '',
        email=teacher.email or '',
        is_active=bool(teacher.is_active),
    )
    Profile.objects.update_or_create(
        user=user, defaults={
            'role': role, 'phone': teacher.phone or '',
            'must_change_password': True,
        }
    )
    type(teacher).objects.filter(pk=teacher.pk).update(user=user)
    teacher.user = user
    return user, True, raw_password


def ensure_user_for_student(student):
    from accounts.models import Profile

    if student.user_id:
        user = student.user
        user.first_name = student.first_name or user.first_name
        user.last_name = student.last_name or user.last_name
        user.is_active = (getattr(student, 'status', 'actif') == 'actif')
        user.save()
        Profile.objects.update_or_create(user=user, defaults={'role': 'eleve'})
        return user, False, None

    mat = (student.matricule or '').strip()
    base = _slug(mat) if mat else _slug(f'{student.last_name}.{student.first_name}')
    username = _unique_username(base or 'eleve')
    raw_password = mat or username
    user = User.objects.create_user(
        username=username,
        password=raw_password,
        first_name=student.first_name or '',
        last_name=student.last_name or '',
        is_active=True,
    )
    Profile.objects.update_or_create(user=user, defaults={
        'role': 'eleve', 'must_change_password': True,
    })
    type(student).objects.filter(pk=student.pk).update(user=user)
    student.user = user
    return user, True, raw_password


def ensure_user_for_parent(parent):
    from accounts.models import Profile

    if parent.user_id:
        user = parent.user
        user.first_name = parent.first_name or user.first_name
        user.last_name = parent.last_name or user.last_name
        if getattr(parent, 'email', None):
            user.email = parent.email
        user.save()
        Profile.objects.update_or_create(
            user=user,
            defaults={'role': 'parent', 'phone': getattr(parent, 'phone', '') or ''},
        )
        return user, False, None

    phone = (getattr(parent, 'phone', None) or '').strip()
    base = _slug(phone) if phone and len(phone) >= 6 else _slug(
        f'{parent.last_name}.{parent.first_name}'
    )
    username = _unique_username(base or 'parent')
    raw_password = phone if len(phone) >= 4 else username
    user = User.objects.create_user(
        username=username,
        password=raw_password,
        first_name=parent.first_name or '',
        last_name=parent.last_name or '',
        email=getattr(parent, 'email', '') or '',
        is_active=True,
    )
    Profile.objects.update_or_create(user=user, defaults={
        'role': 'parent', 'phone': phone, 'must_change_password': True,
    })
    type(parent).objects.filter(pk=parent.pk).update(user=user)
    parent.user = user
    return user, True, raw_password


def connect_signals():
    from teachers.models import Teacher
    from students.models import Student, Parent

    @receiver(post_save, sender=Teacher, dispatch_uid='auto_user_teacher')
    def _teacher_user(sender, instance, **kwargs):
        if kwargs.get('raw'):
            return
        try:
            ensure_user_for_teacher(instance)
        except Exception:
            pass

    @receiver(post_save, sender=Student, dispatch_uid='auto_user_student')
    def _student_user(sender, instance, **kwargs):
        if kwargs.get('raw'):
            return
        try:
            ensure_user_for_student(instance)
        except Exception:
            pass

    @receiver(post_save, sender=Parent, dispatch_uid='auto_user_parent')
    def _parent_user(sender, instance, **kwargs):
        if kwargs.get('raw'):
            return
        try:
            ensure_user_for_parent(instance)
        except Exception:
            pass
