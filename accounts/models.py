from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


class Profile(models.Model):
    """Profil étendu lié à l'utilisateur Django"""

    # 5 rôles métier (+ aliases admin/comptable pour compatibilité données existantes)
    ROLE_CHOICES = [
        ('directeur', 'Directeur / Administration'),
        ('secretaire', 'Secrétaire / Comptable'),
        ('enseignant', 'Enseignant'),
        ('parent', 'Parent'),
        ('eleve', 'Élève'),
        # Aliases (anciennes valeurs en base)
        ('admin', 'Administrateur'),
        ('comptable', 'Comptable'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='eleve')
    phone = models.CharField(max_length=20, blank=True, verbose_name='Téléphone')
    address = models.TextField(blank=True, verbose_name='Adresse')
    photo = models.ImageField(upload_to='profiles/', blank=True, null=True)
    date_of_birth = models.DateField(null=True, blank=True, verbose_name='Date de naissance')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Profil'
        verbose_name_plural = 'Profils'
        ordering = ['user__last_name', 'user__first_name']

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.get_role_display()})"

    @property
    def full_name(self):
        return self.user.get_full_name() or self.user.username


@receiver(post_save, sender=User)
def create_or_update_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)
    else:
        Profile.objects.get_or_create(user=instance)


class WebAuthnCredential(models.Model):
    """Clé Passkey / empreinte digitale liée à un utilisateur."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='webauthn_credentials')
    credential_id = models.CharField(max_length=512, unique=True, db_index=True)
    public_key = models.TextField()  # base64
    sign_count = models.PositiveIntegerField(default=0)
    device_name = models.CharField(max_length=120, blank=True, default='Empreinte / Passkey')
    transports = models.CharField(max_length=200, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Passkey / Empreinte'
        verbose_name_plural = 'Passkeys / Empreintes'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.device_name} — {self.user.username}'
