from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('students', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='enrollment',
            name='end_status',
            field=models.CharField(
                choices=[
                    ('en_cours', 'En cours'),
                    ('promoted', 'Admis (passe)'),
                    ('repeated', 'Redouble'),
                    ('transferred', 'Transféré'),
                    ('abandoned', 'Abandon / Sortie'),
                ],
                default='en_cours',
                max_length=20,
                verbose_name="Décision de fin d'année",
            ),
        ),
        migrations.AddField(
            model_name='enrollment',
            name='end_average',
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=5, null=True,
                verbose_name='Moyenne annuelle',
            ),
        ),
        migrations.AddField(
            model_name='enrollment',
            name='end_note',
            field=models.CharField(blank=True, max_length=255, verbose_name='Observation'),
        ),
    ]
