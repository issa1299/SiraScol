from datetime import date

from django.db import migrations, models


def clear_invalid_dob(apps, schema_editor):
    """Les dates de naissance futures ou donnant moins de 3 ans sont invalides.

    Elles proviennent de données de test et ne doivent pas apparaître sur les
    cartes scolaires. Le secrétaire pourra saisir la vraie date dans la fiche.
    """
    Student = apps.get_model('students', 'Student')
    today = date.today()
    try:
        limit = today.replace(year=today.year - 3)
    except ValueError:  # 29 février
        limit = today.replace(year=today.year - 3, day=28)
    Student.objects.filter(date_of_birth__gt=limit).update(date_of_birth=None)


class Migration(migrations.Migration):

    dependencies = [
        ('students', '0002_enrollment_end_status'),
    ]

    operations = [
        migrations.AlterField(
            model_name='student',
            name='date_of_birth',
            field=models.DateField(
                blank=True, null=True, verbose_name='Date de naissance'
            ),
        ),
        migrations.RunPython(clear_invalid_dob, migrations.RunPython.noop),
    ]
