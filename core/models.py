from django.db import models


class SchoolSettings(models.Model):
    """Paramètres généraux de l'établissement (une seule instance)"""
    name = models.CharField(max_length=200, blank=True, default='', verbose_name="Nom de l'école")
    short_name = models.CharField(max_length=50, blank=True, verbose_name='Sigle')
    motto = models.CharField(max_length=255, blank=True, verbose_name='Devise')
    address = models.TextField(blank=True, verbose_name='Adresse')
    city = models.CharField(max_length=100, blank=True, verbose_name='Ville')
    phone = models.CharField(max_length=30, blank=True, verbose_name='Téléphone')
    phone2 = models.CharField(max_length=30, blank=True, verbose_name='Téléphone 2')
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True, verbose_name='Site web')
    establishment_type = models.CharField(
        max_length=50, blank=True, default='Polyvalent',
        verbose_name="Type d'établissement",
        help_text='Ex: Polyvalent, Primaire, Secondaire, Lycée',
    )
    establishment_status = models.CharField(
        max_length=30, blank=True, default='Privé',
        verbose_name='Statut',
        help_text='Ex: Privé, Public, Confessionnel',
    )
    country = models.CharField(max_length=80, blank=True, default='Mali', verbose_name='Pays')
    province = models.CharField(max_length=100, blank=True, verbose_name='Région / Province')
    commune = models.CharField(max_length=100, blank=True, verbose_name='Commune')
    district = models.CharField(max_length=100, blank=True, verbose_name='District / Cercle')
    inspection = models.CharField(max_length=150, blank=True, verbose_name='Inspection / CAP')
    maintenance_mode = models.BooleanField(default=False, verbose_name='Mode maintenance')
    cover_photo = models.ImageField(
        upload_to='school/covers/', blank=True, null=True,
        verbose_name='Photo de couverture',
    )
    logo = models.ImageField(upload_to='school/', blank=True, null=True, verbose_name='Logo')
    stamp = models.ImageField(
        upload_to='school/', blank=True, null=True,
        verbose_name='Cachet / tampon',
        help_text='Image du cachet de l\'école (PNG transparent recommandé). Affiché sur les bulletins.',
    )
    director_name = models.CharField(max_length=150, blank=True, verbose_name='Nom du directeur')
    academic_year_label = models.CharField(max_length=30, blank=True, verbose_name='Libellé année (ex: 2025-2026)')
    currency = models.CharField(max_length=10, default='FCFA', verbose_name='Devise')
    footer_text = models.CharField(max_length=255, blank=True, verbose_name='Texte pied de page bulletins')
    # En-tête bulletin (personnalisable — rien n'est imposé)
    header_left = models.CharField(
        max_length=200, blank=True,
        verbose_name='En-tête gauche (bulletin)',
        help_text='Ex: CAP de..., Inspection..., ou laissez vide',
    )
    header_right = models.CharField(
        max_length=200, blank=True,
        verbose_name='En-tête droite (bulletin)',
        help_text='Ex: devise, ou laissez vide',
    )
    bulletin_subtitle = models.CharField(
        max_length=150, blank=True,
        verbose_name='Sous-titre bulletin',
        help_text='Ex: Bulletin scolaire du 2e trimestre',
    )
    CARD_TEMPLATE_CHOICES = [
        ('official', 'Officiel (fond blanc)'),
        ('modern', 'Moderne (bleu nuit)'),
        ('classic', 'Classique (bleu roi)'),
        ('gold', 'Prestige (or & noir)'),
        ('green', 'Émeraude'),
        ('burgundy', 'Bordeaux'),
    ]
    card_template = models.CharField(
        max_length=20, default='official',
        choices=CARD_TEMPLATE_CHOICES,
        verbose_name='Modèle de carte scolaire',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Paramètres de l'école"
        verbose_name_plural = "Paramètres de l'école"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Singleton : une seule ligne
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1, defaults={'name': 'Mon École'})
        return obj


class SchoolPhoto(models.Model):
    """Photos de l'école (galerie / couverture)."""
    title = models.CharField(max_length=120, blank=True, verbose_name='Titre')
    image = models.ImageField(upload_to='school/photos/', verbose_name='Photo')
    is_primary = models.BooleanField(default=False, verbose_name='Photo principale')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Photo de l'école"
        verbose_name_plural = "Photos de l'école"
        ordering = ['-is_primary', '-created_at']

    def __str__(self):
        return self.title or f'Photo #{self.pk}'

    def save(self, *args, **kwargs):
        if self.is_primary:
            SchoolPhoto.objects.filter(is_primary=True).exclude(pk=self.pk).update(is_primary=False)
        super().save(*args, **kwargs)


class Notification(models.Model):
    """Notification interne affichée dans les portails dédiés."""

    CATEGORY_CHOICES = [
        ('note', 'Nouvelle note'),
        ('absence', 'Absence / retard'),
        ('annonce', 'Annonce'),
        ('devoir', 'Devoir'),
        ('emploi', 'Emploi du temps'),
        ('bulletin', 'Bulletin'),
        ('paiement', 'Paiement'),
        ('info', 'Information'),
    ]

    user = models.ForeignKey(
        'auth.User', on_delete=models.CASCADE, related_name='notifications',
    )
    title = models.CharField(max_length=200, verbose_name='Titre')
    message = models.TextField(blank=True, verbose_name='Message')
    category = models.CharField(
        max_length=20, choices=CATEGORY_CHOICES, default='info',
    )
    link = models.CharField(max_length=255, blank=True, verbose_name='Lien')
    is_read = models.BooleanField(default=False, verbose_name='Lu')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.title} — {self.user.username}'
