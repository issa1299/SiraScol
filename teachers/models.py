from django.db import models
from core.validators import validate_upload
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from decimal import Decimal


class Teacher(models.Model):
    """Personnel de l'école (enseignant, admin, service)."""
    GENDER_CHOICES = [
        ('M', 'Masculin'),
        ('F', 'Féminin'),
    ]
    CATEGORY_CHOICES = [
        ('enseignant', 'Enseignant'),
        ('admin', 'Administration'),
        ('service', 'Personnel de service'),
    ]
    STATUS_CHOICES = [
        ('actif', 'Actif'),
        ('conge', 'En congé'),
        ('suspendu', 'Suspendu'),
        ('parti', 'Parti'),
    ]
    CONTRACT_CHOICES = [
        ('cdi', 'CDI'),
        ('cdd', 'CDD'),
        ('vacation', 'Vacation / Horaire'),
        ('stage', 'Stage'),
        ('autre', 'Autre'),
    ]

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='teacher', null=True, blank=True
    )
    has_account = models.BooleanField(
        default=True, verbose_name='Compte de connexion',
        help_text='Désactivé pour un personnel ajouté sans compte.',
    )
    matricule = models.CharField(max_length=30, unique=True, verbose_name='Matricule')
    first_name = models.CharField(max_length=100, verbose_name='Prénom')
    last_name = models.CharField(max_length=100, verbose_name='Nom')
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, verbose_name='Sexe')
    date_of_birth = models.DateField(null=True, blank=True, verbose_name='Date de naissance')
    phone = models.CharField(max_length=20, blank=True, verbose_name='Téléphone')
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True, verbose_name='Adresse')
    photo = models.ImageField(upload_to='teachers/', blank=True, null=True)

    category = models.CharField(
        max_length=20, choices=CATEGORY_CHOICES, default='enseignant', verbose_name='Catégorie'
    )
    function = models.CharField(max_length=100, blank=True, verbose_name='Fonction')
    department = models.CharField(max_length=100, blank=True, verbose_name='Département / service')
    speciality = models.CharField(max_length=100, blank=True, verbose_name='Spécialité')
    diploma = models.CharField(max_length=150, blank=True, verbose_name='Diplôme')
    hire_date = models.DateField(null=True, blank=True, verbose_name="Date d'embauche")
    contract_type = models.CharField(
        max_length=20, choices=CONTRACT_CHOICES, blank=True, default='cdi', verbose_name='Type de contrat'
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='actif', verbose_name='Statut'
    )
    base_salary = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)],
        verbose_name='Salaire de base'
    )
    is_active = models.BooleanField(default=True)  # miroir rapide de status==actif
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Personnel'
        verbose_name_plural = 'Personnel'
        ordering = ['last_name', 'first_name']

    def __str__(self):
        return f"{self.last_name} {self.first_name}"

    @property
    def full_name(self):
        return f"{self.last_name} {self.first_name}"

    def save(self, *args, **kwargs):
        self.is_active = self.status == 'actif'
        super().save(*args, **kwargs)


class StaffContract(models.Model):
    staff = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name='contracts')
    contract_type = models.CharField(max_length=20, choices=Teacher.CONTRACT_CHOICES, default='cdi')
    function = models.CharField(max_length=100, blank=True)
    start_date = models.DateField(verbose_name='Date de début')
    end_date = models.DateField(null=True, blank=True, verbose_name='Date de fin')
    salary = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(
        max_length=20,
        choices=[('actif', 'Actif'), ('termine', 'Terminé'), ('resilie', 'Résilié')],
        default='actif',
    )
    document = models.FileField(validators=[validate_upload], upload_to='staff_contracts/', blank=True, null=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-start_date']
        verbose_name = 'Contrat'
        verbose_name_plural = 'Contrats'

    def __str__(self):
        return f"Contrat {self.staff} ({self.start_date})"


class StaffAttendance(models.Model):
    STATUS_CHOICES = [
        ('present', 'Présent'),
        ('absent', 'Absent'),
        ('retard', 'Retard'),
        ('conge', 'Congé'),
        ('permission', 'Permission'),
    ]
    staff = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name='attendances')
    date = models.DateField()
    time_in = models.TimeField(null=True, blank=True, verbose_name='Arrivée')
    time_out = models.TimeField(null=True, blank=True, verbose_name='Départ')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='present')
    notes = models.CharField(max_length=255, blank=True)
    recorded_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', 'staff__last_name']
        unique_together = [('staff', 'date')]
        verbose_name = 'Présence personnel'
        verbose_name_plural = 'Présences personnel'

    def __str__(self):
        return f"{self.staff} — {self.date} ({self.status})"


class StaffSalary(models.Model):
    PAY_STATUS = [
        ('en_attente', 'En attente'),
        ('paye', 'Payé'),
        ('annule', 'Annulé'),
    ]
    staff = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name='salaries')
    year = models.PositiveIntegerField()
    month = models.PositiveIntegerField()  # 1-12
    base = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    primes = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    retenues = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    advances = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Avances')
    net = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=PAY_STATUS, default='en_attente')
    paid_at = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-year', '-month']
        unique_together = [('staff', 'year', 'month')]
        verbose_name = 'Salaire'
        verbose_name_plural = 'Salaires'

    def save(self, *args, **kwargs):
        self.net = (
            Decimal(str(self.base or 0))
            + Decimal(str(self.primes or 0))
            - Decimal(str(self.retenues or 0))
            - Decimal(str(self.advances or 0))
        )
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Salaire {self.month:02d}/{self.year} — {self.staff}"


class StaffDocument(models.Model):
    DOC_TYPES = [
        ('cv', 'CV'),
        ('diplome', 'Diplôme'),
        ('contrat', 'Contrat'),
        ('cni', "Pièce d'identité"),
        ('certificat', 'Certificat'),
        ('attestation', 'Attestation'),
        ('autre', 'Autre'),
    ]
    staff = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name='documents')
    doc_type = models.CharField(max_length=20, choices=DOC_TYPES, default='autre')
    title = models.CharField(max_length=150)
    file = models.FileField(validators=[validate_upload], upload_to='staff_docs/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.title} ({self.staff})"
