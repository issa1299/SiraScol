"""Helpers pour créer des notifications internes sans dépendance des portails."""

from django.contrib.auth.models import User

from .models import Notification


def notify(user, title, message='', category='info', link=''):
    if user is None or not getattr(user, 'pk', None):
        return None
    return Notification.objects.create(
        user=user, title=title, message=message,
        category=category, link=link,
    )


def notify_student_and_parents(student, title, message='', category='info', link=''):
    if student is None:
        return
    users = []
    if student.user_id:
        users.append(student.user)
    from students.models import ParentStudent
    for ps in ParentStudent.objects.filter(student=student).select_related('parent__user'):
        parent = ps.parent
        if parent and parent.user_id:
            users.append(parent.user)
    for user in set(users):
        notify(user, title, message, category, link)


def notify_role(role, title, message='', category='info', link=''):
    """Notifie tous les utilisateurs ayant un rôle donné (via leur Profile)."""
    qs = User.objects.filter(profile__role=role, is_active=True)
    for user in qs:
        notify(user, title, message, category, link)
