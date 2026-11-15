from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_schoolsettings_stamp'),
    ]

    operations = [
        migrations.AddField(
            model_name='schoolsettings',
            name='card_template',
            field=models.CharField(
                choices=[
                    ('modern', 'Moderne (bleu nuit)'),
                    ('classic', 'Classique (bleu roi)'),
                    ('gold', 'Prestige (or & noir)'),
                    ('green', 'Émeraude'),
                    ('burgundy', 'Bordeaux'),
                ],
                default='modern',
                max_length=20,
                verbose_name='Modèle de carte scolaire',
            ),
        ),
    ]
