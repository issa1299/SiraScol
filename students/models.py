from django.db import models
from django.contrib.auth.models import User
from academics.models import ClassRoom, AcademicYear


class Student(models.Model):
    """Élève"""
    GENDER_CHOICES = [
        ('M', 'Masculin'),
        ('F', 'Féminin'),
    ]

    STATUS_CHOICES = [
        ('actif', 'Actif'),
        ('inactif', 'Inactif'),
        ('diplome', 'Diplômé'),
        ('abandon', 'Abandon'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student', null=True, blank=True)
    matricule = models.CharField(max_length=30, unique=True, blank=True, verbose_name='Matricule')
    first_name = models.CharField(max_length=100, verbose_name='Prénom')
    last_name = models.CharField(max_length=100, verbose_name='Nom')
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, verbose_name='Sexe')
    date_of_birth = models.DateField(
        null=True, blank=True, verbose_name='Date de naissance'
    )
    place_of_birth = models.CharField(max_length=100, blank=True, verbose_name='Lieu de naissance')
    nationality = models.CharField(max_length=50, default='Ivoirienne', verbose_name='Nationalité')
    address = models.TextField(blank=True, verbose_name='Adresse')
    phone = models.CharField(max_length=20, blank=True, verbose_name='Téléphone')
    email = models.EmailField(blank=True)
    photo = models.ImageField(upload_to='students/', blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='actif')
    enrollment_date = models.DateField(verbose_name="Date d'inscription")
    notes = models.TextField(blank=True, verbose_name='Observations')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Élève'
        verbose_name_plural = 'Élèves'
        ordering = ['last_name', 'first_name']

    def __str__(self):
        return f"{self.last_name} {self.first_name} ({self.matricule})"

    @property
    def full_name(self):
        return f"{self.last_name} {self.first_name}"

    def current_enrollment(self):
        return self.enrollments.filter(is_active=True).select_related('classroom').first()

    def save(self, *args, **kwargs):
        if not self.matricule:
            self.matricule = self._generate_matricule()
        super().save(*args, **kwargs)

    def _generate_matricule(self):
        """
        Génère un matricule unique du type : ANNEE-XXXX
        Exemple : 2026-0001, 2026-0002...
        """
        from django.utils import timezone
        year = timezone.now().year
        prefix = f"{year}-"

        # Trouver le dernier numéro de cette année
        last = (
            Student.objects
            .filter(matricule__startswith=prefix)
            .order_by('-matricule')
            .values_list('matricule', flat=True)
            .first()
        )
        if last:
            try:
                num = int(last.split('-')[-1]) + 1
            except (ValueError, IndexError):
                num = 1
        else:
            num = 1

        return f"{prefix}{num:04d}"


class Parent(models.Model):
    """Parent / Tuteur"""
    RELATION_CHOICES = [
        ('pere', 'Père'),
        ('mere', 'Mère'),
        ('tuteur', 'Tuteur'),
        ('autre', 'Autre'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='parent_profile', null=True, blank=True)
    first_name = models.CharField(max_length=100, verbose_name='Prénom')
    last_name = models.CharField(max_length=100, verbose_name='Nom')
    phone = models.CharField(max_length=20, verbose_name='Téléphone')
    phone2 = models.CharField(max_length=20, blank=True, verbose_name='Téléphone 2')
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True, verbose_name='Adresse')
    profession = models.CharField(max_length=100, blank=True, verbose_name='Profession')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Parent'
        verbose_name_plural = 'Parents'
        ordering = ['last_name', 'first_name']

    def __str__(self):
        return f"{self.last_name} {self.first_name}"


class ParentStudent(models.Model):
    """Relation Parent - Élève"""
    parent = models.ForeignKey(Parent, on_delete=models.CASCADE, related_name='children')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='parents')
    relation = models.CharField(max_length=20, choices=Parent.RELATION_CHOICES, default='pere')
    is_primary = models.BooleanField(default=False, verbose_name='Contact principal')

    class Meta:
        verbose_name = 'Lien Parent-Élève'
        verbose_name_plural = 'Liens Parent-Élève'
        unique_together = ['parent', 'student']

    def __str__(self):
        return f"{self.parent} → {self.student} ({self.get_relation_display()})"


class Enrollment(models.Model):
    """Inscription d'un élève dans une classe pour une année"""
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='enrollments')
    classroom = models.ForeignKey(ClassRoom, on_delete=models.CASCADE, related_name='enrollments')
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='enrollments')
    enrollment_date = models.DateField(verbose_name="Date d'inscription")
    is_active = models.BooleanField(default=True)
    END_STATUS_CHOICES = [
        ('en_cours', 'En cours'),
        ('promoted', 'Admis (passe)'),
        ('repeated', 'Redouble'),
        ('ajourne', 'Ajourné'),
        ('transferred', 'Transféré'),
        ('autre', 'Autre décision'),
        ('abandoned', 'Abandon / Sortie'),
    ]
    end_status = models.CharField(
        max_length=20, choices=END_STATUS_CHOICES, default='en_cours',
        verbose_name="Décision de fin d'année",
    )
    end_average = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        verbose_name='Moyenne annuelle',
    )
    end_note = models.CharField(max_length=255, blank=True, verbose_name='Observation')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Inscription'
        verbose_name_plural = 'Inscriptions'
        unique_together = ['student', 'academic_year']
        ordering = ['-academic_year__start_date']

    def __str__(self):
        return f"{self.student} → {self.classroom} ({self.academic_year})"

    @property
    def is_promoted(self):
        return self.end_status == 'promoted'

    @property
    def is_repeated(self):
        return self.end_status == 'repeated'


class PromotionOperation(models.Model):
    """Opération de passage/orientation d'une classe source vers l'année suivante.

    Le dossier reste modifiable tant qu'il n'est pas validé. La validation
    définitive (directeur) verrouille l'opération.
    """
    STATUS_CHOICES = [
        ('brouillon', 'Brouillon'),
        ('a_valider', 'À valider'),
        ('valide', 'Validé'),
    ]

    source_classroom = models.ForeignKey(
        ClassRoom, on_delete=models.PROTECT, related_name='promotion_operations'
    )
    source_year = models.ForeignKey(
        AcademicYear, on_delete=models.PROTECT, related_name='promotion_operations'
    )
    target_year = models.ForeignKey(
        AcademicYear, on_delete=models.PROTECT, related_name='promotion_operations_target'
    )
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='brouillon')
    note = models.TextField(blank=True, verbose_name='Observation de la direction')
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='promotions_created',
    )
    validated_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='promotions_validated',
    )
    validated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Opération de passage / orientation'
        verbose_name_plural = 'Opérations de passage / orientation'
        constraints = [
            models.UniqueConstraint(
                fields=['source_classroom', 'source_year', 'target_year'],
                name='promo_unique_operation',
            )
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.source_classroom.name} → {self.target_year.name} ({self.get_status_display()})'

    @property
    def is_locked(self):
        return self.status == 'valide'


class PromotionDecision(models.Model):
    """Décision individuelle, avec révisions conservées pour traçabilité.

    Une correction ne modifie jamais une révision existante : elle crée une
    nouvelle ligne ``is_current`` avec ``revision`` incrémenté.
    """
    operation = models.ForeignKey(
        PromotionOperation, on_delete=models.CASCADE, related_name='decisions'
    )
    enrollment = models.ForeignKey(
        Enrollment, on_delete=models.PROTECT, related_name='orientation_decisions'
    )
    decision = models.CharField(max_length=20, choices=Enrollment.END_STATUS_CHOICES,
                                default='en_cours')
    target_classroom = models.ForeignKey(
        ClassRoom, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='orientation_decisions',
    )
    average = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    note = models.TextField(blank=True)
    revision = models.PositiveIntegerField(default=1)
    is_current = models.BooleanField(default=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Décision d’orientation'
        verbose_name_plural = 'Décisions d’orientation'
        constraints = [
            models.UniqueConstraint(
                fields=['operation', 'enrollment', 'revision'], name='promo_unique_revision'
            )
        ]
        ordering = ['-revision']

    def __str__(self):
        return (f'{self.enrollment.student} — {self.get_decision_display()} '
                f'(rév. {self.revision})')

