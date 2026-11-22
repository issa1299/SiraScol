from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0003_expense_receipt_payment_cancelled_at_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='payment',
            name='tranche',
            field=models.CharField(
                blank=True,
                help_text='Ex. Tranche 1/3, Acompte, Solde…',
                max_length=30,
                verbose_name='Tranche',
            ),
        ),
    ]
