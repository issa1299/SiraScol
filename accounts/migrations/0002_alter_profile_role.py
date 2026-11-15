from django.db import migrations, models


class Migration(migrations.Migration):
    """Aligné avec les rôles étendus (directeur, secrétaire, etc.)."""

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='profile',
            name='role',
            field=models.CharField(
                choices=[
                    ('admin', 'Administrateur'),
                    ('directeur', 'Directeur'),
                    ('secretaire', 'Secrétaire'),
                    ('comptable', 'Comptable'),
                    ('enseignant', 'Enseignant'),
                    ('parent', 'Parent'),
                    ('eleve', 'Élève'),
                ],
                default='eleve',
                max_length=20,
            ),
        ),
    ]
