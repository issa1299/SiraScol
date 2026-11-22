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
        ('transferred', 'Transféré'),
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

