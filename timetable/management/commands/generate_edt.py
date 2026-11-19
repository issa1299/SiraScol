"""Génère une grille d'emploi du temps de base, classe par classe."""

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q, Count

from academics.models import AcademicYear, ClassRoom
from core.year_context import get_selected_year
from timetable.edt_generator import DEFAULT_DAYS, generate_for_class


class Command(BaseCommand):
    help = "Remplit les créneaux vides avec une grille de base (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument('--class', dest='classroom', default='',
                            help="Une classe précise (ex. 1ère A)")
        parser.add_argument('--year', dest='year', default='',
                            help="Année scolaire (ex. 2026-2027). Défaut : année courante")
        parser.add_argument('--all', action='store_true',
                            help="Traiter toutes les classes de l'année")
        parser.add_argument('--with-students', action='store_true',
                            help="Traiter seulement les classes avec élèves (défaut)")
        parser.add_argument('--overwrite', action='store_true',
                            help="Remplacer les créneaux existants")
        parser.add_argument('--saturday', action='store_true',
                            help="Inclure le samedi")

    def handle(self, *args, **opts):
        year = None
        if opts['year']:
            year = AcademicYear.objects.filter(name__iexact=opts['year']).first()
            if not year:
                raise CommandError(f"Année scolaire introuvable : {opts['year']}")
        if year is None:
            year = get_selected_year(None)
        if year is None:
            raise CommandError("Aucune année scolaire configurée.")

        qs = ClassRoom.objects.filter(academic_year=year).select_related(
            'level', 'level__cycle'
        ).annotate(
            n_students=Count('enrollments', filter=Q(enrollments__is_active=True), distinct=True)
        ).order_by('level__cycle__order', 'level__order', 'name')

        if opts['classroom']:
            qs = qs.filter(name__iexact=opts['classroom'])
            if not qs.exists():
                raise CommandError(f"Classe « {opts['classroom']} » introuvable pour {year.name}.")
        elif not opts['all']:
            qs = qs.filter(n_students__gt=0)

        classrooms = list(qs)
        if not classrooms:
            self.stdout.write(self.style.WARNING("Aucune classe à traiter."))
            return

        days = DEFAULT_DAYS + ((6,) if opts['saturday'] else ())
        total_created = total_updated = total_skipped = 0
        errors = []

        for classroom in classrooms:
            try:
                report = generate_for_class(
                    classroom, days=days, overwrite=opts['overwrite']
                )
            except Exception as exc:
                errors.append(f"{classroom.name} : {exc}")
                continue
            total_created += report['created']
            total_updated += report['updated']
            total_skipped += report['skipped']
            self.stdout.write(
                f"  {classroom.name:12} créés={report['created']:3} "
                f"modifiés={report['updated']:3} ignorés={report['skipped']:3}"
            )

        self.stdout.write(self.style.SUCCESS(
            f"\n{year.name} — {len(classrooms)} classe(s) traitée(s) : "
            f"{total_created} cours créés, {total_updated} modifiés, {total_skipped} ignorés."
        ))
        for err in errors:
            self.stdout.write(self.style.ERROR(f"  Erreur : {err}"))
        if errors:
            raise CommandError(f"{len(errors)} classe(s) en erreur.")
