"""
Renomme les cycles selon la terminologie locale :
  Primaire → 1er cycle
  Secondaire → 2ème cycle
  Lycée → Lycée
Usage: python manage.py rename_cycles
"""
from django.core.management.base import BaseCommand
from academics.models import Cycle


class Command(BaseCommand):
    help = "Renomme les cycles en 1er cycle / 2ème cycle / Lycée"

    def handle(self, *args, **options):
        mapping = {
            'primaire': '1er cycle',
            'secondaire': '2ème cycle',
            'lycee': 'Lycée',
        }
        for code, name in mapping.items():
            n = Cycle.objects.filter(code=code).update(name=name)
            if n:
                self.stdout.write(self.style.SUCCESS(f"  {code} → {name}"))
            else:
                # create if missing
                Cycle.objects.get_or_create(code=code, defaults={'name': name, 'order': {'primaire': 1, 'secondaire': 2, 'lycee': 3}.get(code, 9)})
                self.stdout.write(self.style.WARNING(f"  {code} créé ({name})"))
        self.stdout.write(self.style.SUCCESS('Cycles mis à jour.'))
