from django.conf import settings
from django.db import migrations, models
import django.core.validators
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('academics', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Expense',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(verbose_name='Date')),
                ('category', models.CharField(choices=[('salaires', 'Salaires'), ('fournitures', 'Fournitures'), ('entretien', 'Entretien / maintenance'), ('electricite', 'Électricité / eau'), ('transport', 'Transport'), ('communication', 'Communication'), ('autre', 'Autre')], max_length=30, verbose_name='Catégorie')),
                ('amount', models.DecimalField(decimal_places=2, max_digits=12, validators=[django.core.validators.MinValueValidator(0.01)])),
                ('currency', models.CharField(default='FCFA', max_length=10, verbose_name='Devise')),
                ('motif', models.CharField(max_length=255, verbose_name='Motif')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('academic_year', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='expenses', to='academics.academicyear')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Dépense',
                'verbose_name_plural': 'Dépenses',
                'ordering': ['-date', '-id'],
            },
        ),
    ]
