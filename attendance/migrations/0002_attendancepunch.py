from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('students', '0001_initial'),
        ('teachers', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='AttendancePunch',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('kind', models.CharField(choices=[('eleve', 'Élève'), ('personnel', 'Personnel')], default='eleve', max_length=20)),
                ('action', models.CharField(choices=[('arrivee', 'Arrivée'), ('depart', 'Départ')], max_length=20)),
                ('punched_at', models.DateTimeField(auto_now_add=True)),
                ('date', models.DateField(db_index=True)),
                ('notes', models.CharField(blank=True, max_length=255)),
                ('recorded_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='recorded_punches', to=settings.AUTH_USER_MODEL)),
                ('student', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='punches', to='students.student')),
                ('teacher', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='punches', to='teachers.teacher')),
            ],
            options={
                'verbose_name': 'Pointage',
                'verbose_name_plural': 'Pointages',
                'ordering': ['-punched_at'],
            },
        ),
    ]
