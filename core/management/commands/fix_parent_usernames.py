# -*- coding: utf-8 -*-
"""Remplace les identifiants parents « téléphone » par « prénom.nom ».

Les comptes concernés sont ceux dont l'identifiant est exactement le téléphone
slugifié (ex. ``76.01.01.01.07``). Le mot de passe est réinitialisé au nouvel
identifiant et l'obligation de le changer est remise en place.

Usage :
    python manage.py fix_parent_usernames
"""
from django.core.management.base import BaseCommand

from core.account_sync import _slug, _unique_username


class Command(BaseCommand):
    help = 'Identifiants parents : téléphone → prénom.nom'

    def handle(self, *args, **options):
        from accounts.models import Profile
        from students.models import Parent

        changed = 0
        for parent in Parent.objects.filter(user__isnull=False).select_related('user'):
            phone = (parent.phone or '').strip()
            if not phone or parent.user.username != _slug(phone):
                continue
            new_username = _unique_username(
                _slug(f'{parent.first_name}.{parent.last_name}') or 'parent'
            )
            if new_username == parent.user.username:
                continue
            user = parent.user
            old_username = user.username
            user.username = new_username
            user.set_password(new_username)
            user.save()
            Profile.objects.filter(user=user).update(must_change_password=True)
            changed += 1
            self.stdout.write(f'  {old_username} → {new_username}')

        self.stdout.write(self.style.SUCCESS(
            f'{changed} identifiant(s) parent migré(s) vers prénom.nom.'
        ))
