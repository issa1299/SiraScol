from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_notification'),
    ]

    operations = [
        migrations.AlterField(
            model_name='schoolsettings',
            name='name',
            field=models.CharField(
                blank=True, default='', max_length=200, verbose_name="Nom de l'école"
            ),
        ),
    ]
