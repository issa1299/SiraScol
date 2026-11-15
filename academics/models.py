from django.db import models


class AcademicYear(models.Model):
    """Année scolaire (ex: 2025-2026)"""
    name = models.CharField(max_length=20, unique=True, verbose_name='Nom')
    start_date = models.DateField(verbose_name='Date de début')
    end_date = models.DateField(verbose_name='Date de fin')
    is_current = models.BooleanField(default=False, verbose_name='Année en cours')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Année scolaire'
        verbose_name_plural = 'Années scolaires'
        ordering = ['-start_date']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.is_current:
            AcademicYear.objects.filter(is_current=True).exclude(pk=self.pk).update(is_current=False)
        super().save(*args, **kwargs)


class Cycle(models.Model):
    """Cycle : 1er cycle (primaire), 2ème cycle (secondaire), Lycée."""
    CYCLE_CHOICES = [
        ('primaire', '1er cycle'),
        ('secondaire', '2ème cycle'),
        ('lycee', 'Lycée'),
        ('autre', 'Autre'),
    ]

    name = models.CharField(max_length=50, unique=True, verbose_name='Nom')
    code = models.CharField(max_length=20, choices=CYCLE_CHOICES, unique=True, verbose_name='Code')
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0, verbose_name='Ordre')

    class Meta:
        verbose_name = 'Cycle'
        verbose_name_plural = 'Cycles'
        ordering = ['order', 'name']

    def __str__(self):
        return self.name


class Level(models.Model):
    """Niveau (ex: CP, CE1, 6ème, 5ème, Terminale...)"""
    name = models.CharField(max_length=50, verbose_name='Nom')  # CP, 6ème, Terminale S...
    cycle = models.ForeignKey(Cycle, on_delete=models.PROTECT, related_name='levels', verbose_name='Cycle')
    order = models.PositiveIntegerField(default=0, verbose_name='Ordre')
    description = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Niveau'
        verbose_name_plural = 'Niveaux'
        ordering = ['cycle__order', 'order', 'name']
        unique_together = ['name', 'cycle']

    def __str__(self):
        return f"{self.name} ({self.cycle.name})"


class ClassRoom(models.Model):
    """Classe (ex: CP A, 6ème A, Terminale S1)"""
    name = models.CharField(max_length=50, verbose_name='Nom')
    level = models.ForeignKey(Level, on_delete=models.PROTECT, related_name='classrooms')
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='classrooms')
    capacity = models.PositiveIntegerField(default=40, verbose_name='Capacité')
    serie = models.CharField(
        max_length=50, blank=True,
        verbose_name='Série',
        help_text='Pour 10ème, 11ème et 12ème : Scientifique, Littéraire, Économique...'
    )
    inscription_fee = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name="Frais d'inscription"
    )
    tuition_fee = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name='Scolarité'
    )
    main_teacher = models.ForeignKey(
        'teachers.Teacher',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='main_classes',
        verbose_name='Professeur principal / Instituteur'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Classe'
        verbose_name_plural = 'Classes'
        unique_together = ['name', 'academic_year']
        ordering = ['level__cycle__order', 'level__order', 'name']

    def __str__(self):
        return f"{self.name} ({self.academic_year})"

    @property
    def student_count(self):
        return self.enrollments.filter(is_active=True).count()

    @property
    def cycle(self):
        return self.level.cycle


class Subject(models.Model):
    """Matière"""
    name = models.CharField(max_length=100, verbose_name='Nom')
    code = models.CharField(max_length=20, unique=True, verbose_name='Code')
    coefficient = models.DecimalField(max_digits=3, decimal_places=1, default=1.0, verbose_name='Coefficient')
    # Une matière peut être liée à un ou plusieurs cycles
    cycles = models.ManyToManyField(Cycle, blank=True, related_name='subjects', verbose_name='Cycles concernés')
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Matière'
        verbose_name_plural = 'Matières'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.code})"


class ClassSubject(models.Model):
    """Matière enseignée dans une classe (programme de la classe)."""
    classroom = models.ForeignKey(
        ClassRoom, on_delete=models.CASCADE, related_name='class_subjects',
        verbose_name='Classe',
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name='in_classes',
        verbose_name='Matière',
    )
    coefficient = models.DecimalField(
        max_digits=3, decimal_places=1, null=True, blank=True,
        verbose_name='Coefficient (optionnel)',
        help_text='Si vide, utilise le coefficient de la matière',
    )
    hours_per_week = models.PositiveIntegerField(default=2, verbose_name='Heures / semaine')
    order = models.PositiveIntegerField(default=0, verbose_name='Ordre')

    class Meta:
        verbose_name = 'Matière de classe'
        verbose_name_plural = 'Matières de classe'
        unique_together = ['classroom', 'subject']
        ordering = ['order', 'subject__name']

    def __str__(self):
        return f"{self.classroom} — {self.subject}"

    def effective_coefficient(self):
        if self.coefficient is not None:
            return self.coefficient
        return self.subject.coefficient


class SubjectAssignment(models.Model):
    """Affectation Enseignant - Matière - Classe"""
    teacher = models.ForeignKey('teachers.Teacher', on_delete=models.CASCADE, related_name='assignments')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='assignments')
    classroom = models.ForeignKey(ClassRoom, on_delete=models.CASCADE, related_name='assignments')
    hours_per_week = models.PositiveIntegerField(default=2, verbose_name='Heures / semaine')

    class Meta:
        verbose_name = 'Affectation'
        verbose_name_plural = 'Affectations'
        unique_together = ['teacher', 'subject', 'classroom']

    def __str__(self):
        return f"{self.teacher} - {self.subject} - {self.classroom}"
