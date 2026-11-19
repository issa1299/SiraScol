"""Diagnostic des destinataires autorisés dans la messagerie privée."""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User

from core.messaging import allowed_recipients
from core.permissions import get_role


class Command(BaseCommand):
    help = "Affiche, pour chaque utilisateur, ses rôles et ses destinataires autorisés."

    def add_arguments(self, parser):
        parser.add_argument('--user', dest='username', default='',
                            help="Afficher uniquement cet identifiant")

    def handle(self, *args, **opts):
        qs = User.objects.filter(is_active=True).select_related('profile').order_by('username')
        if opts['username']:
            qs = qs.filter(username__icontains=opts['username'])
        for u in qs:
            recipients = list(allowed_recipients(u))
            self.stdout.write(
                f"{u.username:20} stocké={getattr(getattr(u, 'profile', None), 'role', '—'):12} "
                f"actif={get_role(u) or '—':12} destinataires={len(recipients)}"
            )
            for r in recipients[:12]:
                self.stdout.write(f"    - {r.username} ({get_role(r) or '—'})")
            if len(recipients) > 12:
                self.stdout.write(f"    … et {len(recipients) - 12} autre(s)")
