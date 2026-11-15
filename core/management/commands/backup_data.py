"""
Sauvegarde db.sqlite3 + dossier media dans backups/
Usage:
  python manage.py backup_data
  python manage.py backup_data --keep 10
"""
from datetime import datetime
from pathlib import Path
import shutil
import zipfile

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Sauvegarde la base SQLite et les fichiers media'

    def add_arguments(self, parser):
        parser.add_argument('--keep', type=int, default=15, help='Nombre de sauvegardes à conserver')

    def handle(self, *args, **options):
        backup_dir = Path(getattr(settings, 'BACKUP_DIR', settings.BASE_DIR / 'backups'))
        backup_dir.mkdir(parents=True, exist_ok=True)

        stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        zip_path = backup_dir / f'sirascol_backup_{stamp}.zip'

        db_path = Path(settings.DATABASES['default']['NAME'])
        media_root = Path(settings.MEDIA_ROOT)

        with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
            if db_path.exists():
                zf.write(db_path, arcname='db.sqlite3')
                self.stdout.write(f'  + base: {db_path.name}')
            if media_root.exists():
                for f in media_root.rglob('*'):
                    if f.is_file():
                        zf.write(f, arcname=str(Path('media') / f.relative_to(media_root)))
                self.stdout.write(f'  + media: {media_root}')

        self.stdout.write(self.style.SUCCESS(f'Sauvegarde créée: {zip_path}'))

        # Nettoyage anciennes sauvegardes
        keep = options['keep']
        archives = sorted(backup_dir.glob('sirascol_backup_*.zip'), key=lambda p: p.stat().st_mtime, reverse=True)
        for old in archives[keep:]:
            old.unlink(missing_ok=True)
            self.stdout.write(f'  - supprimé: {old.name}')
