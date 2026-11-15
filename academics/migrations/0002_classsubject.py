from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('academics', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ClassSubject',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('coefficient', models.DecimalField(blank=True, decimal_places=1, help_text='Si vide, utilise le coefficient de la matière', max_digits=3, null=True, verbose_name='Coefficient (optionnel)')),
                ('hours_per_week', models.PositiveIntegerField(default=2, verbose_name='Heures / semaine')),
                ('order', models.PositiveIntegerField(default=0, verbose_name='Ordre')),
                ('classroom', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='class_subjects', to='academics.classroom', verbose_name='Classe')),
                ('subject', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='in_classes', to='academics.subject', verbose_name='Matière')),
            ],
            options={
                'verbose_name': 'Matière de classe',
                'verbose_name_plural': 'Matières de classe',
                'ordering': ['order', 'subject__name'],
                'unique_together': {('classroom', 'subject')},
            },
        ),
    ]
