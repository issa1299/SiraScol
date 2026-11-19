"""Contrôle de l'association entre les classes et leur emploi du temps."""

from django.core.management.base import BaseCommand
from django.db.models import Count, Q

from academics.models import ClassRoom
from timetable.models import TimetableEntry, TimeSlot


class Command(BaseCommand):
    help = "Vérifie que chaque classe (surtout celles avec des élèves) a un emploi du temps."

    def add_arguments(self, parser):
        parser.add_argument(
            '--year', dest='year', default='',
            help="Année scolaire (ex. 2026-2027). Par défaut : toutes",
        )

    def handle(self, *args, **opts):
        classrooms = ClassRoom.objects.select_related('academic_year', 'level', 'level__cycle').annotate(
            n_entries=Count('timetable_entries', distinct=True),
            n_students=Count('enrollments', filter=Q(enrollments__is_active=True), distinct=True),
        ).order_by('academic_year__name', 'level__cycle__order', 'level__order', 'name')

        if opts['year']:
            classrooms = classrooms.filter(academic_year__name__iexact=opts['year'])

        slots = TimeSlot.objects.count()
        total_entries = TimetableEntry.objects.count()
        self.stdout.write(f"Créneaux définis : {slots}")
        self.stdout.write(f"Entrées EDT au total : {total_entries}")
        self.stdout.write(f"Classes contrôlées : {classrooms.count()}\n")

        empty_with_students = []
        empty_without_students = []
        for c in classrooms:
            status = self.style.SUCCESS('OK') if c.n_entries else self.style.WARNING('VIDE')
            line = (
                f"  {c.academic_year.name:12} {c.name:10} "
                f"{getattr(c.level, 'name', '') or '':22} "
                f"cours={c.n_entries:3} élèves={c.n_students:3} {status}"
            )
            self.stdout.write(line)
            if not c.n_entries:
                if c.n_students:
                    empty_with_students.append(c)
                else:
                    empty_without_students.append(c)

        self.stdout.write('')
        missing_subject = TimetableEntry.objects.filter(subject__isnull=True).count()
        missing_teacher = TimetableEntry.objects.filter(teacher__isnull=True).count()
        missing_room = TimetableEntry.objects.filter(room__isnull=True).count()
        self.stdout.write(f"Entrées sans matière : {missing_subject}")
        self.stdout.write(f"Entrées sans enseignant : {missing_teacher}")
        self.stdout.write(f"Entrées sans salle : {missing_room}")

        if empty_with_students:
            self.stdout.write(self.style.ERROR('\nClasses avec élèves SANS emploi du temps :'))
            for c in empty_with_students:
                self.stdout.write(f"  - {c.name} ({c.academic_year.name}) — {c.n_students} élève(s)")
            self.stdout.write(
                self.style.WARNING(
                    "\nCes élèves verront un emploi du temps vide dans leur Espace Élève. "
                    "Renseignez leur emploi du temps dans /emploi-du-temps/."
                )
            )
        else:
            self.stdout.write(self.style.SUCCESS('\nToutes les classes avec élèves ont un emploi du temps.'))

        if empty_without_students:
            self.stdout.write(
                self.style.WARNING(
                    f"\n{len(empty_without_students)} classe(s) sans élèves ni emploi du temps "
                    "(normal si elles ne sont pas encore utilisées)."
                )
            )
