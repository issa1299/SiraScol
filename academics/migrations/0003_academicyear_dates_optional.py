
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('academics', '0002_classsubject'),
    ]

    operations = [
        migrations.AlterField(
            model_name='academicyear',
            name='start_date',
            field=models.DateField(blank=True, null=True, verbose_name='Date de début'),
        ),
        migrations.AlterField(
            model_name='academicyear',
            name='end_date',
            field=models.DateField(blank=True, null=True, verbose_name='Date de fin'),
        ),
        migrations.AlterModelOptions(
            name='academicyear',
            options={'ordering': ['-is_current', '-start_date', '-id'], 'verbose_name': 'Année scolaire', 'verbose_name_plural': 'Années scolaires'},
        ),
    ]
