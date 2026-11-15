from django.db import migrations, models


def dedupe_punches(apps, schema_editor):
    """Garde le premier pointage, supprime les doublons (même personne/jour/action)."""
    AttendancePunch = apps.get_model('attendance', 'AttendancePunch')
    seen = set()
    to_delete = []
    qs = AttendancePunch.objects.order_by('id')
    for p in qs.iterator():
        if p.student_id:
            key = ('s', p.kind, p.student_id, str(p.date), p.action)
        elif p.teacher_id:
            key = ('t', p.kind, p.teacher_id, str(p.date), p.action)
        else:
            continue
        if key in seen:
            to_delete.append(p.pk)
        else:
            seen.add(key)
    if to_delete:
        AttendancePunch.objects.filter(pk__in=to_delete).delete()


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0002_attendancepunch'),
    ]

    operations = [
        migrations.RunPython(dedupe_punches, noop_reverse),
        migrations.AddConstraint(
            model_name='attendancepunch',
            constraint=models.UniqueConstraint(
                condition=models.Q(('student__isnull', False)),
                fields=('kind', 'student', 'date', 'action'),
                name='uniq_punch_student_day_action',
            ),
        ),
        migrations.AddConstraint(
            model_name='attendancepunch',
            constraint=models.UniqueConstraint(
                condition=models.Q(('teacher__isnull', False)),
                fields=('kind', 'teacher', 'date', 'action'),
                name='uniq_punch_teacher_day_action',
            ),
        ),
    ]
