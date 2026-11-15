from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('academics', '0001_initial'),
        ('communication', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='SchoolDocument',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200, verbose_name='Titre')),
                ('category', models.CharField(choices=[('reglement', 'Règlement intérieur'), ('circulaire', 'Circulaire / note de service'), ('formulaire', 'Formulaire'), ('pedagogie', 'Pédagogie / programme'), ('examen', 'Examens / calendrier'), ('financier', 'Document financier'), ('autre', 'Autre')], default='autre', max_length=20)),
                ('description', models.TextField(blank=True, verbose_name='Description')),
                ('file', models.FileField(upload_to='documents/%Y/%m/', verbose_name='Fichier')),
                ('is_published', models.BooleanField(default=True, verbose_name='Publié')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('academic_year', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='school_documents', to='academics.academicyear')),
                ('uploaded_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Document scolaire',
                'verbose_name_plural': 'Documents scolaires',
                'ordering': ['-created_at'],
            },
        ),
    ]
