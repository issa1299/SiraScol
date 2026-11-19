from django.db import models
from django.contrib.auth.models import User
from academics.models import ClassRoom, Level, AcademicYear


class Announcement(models.Model):
    """Annonce / Communication"""
    TARGET_CHOICES = [
        ('all', 'Tout le monde'),
        ('teachers', 'Enseignants'),
        ('parents', 'Parents'),
        ('students', 'Élèves'),
        ('class', 'Classe spécifique'),
        ('level', 'Niveau spécifique'),
    ]

    title = models.CharField(max_length=200, verbose_name='Titre')
    content = models.TextField(verbose_name='Contenu')
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    target = models.CharField(max_length=20, choices=TARGET_CHOICES, default='all')
    classroom = models.ForeignKey(ClassRoom, on_delete=models.CASCADE, null=True, blank=True)
    level = models.ForeignKey(Level, on_delete=models.CASCADE, null=True, blank=True)
    is_published = models.BooleanField(default=True)
    published_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Annonce'
        verbose_name_plural = 'Annonces'
        ordering = ['-published_at']

    def __str__(self):
        return self.title


class Message(models.Model):
    """Message interne simple"""
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages')
    subject = models.CharField(max_length=200, verbose_name='Sujet')
    body = models.TextField(verbose_name='Message')
    attachment = models.FileField(
        upload_to='messages/%Y/%m/', blank=True, null=True,
        verbose_name='Pièce jointe',
    )
    is_read = models.BooleanField(default=False)
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Message'
        verbose_name_plural = 'Messages'
        ordering = ['-sent_at']

    def __str__(self):
        return f"{self.sender} → {self.recipient} : {self.subject}"

    def save(self, *args, **kwargs):
        if self._state.adding:
            from django.core.exceptions import PermissionDenied
            from core.messaging import can_message
            if not can_message(self.sender, self.recipient):
                raise PermissionDenied("Vous n'êtes pas autorisé à contacter ce destinataire.")
        super().save(*args, **kwargs)


class SchoolDocument(models.Model):
    """Document scolaire (règlement, circulaire, formulaire…)."""
    CATEGORY_CHOICES = [
        ('reglement', 'Règlement intérieur'),
        ('circulaire', 'Circulaire / note de service'),
        ('formulaire', 'Formulaire'),
        ('pedagogie', 'Pédagogie / programme'),
        ('examen', 'Examens / calendrier'),
        ('financier', 'Document financier'),
        ('autre', 'Autre'),
    ]

    title = models.CharField(max_length=200, verbose_name='Titre')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='autre')
    description = models.TextField(blank=True, verbose_name='Description')
    file = models.FileField(upload_to='documents/%Y/%m/', verbose_name='Fichier')
    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.SET_NULL, null=True, blank=True, related_name='school_documents'
    )
    is_published = models.BooleanField(default=True, verbose_name='Publié')
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Document scolaire'
        verbose_name_plural = 'Documents scolaires'
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    @property
    def filename(self):
        import os
        return os.path.basename(self.file.name) if self.file else ''

    @property
    def extension(self):
        name = self.filename.lower()
        if '.' in name:
            return name.rsplit('.', 1)[-1]
        return ''
