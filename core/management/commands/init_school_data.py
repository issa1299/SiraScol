"""
python manage.py init_school_data

Évaluations :
- 1ère → 5ème : Composition chaque mois (périodes type Mois)
- 6ème → 12ème : Devoir + Composition / examen de trimestre (périodes Trimestre 1, 2, 3)
"""
from datetime import date

from django.core.management.base import BaseCommand
from academics.models import Cycle, Level, AcademicYear
from grades.models import AssessmentType, Period


class Command(BaseCommand):
    help = "Initialise cycles, niveaux, types d'évaluation et périodes (mois + trimestres)"

    def handle(self, *args, **options):
        # --- Cycles & Niveaux ---
        cycles_data = [
            {'name': '1er cycle', 'code': 'primaire', 'order': 1},
            {'name': '2ème cycle', 'code': 'secondaire', 'order': 2},
            {'name': 'Lycée', 'code': 'lycee', 'order': 3},
        ]
        levels_data = {
            'primaire': [
                ('1ère année', 1), ('2ème année', 2), ('3ème année', 3),
                ('4ème année', 4), ('5ème année', 5), ('6ème année', 6),
            ],
            'secondaire': [
                ('7ème année', 1), ('8ème année', 2), ('9ème année', 3),
            ],
            'lycee': [
                ('10ème année', 1), ('11ème année', 2), ('12ème année', 3),
            ],
        }

        for cdata in cycles_data:
            cycle, created = Cycle.objects.get_or_create(
                code=cdata['code'],
                defaults={'name': cdata['name'], 'order': cdata['order']},
            )
            if not created and (cycle.name != cdata['name'] or cycle.order != cdata['order']):
                cycle.name = cdata['name']
                cycle.order = cdata['order']
                cycle.save(update_fields=['name', 'order'])
            self.stdout.write(f"  Cycle {cycle.name} ({'créé' if created else 'mis à jour'})")
            for level_name, order in levels_data.get(cdata['code'], []):
                Level.objects.get_or_create(
                    name=level_name, cycle=cycle, defaults={'order': order}
                )
                self.stdout.write(f"    → {level_name}")

        # --- Année scolaire courante ---
        today = date.today()
        # Année scolaire type sept N → juillet N+1
        if today.month >= 9:
            y1, y2 = today.year, today.year + 1
        else:
            y1, y2 = today.year - 1, today.year
        year_name = f'{y1}-{y2}'
        academic_year, created = AcademicYear.objects.get_or_create(
            name=year_name,
            defaults={
                'start_date': date(y1, 9, 1),
                'end_date': date(y2, 7, 31),
                'is_current': True,
            },
        )
        if not academic_year.is_current:
            AcademicYear.objects.exclude(pk=academic_year.pk).update(is_current=False)
            academic_year.is_current = True
            academic_year.save(update_fields=['is_current'])
        self.stdout.write(f"\n  Année scolaire : {academic_year.name}")

        # --- Périodes PRIMAIRE : mois (compositions mensuelles) ---
        self.stdout.write('\nPériodes PRIMAIRE (compositions chaque mois) :')
        months = [
            (1, 'Septembre', date(y1, 9, 1), date(y1, 9, 30)),
            (2, 'Octobre', date(y1, 10, 1), date(y1, 10, 31)),
            (3, 'Novembre', date(y1, 11, 1), date(y1, 11, 30)),
            (4, 'Décembre', date(y1, 12, 1), date(y1, 12, 31)),
            (5, 'Janvier', date(y2, 1, 1), date(y2, 1, 31)),
            (6, 'Février', date(y2, 2, 1), date(y2, 2, 28)),
            (7, 'Mars', date(y2, 3, 1), date(y2, 3, 31)),
            (8, 'Avril', date(y2, 4, 1), date(y2, 4, 30)),
            (9, 'Mai', date(y2, 5, 1), date(y2, 5, 31)),
            (10, 'Juin', date(y2, 6, 1), date(y2, 6, 30)),
        ]
        for order, name, start, end in months:
            p, created = Period.objects.get_or_create(
                name=name,
                academic_year=academic_year,
                defaults={
                    'period_type': 'mois',
                    'start_date': start,
                    'end_date': end,
                    'order': order,
                    'is_active': True,
                },
            )
            if not created and p.period_type != 'mois':
                p.period_type = 'mois'
                p.save(update_fields=['period_type'])
            self.stdout.write(f"  ✓ {name} ({'créé' if created else 'existant'})")

        # --- Périodes SECONDAIRE / LYCÉE : 3 trimestres ---
        self.stdout.write('\nPériodes SECONDAIRE / LYCÉE (1er, 2e, 3e trimestre) :')
        trimesters = [
            (11, '1er Trimestre', date(y1, 9, 1), date(y1, 12, 20)),
            (12, '2e Trimestre', date(y2, 1, 5), date(y2, 3, 31)),
            (13, '3e Trimestre', date(y2, 4, 1), date(y2, 6, 30)),
        ]
        for order, name, start, end in trimesters:
            p, created = Period.objects.get_or_create(
                name=name,
                academic_year=academic_year,
                defaults={
                    'period_type': 'trimestre',
                    'start_date': start,
                    'end_date': end,
                    'order': order,
                    'is_active': True,
                },
            )
            if not created and p.period_type != 'trimestre':
                p.period_type = 'trimestre'
                p.save(update_fields=['period_type'])
            self.stdout.write(f"  ✓ {name} ({'créé' if created else 'existant'})")

        # --- Types d'évaluation ---
        self.stdout.write("\nTypes d'évaluation :")
        for code, name, weight, desc in [
            ('composition', 'Composition', 2.0,
             'Composition mensuelle (primaire) ou de période (secondaire/lycée)'),
            ('devoir', 'Devoir', 1.0, 'Devoir de classe (6ème à 12ème) → Note de classe'),
            ('trimestre', 'Examen trimestriel', 3.0,
             'Examen de fin de trimestre (6ème à 12ème) → Note de composition'),
        ]:
            at, created = AssessmentType.objects.get_or_create(
                code=code,
                defaults={'name': name, 'weight': weight, 'description': desc},
            )
            if created or not at.cycles.exists():
                at.cycles.set(Cycle.objects.all())
            self.stdout.write(f"  ✓ {name}")

        self.stdout.write(self.style.SUCCESS(
            '\n✅ Initialisation terminée.\n\n'
            'Bulletins :\n'
            '  • 1er cycle (1ère–5ème) : composition chaque mois\n'
            '  • 2ème cycle (7ème–9ème) : trimestres\n'
            '  • Lycée (10ème–12ème) : trimestres + séries\n'
        ))
