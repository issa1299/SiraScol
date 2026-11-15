from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('accounts', '0002_alter_profile_role'),
    ]

    operations = [
        migrations.CreateModel(
            name='WebAuthnCredential',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('credential_id', models.CharField(db_index=True, max_length=512, unique=True)),
                ('public_key', models.TextField()),
                ('sign_count', models.PositiveIntegerField(default=0)),
                ('device_name', models.CharField(blank=True, default='Empreinte / Passkey', max_length=120)),
                ('transports', models.CharField(blank=True, default='', max_length=200)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('last_used_at', models.DateTimeField(blank=True, null=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='webauthn_credentials', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Passkey / Empreinte',
                'verbose_name_plural': 'Passkeys / Empreintes',
                'ordering': ['-created_at'],
            },
        ),
    ]
