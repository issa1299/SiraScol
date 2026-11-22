from django.db import migrations


def clear_placeholder(apps, schema_editor):
    SchoolSettings = apps.get_model('core', 'SchoolSettings')
    SchoolSettings.objects.filter(name__iexact='Mon École').update(name='')
    SchoolSettings.objects.filter(name__iexact='Mon Ecole').update(name='')


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0007_school_name_no_default'),
    ]

    operations = [
        migrations.RunPython(clear_placeholder, migrations.RunPython.noop),
    ]
