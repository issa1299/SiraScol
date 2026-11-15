from django.db import models
from django.core.validators import MinValueValidator
from students.models import Student
from academics.models import Subject, ClassRoom, AcademicYear, Cycle
from teachers.models import Teacher


class Period(models.Model):
    """
    Période d'évaluation :
    - Pour 1ère-5ème : Mois (Septembre, Octobre...)
    - Pour 6ème-12ème : Trimestre 1, 2, 3
    """
    PERIOD_TYPE_CHOICES = [
        ('mois', 'Mois (1ère-5ème)'),
        ('trimestre', 'Trimestre (6ème-12ème)'),
    ]

    name = models.CharField(max_length=50, verbose_name='Nom')  # ex: Septembre, Trimestre 1
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='periods')
    period_type = models.CharField(max_length=20, choices=PERIOD_TYPE_CHOICES, default='trimestre')
    start_date = models.DateField()
    end_date = models.DateField()
    order = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Période'
        verbose_name_plural = 'Périodes'
        ordering = ['academic_year', 'order']
        unique_together = ['name', 'academic_year']

    def __str__(self):
        return f"{self.name} ({self.academic_year})"


class AssessmentType(models.Model):
    """
    Type d'évaluation selon le niveau :
    - 1ère à 5ème : Composition uniquement
    - 6ème à 12ème : Devoir, Composition, Examen trimestriel
    """
    name = models.CharField(max_length=50, unique=True)
    code = models.CharField(max_length=30, unique=True, blank=True)  # composition, devoir, trimestre
    weight = models.DecimalField(max_digits=4, decimal_places=2, default=1.0, verbose_name='Coefficient')
    # Cycles concernés (vide = tous)
    cycles = models.ManyToManyField(Cycle, blank=True, related_name='assessment_types',
                                    verbose_name='Cycles concernés')
    description = models.TextField(blank=True)

    class Meta:
        verbose_name = "Type d'évaluation"
        verbose_name_plural = "Types d'évaluation"

    def __str__(self):
        return self.name


class Assessment(models.Model):
    """Une évaluation (devoir, composition, examen de trimestre...)"""
    title = models.CharField(max_length=150, verbose_name='Titre')
    assessment_type = models.ForeignKey(AssessmentType, on_delete=models.PROTECT, related_name='assessments')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='assessments')
    classroom = models.ForeignKey(ClassRoom, on_delete=models.CASCADE, related_name='assessments')
    teacher = models.ForeignKey(Teacher, on_delete=models.SET_NULL, null=True, blank=True, related_name='assessments')
    period = models.ForeignKey(Period, on_delete=models.CASCADE, related_name='assessments')
    date = models.DateField(verbose_name='Date')
    max_score = models.DecimalField(max_digits=5, decimal_places=2, default=20, verbose_name='Note max')
    coefficient = models.DecimalField(max_digits=3, decimal_places=1, default=1.0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Évaluation'
        verbose_name_plural = 'Évaluations'
        ordering = ['-date']

    def __str__(self):
        return f"{self.title} - {self.subject} ({self.classroom})"


class Grade(models.Model):
    """Note d'un élève pour une évaluation"""
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name='grades')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='grades')
    score = models.DecimalField(
        max_digits=5, decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name='Note'
    )
    appreciation = models.CharField(max_length=255, blank=True, verbose_name='Appréciation')
    is_absent = models.BooleanField(default=False, verbose_name='Absent')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Note'
        verbose_name_plural = 'Notes'
        unique_together = ['assessment', 'student']
        ordering = ['student__last_name']

    def __str__(self):
        return f"{self.student} - {self.assessment}: {self.score}"

    def save(self, *args, **kwargs):
        if self.is_absent:
            self.score = 0
        super().save(*args, **kwargs)



class BulletinTemplate(models.Model):
    """
    Modèle / gabarit de bulletin configurable.
    L'école peut en créer plusieurs et choisir celui utilisé pour primaire ou secondaire/lycée.
    """
    CATEGORY_CHOICES = [
        ('primaire', 'Primaire (1ère–5ème)'),
        ('secondaire', '2ème cycle / Lycée (7ème–12ème)'),
    ]
    LAYOUT_CHOICES = [
        ('mali_standard', 'Standard Mali (NoteClasse/20 + Comp/40)'),
        ('simple_20', 'Simple (toutes notes sur 20)'),
        ('primaire_compositions', 'Primaire – compositions'),
    ]
    FORMULA_CHOICES = [
        ('comp40_plus_classe_div3', '(NoteComp/40 + NoteClasse/20) / 3'),
        ('comp20_x2_plus_classe_div3', '(Composition×2 + NoteClasse) / 3  [notes sur 20]'),
        ('moyenne_simple', 'Moyenne simple des notes'),
    ]

    name = models.CharField(max_length=120, verbose_name='Nom du modèle')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, verbose_name='Catégorie')
    layout = models.CharField(max_length=40, choices=LAYOUT_CHOICES, default='mali_standard')
    formula = models.CharField(
        max_length=40, choices=FORMULA_CHOICES, default='comp40_plus_classe_div3',
        verbose_name='Formule de moyenne',
    )
    description = models.TextField(blank=True)
    is_default = models.BooleanField(
        default=False,
        verbose_name='Modèle par défaut pour cette catégorie',
        help_text='Un seul défaut par catégorie (primaire ou secondaire).',
    )
    show_rank = models.BooleanField(default=True, verbose_name='Afficher le rang')
    show_prev_average = models.BooleanField(default=True, verbose_name='Afficher moyenne trimestre préc.')
    header_title = models.CharField(
        max_length=150, blank=True,
        verbose_name='Titre en-tête (optionnel)',
        help_text='Ex: BULLETIN SCOLAIRE — 2e TRIMESTRE',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Modèle de bulletin'
        verbose_name_plural = 'Modèles de bulletins'
        ordering = ['category', 'name']

    def __str__(self):
        return f"{self.name} ({self.get_category_display()})"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_default:
            BulletinTemplate.objects.filter(
                category=self.category, is_default=True
            ).exclude(pk=self.pk).update(is_default=False)

    @classmethod
    def get_default(cls, category):
        obj = cls.objects.filter(category=category, is_default=True).first()
        if obj:
            return obj
        return cls.objects.filter(category=category).first()
