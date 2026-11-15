from core.permissions import role_required, can, get_role, get_parent_students
from core.year_context import get_selected_year
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Sum, Q, Count
from django.utils import timezone
from decimal import Decimal, InvalidOperation

from .models import FeeType, Invoice, Payment, Expense
from students.models import Student
from academics.models import AcademicYear


@login_required
def finance_dashboard(request):
    """Centre Financier SiraScol — encaissements, dépenses, soldes."""
    from academics.models import ClassRoom
    from students.models import Enrollment
    from .models import Expense
    from datetime import date

    tab = request.GET.get('tab', 'dashboard')
    current_year = get_selected_year(request)
    classroom_id = request.GET.get('classroom', '')
    today = timezone.now().date()

    try:
        invoices = Invoice.objects.all()
        if current_year:
            invoices = invoices.filter(academic_year=current_year)
        payments = Payment.objects.filter(invoice__in=invoices).select_related(
            'invoice__student', 'invoice__fee_type', 'invoice'
        )
        expenses = Expense.objects.all()
        if current_year:
            expenses = expenses.filter(academic_year=current_year)

        if classroom_id:
            student_ids = Enrollment.objects.filter(
                classroom_id=classroom_id, is_active=True
            ).values_list('student_id', flat=True)
            invoices = invoices.filter(student_id__in=student_ids)
            payments = payments.filter(invoice__student_id__in=student_ids)

        total_paid = payments.aggregate(s=Sum('amount'))['s'] or Decimal('0')
        total_due = invoices.aggregate(s=Sum('amount'))['s'] or Decimal('0')
        total_expenses = expenses.aggregate(s=Sum('amount'))['s'] or Decimal('0')
        solde = total_paid - total_expenses
        today_paid = payments.filter(payment_date=today).aggregate(s=Sum('amount'))['s'] or Decimal('0')
        today_count = payments.filter(payment_date=today).count()
        nb_eleves = invoices.values('student_id').distinct().count()

        stats = {
            'encaise': total_paid,
            'depenses': total_expenses,
            'solde': solde,
            'total_due': total_due,
            'reste': total_due - total_paid,
            'nb_eleves': nb_eleves,
            'aujourdhui': today_count,
            'montant_jour': today_paid,
        }
        recent_payments = payments.order_by('-payment_date', '-id')[:30]
        recent_expenses = expenses.order_by('-date', '-id')[:20]
        classrooms = ClassRoom.objects.filter(
            academic_year=current_year
        ).order_by('level__order', 'name') if current_year else ClassRoom.objects.none()
        fee_types = FeeType.objects.filter(is_active=True)
        method_choices = Payment.METHOD_CHOICES
        expense_categories = Expense.CATEGORY_CHOICES
    except Exception as e:
        messages.warning(request, f"Finances : {e}")
        stats = {
            'encaise': 0, 'depenses': 0, 'solde': 0, 'total_due': 0, 'reste': 0,
            'nb_eleves': 0, 'aujourdhui': 0, 'montant_jour': 0,
        }
        recent_payments = []
        recent_expenses = []
        classrooms = []
        fee_types = []
        method_choices = Payment.METHOD_CHOICES
        expense_categories = []
        current_year = current_year

    # Élèves pour modal paiement
    students = []
    if classroom_id:
        from students.models import Enrollment
        students = [
            e.student for e in Enrollment.objects.filter(
                classroom_id=classroom_id, is_active=True
            ).select_related('student').order_by('student__last_name')
        ]

    pending_invoices = []
    try:
        pending_invoices = list(
            invoices.filter(status__in=['en_attente', 'partiel'])
            .select_related('student', 'fee_type')
            .order_by('student__last_name')[:100]
        )
    except Exception:
        pass

    return render(request, 'finance/dashboard.html', {
        'stats': stats,
        'current_year': current_year,
        'recent_payments': recent_payments,
        'recent_expenses': recent_expenses,
        'tab': tab,
        'classrooms': classrooms,
        'classroom_id': classroom_id,
        'fee_types': fee_types,
        'method_choices': method_choices,
        'expense_categories': expense_categories,
        'students': students,
        'today': today.isoformat(),
        'pending_invoices': pending_invoices,
    })


@login_required
def finance_report(request):
    """Rapport financier journalier / période — prévisualisation imprimable."""
    from .models import Expense
    from core.models import SchoolSettings
    from datetime import datetime

    current_year = get_selected_year(request)
    date_str = request.GET.get('date', '')
    try:
        report_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else timezone.now().date()
    except ValueError:
        report_date = timezone.now().date()

    payments = Payment.objects.filter(payment_date=report_date).select_related(
        'invoice__student', 'invoice__fee_type', 'invoice'
    )
    if current_year:
        payments = payments.filter(invoice__academic_year=current_year)
    expenses = Expense.objects.filter(date=report_date)
    if current_year:
        expenses = expenses.filter(academic_year=current_year)

    total_recettes = payments.aggregate(s=Sum('amount'))['s'] or Decimal('0')
    total_depenses = expenses.aggregate(s=Sum('amount'))['s'] or Decimal('0')
    solde_net = total_recettes - total_depenses

    # Par type de frais
    by_type = {}
    for p in payments:
        name = p.invoice.fee_type.name if p.invoice.fee_type_id else 'Autre'
        by_type.setdefault(name, {'count': 0, 'amount': Decimal('0')})
        by_type[name]['count'] += 1
        by_type[name]['amount'] += p.amount

    try:
        school = SchoolSettings.get_solo()
    except Exception:
        school = None

    return render(request, 'finance/report_daily.html', {
        'report_date': report_date,
        'payments': payments,
        'expenses': expenses,
        'total_recettes': total_recettes,
        'total_depenses': total_depenses,
        'solde_net': solde_net,
        'by_type': by_type,
        'nb_paiements': payments.count(),
        'school': school,
        'current_year': current_year,
        'print_mode': request.GET.get('print') == '1',
        'agent': request.user.get_full_name() or request.user.username,
    })


@login_required
def student_finance_card(request, student_id):
    """Carte financière d'un élève (payé / dû / reste + historique)."""
    student = get_object_or_404(Student, pk=student_id)
    current_year = get_selected_year(request)
    invoices = Invoice.objects.filter(student=student)
    if current_year:
        invoices = invoices.filter(academic_year=current_year)
    invoices = invoices.select_related('fee_type')
    total_due = invoices.aggregate(s=Sum('amount'))['s'] or Decimal('0')
    payments = Payment.objects.filter(invoice__in=invoices).select_related(
        'invoice__fee_type'
    ).order_by('-payment_date')
    total_paid = payments.aggregate(s=Sum('amount'))['s'] or Decimal('0')
    reste = total_due - total_paid

    from students.models import Enrollment
    enr = Enrollment.objects.filter(student=student, is_active=True).select_related('classroom').first()

    ctx = {
        'student': student,
        'classroom': enr.classroom if enr else None,
        'total_paid': total_paid,
        'total_due': total_due,
        'reste': reste,
        'payments': payments,
        'invoices': invoices,
        'current_year': current_year,
    }
    if request.GET.get('modal') == '1':
        return render(request, 'finance/student_card_modal.html', ctx)
    return render(request, 'finance/student_card.html', ctx)


@login_required
def invoice_list(request):
    try:
        qs = Invoice.objects.select_related('student', 'fee_type', 'academic_year').order_by('-created_at')
    except Exception:
        messages.error(request, "Tables finances absentes. Exécute : python manage.py makemigrations && python manage.py migrate")
        return render(request, 'finance/invoice_list.html', {
            'invoices': [], 'q': '', 'status': '', 'status_choices': Invoice.STATUS_CHOICES,
        })

    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(
            Q(student__last_name__icontains=q) |
            Q(student__first_name__icontains=q) |
            Q(student__matricule__icontains=q)
        )
    status = request.GET.get('status', '')
    if status:
        qs = qs.filter(status=status)

    invoices = Paginator(qs, 20).get_page(request.GET.get('page'))
    return render(request, 'finance/invoice_list.html', {
        'invoices': invoices, 'q': q, 'status': status, 'status_choices': Invoice.STATUS_CHOICES,
    })


@login_required
def invoice_create(request):
    students = Student.objects.filter(status='actif').order_by('last_name', 'first_name')
    fee_types = FeeType.objects.filter(is_active=True)
    years = AcademicYear.objects.all()
    current_year = get_selected_year(request)

    if request.method == 'POST':
        try:
            student = Student.objects.get(pk=request.POST.get('student'))
            fee_type = FeeType.objects.get(pk=request.POST.get('fee_type'))
            year = AcademicYear.objects.get(pk=request.POST.get('academic_year'))
            amount = Decimal(request.POST.get('amount', '0').replace(',', '.'))
            due_date = request.POST.get('due_date')
            description = request.POST.get('description', '')
            inv = Invoice.objects.create(
                student=student, fee_type=fee_type, academic_year=year,
                amount=amount, due_date=due_date, description=description,
            )
            messages.success(request, f"Facture créée pour {student}.")
            return redirect('finance:invoices')
        except Exception as e:
            messages.error(request, f"Erreur : {e}")

    ctx = {
        'students': students,
        'fee_types': fee_types,
        'years': years,
        'current_year': current_year,
        'today': timezone.now().date().isoformat(),
        'form_action': request.path,
    }
    if request.GET.get('modal') == '1' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'finance/invoice_form_modal.html', ctx)
    return render(request, 'finance/invoice_form.html', ctx)


@login_required
def payment_create(request):
    if request.method == 'POST':
        try:
            amount = Decimal(request.POST.get('amount', '').strip().replace(',', '.'))
            invoice = Invoice.objects.get(pk=request.POST.get('invoice'))
            pay = Payment.objects.create(
                invoice=invoice,
                amount=amount,
                payment_date=request.POST.get('payment_date'),
                method=request.POST.get('method', 'especes'),
                reference=request.POST.get('reference', ''),
                received_by=request.POST.get('received_by') or (
                    request.user.get_full_name() or request.user.username
                ),
                notes=request.POST.get('notes', ''),
            )
            messages.success(request, f"Paiement de {amount} enregistré pour {invoice.student}.")
            nxt = request.POST.get('next')
            if nxt and nxt.startswith('/'):
                return redirect(nxt)
            return redirect('finance:receipt', pk=pay.pk)
        except Exception as e:
            messages.error(request, f"Erreur : {e}")

    try:
        open_invoices = (
            Invoice.objects.filter(status__in=['en_attente', 'partiel'])
            .select_related('student', 'fee_type')
            .order_by('student__last_name')
        )
    except Exception:
        open_invoices = []
        messages.warning(request, "Aucune facture disponible. Crée d'abord une facture.")

    ctx = {
        'open_invoices': open_invoices,
        'method_choices': Payment.METHOD_CHOICES,
        'today': timezone.now().date().isoformat(),
        'form_action': request.path,
    }
    if request.GET.get('modal') == '1' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'finance/payment_form_modal.html', ctx)
    return render(request, 'finance/payment_form.html', ctx)


@login_required
def payment_receipt(request, pk):
    """Reçu de paiement imprimable / PDF HTML"""
    payment = get_object_or_404(
        Payment.objects.select_related(
            'invoice__student', 'invoice__fee_type', 'invoice__academic_year'
        ),
        pk=pk
    )
    try:
        from core.models import SchoolSettings
        school = SchoolSettings.get_solo()
    except Exception:
        school = None
    return render(request, 'finance/payment_receipt.html', {
        'payment': payment,
        'invoice': payment.invoice,
        'student': payment.invoice.student,
        'school': school,
        'print_mode': request.GET.get('print') == '1',
    })


@login_required
def finance_classes(request):
    """Liste des classes avec résumé des soldes."""
    from academics.models import ClassRoom, AcademicYear
    from students.models import Enrollment
    from django.db.models import Count

    year = get_selected_year(request)
    qs = ClassRoom.objects.select_related('level', 'academic_year', 'main_teacher')
    if year:
        qs = qs.filter(academic_year=year)
    qs = qs.annotate(
        nb_eleves=Count('enrollments', filter=Q(enrollments__is_active=True))
    ).order_by('level__order', 'name')

    classes_data = []
    for room in qs:
        student_ids = list(
            Enrollment.objects.filter(classroom=room, is_active=True)
            .values_list('student_id', flat=True)
        )
        invoices = Invoice.objects.filter(student_id__in=student_ids)
        if year:
            invoices = invoices.filter(academic_year=year)
        total_due = invoices.aggregate(s=Sum('amount'))['s'] or Decimal('0')
        total_paid = Payment.objects.filter(invoice__in=invoices).aggregate(s=Sum('amount'))['s'] or Decimal('0')
        classes_data.append({
            'classroom': room,
            'nb_eleves': room.nb_eleves,
            'total_due': total_due,
            'total_paid': total_paid,
            'balance': total_due - total_paid,
        })

    return render(request, 'finance/classes.html', {
        'classes_data': classes_data,
        'current_year': year,
    })


@login_required
def finance_class_students(request, classroom_id):
    """Élèves d'une classe avec soldes + recherche."""
    from academics.models import ClassRoom, AcademicYear
    from students.models import Enrollment, Student

    classroom = get_object_or_404(
        ClassRoom.objects.select_related('level', 'academic_year'),
        pk=classroom_id,
    )
    year = classroom.academic_year or get_selected_year(request)
    q = request.GET.get('q', '').strip()

    enrollments = (
        Enrollment.objects.filter(classroom=classroom, is_active=True)
        .select_related('student')
        .order_by('student__last_name', 'student__first_name')
    )
    if q:
        enrollments = enrollments.filter(
            Q(student__last_name__icontains=q)
            | Q(student__first_name__icontains=q)
            | Q(student__matricule__icontains=q)
        )

    students_data = []
    for enr in enrollments:
        student = enr.student
        invoices = Invoice.objects.filter(student=student)
        if year:
            invoices = invoices.filter(academic_year=year)
        total_due = invoices.aggregate(s=Sum('amount'))['s'] or Decimal('0')
        total_paid = Payment.objects.filter(invoice__in=invoices).aggregate(s=Sum('amount'))['s'] or Decimal('0')
        balance = total_due - total_paid
        students_data.append({
            'student': student,
            'total_due': total_due,
            'total_paid': total_paid,
            'balance': balance,
            'invoices': list(invoices.select_related('fee_type')),
        })

    return render(request, 'finance/class_students.html', {
        'classroom': classroom,
        'students_data': students_data,
        'q': q,
        'current_year': year,
        'method_choices': Payment.METHOD_CHOICES,
        'today': timezone.now().date().isoformat(),
    })


@login_required
def student_payment_modal(request, student_id):
    """Formulaire modal de paiement pour un élève (GET fragment / POST)."""
    from students.models import Student
    from academics.models import AcademicYear

    student = get_object_or_404(Student, pk=student_id)
    year = get_selected_year(request)
    invoices = Invoice.objects.filter(
        student=student,
        status__in=['en_attente', 'partiel'],
    ).select_related('fee_type')
    if year:
        invoices = invoices.filter(academic_year=year)

    if request.method == 'POST':
        try:
            amount = Decimal(request.POST.get('amount', '').strip().replace(',', '.'))
            invoice_id = request.POST.get('invoice')
            if invoice_id:
                invoice = Invoice.objects.get(pk=invoice_id, student=student)
                pay = Payment.objects.create(
                    invoice=invoice,
                    amount=amount,
                    payment_date=request.POST.get('payment_date') or timezone.now().date(),
                    method=request.POST.get('method', 'especes'),
                    reference=request.POST.get('reference', ''),
                    received_by=request.POST.get('received_by') or (
                        request.user.get_full_name() or request.user.username
                    ),
                    notes=request.POST.get('notes', ''),
                )
                messages.success(request, f"Paiement de {amount} enregistré pour {student}.")
                next_url = request.POST.get('next') or request.GET.get('next')
                if next_url:
                    return redirect(next_url)
                return redirect('finance:receipt', pk=pay.pk)
            else:
                # Répartir sur toutes les factures ouvertes (inscription d'abord)
                remaining = amount
                last_pay = None
                for inv in invoices.order_by('due_date', 'id'):
                    if remaining <= 0:
                        break
                    bal = inv.balance
                    if bal <= 0:
                        continue
                    pay_amt = min(remaining, Decimal(str(bal)))
                    last_pay = Payment.objects.create(
                        invoice=inv,
                        amount=pay_amt,
                        payment_date=request.POST.get('payment_date') or timezone.now().date(),
                        method=request.POST.get('method', 'especes'),
                        reference=request.POST.get('reference', ''),
                        received_by=request.POST.get('received_by') or (
                            request.user.get_full_name() or request.user.username
                        ),
                        notes=request.POST.get('notes', '') or 'Paiement élève',
                    )
                    remaining -= pay_amt
                if last_pay:
                    messages.success(request, f"Paiement enregistré pour {student}.")
                    next_url = request.POST.get('next') or request.GET.get('next')
                    if next_url:
                        return redirect(next_url)
                    return redirect('finance:receipt', pk=last_pay.pk)
                messages.error(request, "Aucune facture ouverte ou montant invalide.")
        except Exception as e:
            messages.error(request, f"Erreur : {e}")

    total_due = sum((Decimal(str(i.amount)) for i in invoices), Decimal('0'))
    total_balance = sum((Decimal(str(i.balance)) for i in invoices), Decimal('0'))

    ctx = {
        'student': student,
        'invoices': invoices,
        'method_choices': Payment.METHOD_CHOICES,
        'today': timezone.now().date().isoformat(),
        'total_due': total_due,
        'total_balance': total_balance,
        'form_action': request.path,
        'next': request.GET.get('next', ''),
    }
    if request.GET.get('modal') == '1' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'finance/student_payment_modal.html', ctx)
    return render(request, 'finance/student_payment_modal.html', ctx)


@login_required
def expense_create(request):
    """Modal / page : enregistrer une dépense."""
    from .models import Expense
    from core.year_context import get_selected_year
    from datetime import date

    year = get_selected_year(request)
    if request.method == 'POST':
        try:
            amount = request.POST.get('amount', '').replace(' ', '').replace(',', '.')
            from decimal import Decimal
            exp = Expense(
                date=request.POST.get('date') or date.today().isoformat(),
                category=request.POST.get('category') or 'autre',
                amount=Decimal(amount),
                currency=request.POST.get('currency') or 'FCFA',
                motif=(request.POST.get('motif') or '').strip() or 'Dépense',
                academic_year=year,
                created_by=request.user,
            )
            exp.save()
            messages.success(request, f'Dépense enregistrée : {exp.amount} {exp.currency}')
        except Exception as e:
            messages.error(request, f'Erreur dépense : {e}')
        next_url = request.POST.get('next') or request.GET.get('next') or 'finance:dashboard'
        if next_url.startswith('/'):
            return redirect(next_url)
        return redirect(next_url)
    ctx = {
        'today': date.today().isoformat(),
        'categories': Expense.CATEGORY_CHOICES,
        'form_action': request.path,
    }
    if request.GET.get('modal') == '1' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'finance/expense_form_modal.html', ctx)
    return render(request, 'finance/expense_form.html', ctx)
