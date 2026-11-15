from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_card_template'),
    ]

    operations = [
        migrations.AlterField(
            model_name='schoolsettings',
            name='card_template',
            field=models.CharField(
                choices=[
                    ('official', 'Officiel (fond blanc)'),
                    ('modern', 'Moderne (bleu nuit)'),
                    ('classic', 'Classique (bleu roi)'),
                    ('gold', 'Prestige (or & noir)'),
                    ('green', 'Émeraude'),
                    ('burgundy', 'Bordeaux'),
                ],
                default='official',
                max_length=20,
                verbose_name='Modèle de carte scolaire',
            ),
        ),
    ]
