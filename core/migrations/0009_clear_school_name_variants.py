from django.db import migrations


def clear_variants(apps, schema_editor):
    import unicodedata

    SchoolSettings = apps.get_model('core', 'SchoolSettings')
    for obj in SchoolSettings.objects.all():
        raw = (obj.name or '').strip()
        normalized = ''.join(
            c for c in unicodedata.normalize('NFKD', raw.lower())
            if not unicodedata.combining(c)
        )
        if normalized.startswith('mon ecole'):
            obj.name = ''
            obj.save(update_fields=['name'])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0008_clear_school_name_placeholder'),
    ]

    operations = [
        migrations.RunPython(clear_variants, migrations.RunPython.noop),
    ]
