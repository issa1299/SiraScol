from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from academics.models import AcademicYear, ClassRoom
from core.year_context import get_selected_year
from students.import_service import import_rows, parse_file, sample_csv


class Command(BaseCommand):
    help = "Importe des élèves depuis un CSV ou un classeur Excel (comptes et inscriptions inclus)."

    def add_arguments(self, parser):
        parser.add_argument('file', type=str, help='Chemin du fichier .csv ou .xlsx')
        parser.add_argument('--class', dest='classroom', required=True,
                            help="Classe obligatoire : tous les élèves du fichier y seront inscrits")
        parser.add_argument('--year', dest='year', default='',
                            help="Année scolaire (ex. 2026-2027). Par défaut : année courante")
        parser.add_argument('--no-parents', action='store_true', help="Ne pas créer les parents")
        parser.add_argument('--no-invoices', action='store_true', help="Ne pas créer les factures")
        parser.add_argument('--sample', action='store_true', help='Afficher le modèle CSV et quitter')

    def handle(self, *args, **opts):
        if opts['sample']:
            self.stdout.write(sample_csv())
            return

        path = Path(opts['file'])
        if not path.exists():
            raise CommandError(f"Fichier introuvable : {path}")

        with path.open('rb') as fh:
            rows = parse_file(fh, path.name)
        if not rows:
            raise CommandError("Aucune ligne d'élève trouvée dans le fichier.")

        year = None
        if opts['year']:
            year = AcademicYear.objects.filter(name__iexact=opts['year']).first()
            if not year:
                raise CommandError(f"Année scolaire introuvable : {opts['year']}")
        if year is None:
            year = get_selected_year(None)

        classroom = ClassRoom.objects.filter(
            academic_year=year, name__iexact=opts['classroom']
        ).select_related('level', 'academic_year').first()
        if not classroom:
            raise CommandError(
                f"Classe « {opts['classroom']} » introuvable pour {year.name if year else 'l’année courante'}."
            )

        report = import_rows(
            rows,
            classroom=classroom,
            create_parents=not opts['no_parents'],
            create_invoices=not opts['no_invoices'],
        )

        self.stdout.write(self.style.SUCCESS(
            f"Import {classroom.name} ({classroom.academic_year.name}) : "
            f"{report['created']} créé(s), {report['exists']} existant(s), "
            f"{len(report['errors'])} erreur(s)."
        ))
        for cred in report['credentials']:
            self.stdout.write(
                f"  {cred['type']:6} | {cred['name']:30} | "
                f"{cred['username']:15} / {cred['password']}"
            )
        for err in report['errors']:
            self.stdout.write(self.style.ERROR(f"  Ligne {err['line']} : {err['message']}"))
        if report['errors']:
            raise CommandError(f"{len(report['errors'])} ligne(s) en erreur — voir ci-dessus.")
