# -*- coding: utf-8 -*-
"""Gestion des candidats aux examens nationaux : DEF et BAC."""
from django.conf import settings
from django.db import models

from academics.models import AcademicYear, ClassRoom
from students.models import Student


class ExamSession(models.Model):
    TYPE_CHOICES = [('def', 'DEF — Diplôme d’Études Fondamentales'),
                    ('bac', 'BAC — Baccalauréat')]
    SESSION_CHOICES = [('normal', 'Session normale'), ('rattrapage', 'Rattrapage')]
    STATUS_CHOICES = [
        ('preparation', 'Préparation'),
        ('ouverte', 'Ouverte'),
        ('cloturee', 'Clôturée'),
    ]

    type = models.CharField(max_length=5, choices=TYPE_CHOICES)
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE,
                                      related_name='exam_sessions')
    # `session` est conservé pour compatibilité ; `kind` est la typologie
    # configurable (normale, rattrapage, session spéciale…), jamais imposée.
    session = models.CharField(max_length=12, choices=SESSION_CHOICES, default='normal')
    kind = models.CharField(max_length=40, default='normale', verbose_name='Type de session')
    date = models.DateField(verbose_name='Date de l’examen')
    start_date = models.DateField(null=True, blank=True, verbose_name='Date de début')
    end_date = models.DateField(null=True, blank=True, verbose_name='Date de fin')
    academy = models.CharField(max_length=150, blank=True,
                               verbose_name='Académie d’enseignement')
    center = models.CharField(max_length=150, blank=True, verbose_name='Centre d’examen')
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='preparation',
                              verbose_name='Statut de la session')
    is_open = models.BooleanField(default=True, verbose_name='Inscriptions ouvertes')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['type', 'academic_year', 'session'],
                name='exam_unique_session',
            ),
            models.UniqueConstraint(
                fields=['type', 'academic_year', 'kind'],
                name='exam_unique_session_kind',
            ),
        ]
        ordering = ['-date']

    def __str__(self):
        return (f'{self.get_type_display()} — {self.academic_year.name} '
                f'({self.kind}, {self.get_status_display()})')

    def save(self, *args, **kwargs):
        if not self.start_date:
            self.start_date = self.date
        if not self.end_date:
            self.end_date = self.date
        # `is_open` reste cohérent avec le statut pour le code historique.
        self.is_open = self.status == 'ouverte'
        super().save(*args, **kwargs)


class Candidate(models.Model):
    STATUS_CHOICES = [
        ('inscrit', 'Inscrit'),
        ('valide', 'Validé'),
        ('absent', 'Absent'),
        ('admis', 'Admis'),
        ('eche', 'Échoué'),
        ('rattrapage', 'Rattrapage'),
    ]
    SERIES_CHOICES = [
        ('', '—'),
        ('scientifique', 'Scientifique'),
        ('litteraire', 'Littéraire'),
        ('stg', 'STG — Sciences et technologiques de gestion'),
        ('sti', 'STI — Sciences et techniques industrielles'),
    ]

    REGISTRATION_STATUS_CHOICES = [
        ('brouillon', 'Brouillon'),
        ('a_verifier', 'À vérifier'),
        ('valide', 'Validé'),
        ('rejete', 'Rejeté'),
    ]
    LANGUAGE_CHOICES = [
        ('', '—'), ('anglais', 'Anglais'), ('arabe', 'Arabe'),
        ('espagnol', 'Espagnol'), ('allemand', 'Allemand'),
    ]

    # ``student`` est facultatif : un candidat externe n'est pas inscrit comme élève
    # dans l'établissement (module distinct des inscriptions scolaires classiques).
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='exam_candidates',
                                null=True, blank=True)
    session = models.ForeignKey(ExamSession, on_delete=models.CASCADE, related_name='candidates')
    registration_number = models.CharField(max_length=30, unique=True, blank=True,
                                            verbose_name='Numéro de candidat')
    classroom = models.ForeignKey(ClassRoom, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='exam_candidates')
    is_external = models.BooleanField(default=False, verbose_name='Candidat externe')
    CANDIDATE_KIND_CHOICES = [
        ('regulier', 'Candidat régulier (élève de l’établissement)'),
        ('libre', 'Candidat libre (dossier spécifique)'),
    ]
    candidate_kind = models.CharField(max_length=10, choices=CANDIDATE_KIND_CHOICES,
                                      default='regulier', verbose_name='Type de candidature')
    official_number = models.CharField(max_length=30, blank=True,
                                       verbose_name='Numéro officiel de place')
    academy = models.CharField(max_length=150, blank=True,
                               verbose_name='Académie d’enseignement')

    # Identité du candidat externe (élève : ces données sont lues sur ``student``)
    external_matricule = models.CharField(max_length=30, blank=True, verbose_name='Matricule (externe)')
    external_last_name = models.CharField(max_length=100, blank=True, verbose_name='Nom (externe)')
    external_first_name = models.CharField(max_length=100, blank=True, verbose_name='Prénom (externe)')
    external_gender = models.CharField(max_length=1, choices=Student.GENDER_CHOICES, blank=True,
                                       verbose_name='Sexe (externe)')
    external_date_of_birth = models.DateField(null=True, blank=True,
                                              verbose_name='Date de naissance (externe)')

    # Identité / naissance (figées au moment de l'inscription)
    birth_place = models.CharField(max_length=120, blank=True, verbose_name='Lieu de naissance')
    school_name = models.CharField(max_length=200, blank=True, verbose_name='Établissement d’origine')

    # Identification / parents
    parent_name = models.CharField(max_length=200, blank=True, verbose_name='Nom du parent / tuteur')
    parent_phone = models.CharField(max_length=30, blank=True, verbose_name='Téléphone du parent')

    # Pièces du dossier
    photo = models.ImageField(upload_to='examens/photos/', blank=True, null=True)
    birth_certificate = models.FileField(upload_to='examens/pieces/', blank=True, null=True,
                                          verbose_name='Extrait de naissance')
    other_document = models.FileField(upload_to='examens/pieces/', blank=True, null=True,
                                       verbose_name='Autre pièce')

    # Examen
    registration_status = models.CharField(max_length=12, choices=REGISTRATION_STATUS_CHOICES,
                                            default='brouillon', verbose_name='Statut d’inscription')
    exam_center = models.CharField(max_length=150, blank=True, verbose_name='Centre d’examen')
    series = models.CharField(max_length=20, choices=SERIES_CHOICES, blank=True,
                              verbose_name='Série du BAC')
    speciality = models.CharField(max_length=120, blank=True,
                                   verbose_name='Spécialité / option')
    terminale_class = models.CharField(max_length=60, blank=True, verbose_name='Classe de Terminale')
    living_language = models.CharField(max_length=20, choices=LANGUAGE_CHOICES, blank=True,
                                        verbose_name='Langue vivante')
    subjects_options = models.TextField(blank=True, verbose_name='Matières et options')

    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='inscrit',
                              verbose_name='Résultat / présence')
    exam_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                    verbose_name='Frais d’examen')
    fee_paid = models.BooleanField(default=False, verbose_name='Frais payés')
    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                    null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['student', 'session'], name='exam_unique_candidate',
            ),
            models.UniqueConstraint(
                fields=['session', 'official_number'], name='exam_unique_official_number',
                condition=models.Q(official_number__gt=''),
            ),
        ]
        ordering = ['registration_number', 'student__last_name']

    # ── Accès uniformes élève / candidat externe ──────────────────────────────
    @property
    def candidate_name(self):
        if self.student_id:
            return self.student.full_name
        return f'{self.external_last_name} {self.external_first_name}'.strip() or '—'

    @property
    def candidate_matricule(self):
        if self.student_id:
            return self.student.matricule
        return self.external_matricule

    @property
    def candidate_gender_display(self):
        if self.student_id:
            return self.student.get_gender_display()
        return dict(Student.GENDER_CHOICES).get(self.external_gender, '—')

    @property
    def candidate_birth_date(self):
        if self.student_id:
            return self.student.date_of_birth
        return self.external_date_of_birth

    def __str__(self):
        return f'{self.registration_number} — {self.candidate_name}'

    def save(self, *args, **kwargs):
        year = self.session.academic_year.name.replace('-', '')[-4:]
        if not self.registration_number:
            prefix = 'D' if self.session.type == 'def' else 'B'
            last = Candidate.objects.filter(
                registration_number__startswith=f'{prefix}{year}'
            ).order_by('-registration_number').values_list('registration_number', flat=True).first()
            n = 1
            if last:
                try:
                    n = int(last[-4:]) + 1
                except ValueError:
                    n = Candidate.objects.count() + 1
            self.registration_number = f'{prefix}{year}{n:04d}'
        if self.is_external and not self.external_matricule:
            prefix = f'EXT{year}'
            last = Candidate.objects.filter(
                external_matricule__startswith=prefix
            ).order_by('-external_matricule').values_list('external_matricule', flat=True).first()
            n = int(last[-4:]) + 1 if last and last[-4:].isdigit() else 1
            self.external_matricule = f'{prefix}{n:04d}'
        super().save(*args, **kwargs)
