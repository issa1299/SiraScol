from django.db import models
from django.core.validators import MinValueValidator
from django.db.models import Sum
from students.models import Student
from academics.models import AcademicYear


class FeeType(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name='Nom')
    description = models.TextField(blank=True)
    default_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Type de frais'
        verbose_name_plural = 'Types de frais'

    def __str__(self):
        return self.name


class Invoice(models.Model):
    STATUS_CHOICES = [
        ('en_attente', 'En attente'),
        ('partiel', 'Partiellement payé'),
        ('paye', 'Payé'),
        ('annule', 'Annulé'),
    ]

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='invoices')
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='invoices')
    fee_type = models.ForeignKey(FeeType, on_delete=models.PROTECT, related_name='invoices')
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    due_date = models.DateField(verbose_name="Date d'échéance")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='en_attente')
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Facture'
        verbose_name_plural = 'Factures'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.student} - {self.fee_type} ({self.amount})"

    @property
    def amount_paid(self):
        total = self.payments.filter(is_cancelled=False).aggregate(s=Sum('amount'))['s']
        return total if total is not None else 0

    @property
    def balance(self):
        try:
            return self.amount - self.amount_paid
        except Exception:
            return self.amount

    def refresh_status(self):
        paid = self.amount_paid
        if self.status == 'annule':
            return
        if paid >= self.amount:
            self.status = 'paye'
        elif paid > 0:
            self.status = 'partiel'
        else:
            self.status = 'en_attente'
        Invoice.objects.filter(pk=self.pk).update(status=self.status)


class Payment(models.Model):
    METHOD_CHOICES = [
        ('especes', 'Espèces'),
        ('virement', 'Virement'),
        ('cheque', 'Chèque'),
        ('mobile_money', 'Mobile Money'),
        ('autre', 'Autre'),
    ]

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0.01)])
    payment_date = models.DateField(verbose_name='Date de paiement')
    method = models.CharField(max_length=20, choices=METHOD_CHOICES, default='especes')
    reference = models.CharField(max_length=100, blank=True, verbose_name='Référence')
    received_by = models.CharField(max_length=100, blank=True, verbose_name='Reçu par')
    notes = models.TextField(blank=True)
    is_cancelled = models.BooleanField(default=False, verbose_name='Annulé')
    cancelled_reason = models.CharField(max_length=255, blank=True, verbose_name='Motif d’annulation')
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Paiement'
        verbose_name_plural = 'Paiements'
        ordering = ['-payment_date']

    def __str__(self):
        return f"Paiement {self.amount} - {self.invoice.student}"

    @property
    def receipt_number(self):
        d = self.payment_date or self.created_at
        if hasattr(d, 'strftime'):
            return f"REC-{d.strftime('%Y%m')}-{self.pk:04d}"
        return f"REC-{self.pk:04d}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        try:
            self.invoice.refresh_status()
        except Exception:
            pass


class Expense(models.Model):
    """Dépense de l'établissement (salaires, fournitures…)."""
    CATEGORY_CHOICES = [
        ('salaires', 'Salaires'),
        ('fournitures', 'Fournitures'),
        ('entretien', 'Entretien / maintenance'),
        ('electricite', 'Électricité / eau'),
        ('transport', 'Transport'),
        ('communication', 'Communication'),
        ('autre', 'Autre'),
    ]

    date = models.DateField(verbose_name='Date')
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, verbose_name='Catégorie')
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0.01)])
    currency = models.CharField(max_length=10, default='FCFA', verbose_name='Devise')
    motif = models.CharField(max_length=255, verbose_name='Motif')
    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.SET_NULL, null=True, blank=True, related_name='expenses'
    )
    created_by = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True
    )
    receipt = models.FileField(
        upload_to='justificatifs/%Y/%m/', blank=True, null=True,
        verbose_name='Pièce justificative',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Dépense'
        verbose_name_plural = 'Dépenses'
        ordering = ['-date', '-id']

    def __str__(self):
        return f"{self.date} — {self.get_category_display()} — {self.amount}"
