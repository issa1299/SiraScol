from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='schoolsettings',
            name='stamp',
            field=models.ImageField(
                blank=True,
                help_text="Image du cachet de l'école (PNG transparent recommandé). Affiché sur les bulletins.",
                null=True,
                upload_to='school/',
                verbose_name='Cachet / tampon',
            ),
        ),
    ]
