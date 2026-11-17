
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Désactive le mode maintenance"

    def handle(self, *args, **options):
        from core.models import SchoolSettings
        s = SchoolSettings.get_solo()
        s.maintenance_mode = False
        s.save(update_fields=["maintenance_mode"])
        self.stdout.write(self.style.SUCCESS("Mode maintenance désactivé."))
