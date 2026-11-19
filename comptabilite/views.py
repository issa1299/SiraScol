# -*- coding: utf-8 -*-
"""Espace Comptable — opérations financières, avec séparation des rôles."""

from datetime import date, timedelta
from io import BytesIO

from django.contrib import messages
from django.contrib.auth.models import User
from django.db.models import Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from academics.models import AcademicYear, ClassRoom
from communication.models import Message
from core.messaging import allowed_recipients
from core.models import Notification
from core.permissions import role_required
from core.year_context import get_selected_year
from finance.models import Expense, FeeType, Invoice, Payment
from secretariat.pdf import document_pdf
from students.models import Enrollment, ParentStudent, Student


def _year():
    return get_selected_year(None) or AcademicYear.objects.filter(is_current=True).first() or \
        AcademicYear.objects.order_by('-start_date', '-id').first()


def _parent_users(student):
    users = []
    if student.user_id:
        users.append(student.user)
    for ps in ParentStudent.objects.filter(student=student).select_related('parent__user'):
        if ps.parent and ps.parent.user_id:
            users.append(ps.parent.user)
    return list(set(users))


def _period_bounds(period, year):
    today = date.today()
    if period == 'jour':
        return today, today
    if period == 'semaine':
        return today - timedelta(days=today.weekday()), today
    if period == 'mois':
        return today.replace(day=1), today
    if period == 'annee' and year and year.start_date and year.end_date:
        return year.start_date, min(today, year.end_date)
    if year and year.start_date:
        return year.start_date, today
    return today.replace(month=1, day=1), today


@role_required('comptable')
def dashboard(request):
    year = _year()
    invoices = Invoice.objects.filter(academic_year=year)
    expected = invoices.aggregate(s=Sum('amount'))['s'] or 0
    collected = sum(i.amount_paid for i in invoices)
    balance = expected - collected
    expenses = Expense.objects.filter(academic_year=year).aggregate(s=Sum('amount'))['s'] or 0
    unpaid = [i for i in invoices if i.balance > 0]
    parent_ids = set()
    for i in unpaid:
        for u in _parent_users(i.student):
            parent_ids.add(u.pk)
    return render(request, 'comptabilite/dashboard.html', {
        'year': year, 'expected': expected, 'collected': collected,
        'balance': balance, 'expenses': expenses, 'solde': collected - expenses,
        'nb_unpaid': len(parent_ids),
        'payments': Payment.objects.select_related('invoice__student').order_by('-created_at')[:12],
        'section': 'accueil',
    })


@role_required('comptable')
def frais(request):
    year = _year()
    if request.method == 'POST' and request.POST.get('action') == 'tarif':
        fee_id = request.POST.get('fee_type')
        amount = request.POST.get('amount', '0').replace(',', '.')
        fee = FeeType.objects.filter(pk=fee_id).first()
        if fee:
            fee.default_amount = amount
            fee.save(update_fields=['default_amount'])
            messages.success(request, f'Tarif {fee.name} mis à jour.')
        return redirect('comptabilite:frais')

    if request.method == 'POST' and request.POST.get('action') == 'generer':
        fee = get_object_or_404(FeeType, pk=request.POST.get('fee_type'))
        classroom = get_object_or_404(ClassRoom, pk=request.POST.get('classroom'))
        due = request.POST.get('due_date') or date.today().isoformat()
        remise = request.POST.get('remise', '0').replace(',', '.') or '0'
        exempted = set(request.POST.getlist('exempt'))
        created = 0
        for enr in Enrollment.objects.filter(classroom=classroom, academic_year=year, is_active=True):
            if str(enr.student_id) in exempted:
                continue
            amount = max(0, float(fee.default_amount) - float(remise))
            Invoice.objects.get_or_create(
                student=enr.student, academic_year=year, fee_type=fee,
                defaults={
                    'amount': amount, 'due_date': due,
                    'description': f'{fee.name} — {classroom.name}'
                                   + (f' (remise {remise})' if float(remise) else ''),
                },
            )
            created += 1
        messages.success(request, f'{created} facture(s) générée(s) pour {classroom.name}.')
        return redirect('comptabilite:frais')

    classroom_id = request.GET.get('classroom', '')
    classroom = None
    students = []
    if classroom_id:
        classroom = ClassRoom.objects.filter(pk=classroom_id).first()
        if classroom:
            students = Student.objects.filter(
                enrollments__classroom=classroom, enrollments__is_active=True
            ).order_by('last_name', 'first_name')
    return render(request, 'comptabilite/frais.html', {
        'year': year, 'fees': FeeType.objects.filter(is_active=True),
        'classrooms': ClassRoom.objects.filter(academic_year=year).order_by('name'),
        'classroom': classroom, 'students': students,
        'today': date.today(), 'section': 'frais',
    })


@role_required('comptable')
def paiements(request):
    q = request.GET.get('q', '').strip()
    student = None
    invoices = Invoice.objects.none()
    if q:
        invoices = Invoice.objects.filter(
            Q(student__last_name__icontains=q) |
            Q(student__first_name__icontains=q) |
            Q(student__matricule__icontains=q)
        ).select_related('student', 'fee_type', 'academic_year').order_by('-due_date')
        student = invoices.first().student if invoices.exists() else None

    if request.method == 'POST':
        invoice = get_object_or_404(Invoice, pk=request.POST.get('invoice'))
        amount = request.POST.get('amount', '0').replace(',', '.')
        try:
            Payment.objects.create(
                invoice=invoice, amount=amount,
                payment_date=request.POST.get('payment_date') or date.today().isoformat(),
                method=request.POST.get('method', 'especes'),
                reference=request.POST.get('reference', ''),
                notes=request.POST.get('notes', ''),
                received_by=request.user.get_full_name() or request.user.username,
            )
            messages.success(request, 'Paiement enregistré et reçu généré.')
            for u in _parent_users(invoice.student):
                Notification.objects.create(
                    user=u, title='Paiement enregistré',
                    message=f'{amount} FCFA — {invoice.fee_type.name}',
                    category='paiement', link='/mon-espace-parent/paiements/',
                )
        except Exception as exc:
            messages.error(request, f'Erreur : {exc}')
        return redirect(f"{reverse('comptabilite:paiements')}?q={invoice.student.matricule}")

    payment_list = Payment.objects.select_related('invoice__student').order_by('-created_at')[:40]
    return render(request, 'comptabilite/paiements.html', {
        'q': q, 'invoices': invoices, 'student': student,
        'payments': payment_list, 'today': date.today(), 'section': 'paiements',
    })


@role_required('comptable')
def depenses(request):
    year = _year()
    if request.method == 'POST':
        try:
            Expense.objects.create(
                date=request.POST.get('date') or date.today().isoformat(),
                category=request.POST.get('category', 'autre'),
                amount=request.POST.get('amount', '0').replace(',', '.'),
                motif=request.POST.get('motif', '').strip() or 'Dépense',
                academic_year_id=request.POST.get('academic_year') or (year.pk if year else None),
                created_by=request.user,
                receipt=request.FILES.get('receipt'),
            )
            messages.success(request, 'Dépense enregistrée.')
        except Exception as exc:
            messages.error(request, f'Erreur : {exc}')
        return redirect('comptabilite:depenses')
    return render(request, 'comptabilite/depenses.html', {
        'year': year, 'expenses': Expense.objects.select_related('academic_year').order_by('-date')[:100],
        'today': date.today(), 'section': 'depenses',
    })


@role_required('comptable')
def impayes(request):
    year = _year()
    classroom_id = request.GET.get('classroom', '')
    invoices = Invoice.objects.filter(academic_year=year).select_related(
        'student', 'fee_type'
    ).order_by('due_date')
    if classroom_id:
        invoices = invoices.filter(student__enrollments__classroom_id=classroom_id,
                                   student__enrollments__is_active=True)
    rows = [{'invoice': i, 'balance': i.balance, 'late': i.due_date < date.today()}
            for i in invoices if i.balance > 0]
    return render(request, 'comptabilite/impayes.html', {
        'year': year, 'rows': rows,
        'classrooms': ClassRoom.objects.filter(academic_year=year).order_by('name'),
        'classroom_id': classroom_id, 'section': 'impayes',
    })


@require_POST
@role_required('comptable')
def rappel(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    users = _parent_users(invoice.student)
    for u in users:
        Notification.objects.create(
            user=u, title='Rappel de paiement',
            message=f'{invoice.fee_type.name} : reste {invoice.balance} FCFA, échéance {invoice.due_date.strftime("%d/%m/%Y")}',
            category='paiement', link='/mon-espace-parent/paiements/',
        )
    messages.success(request, f'Rappel envoyé à {len(users)} parent(s).')
    return redirect('comptabilite:impayes')


@role_required('comptable')
def impayes_pdf(request):
    year = _year()
    rows = [i for i in Invoice.objects.filter(academic_year=year).select_related('student', 'fee_type')
            if i.balance > 0]
    lines = [f'Année scolaire : {year.name if year else "—"}', '']
    for i in rows:
        lines.append(f'{i.student.last_name} {i.student.first_name} ({i.student.matricule}) — {i.fee_type.name} : reste {i.balance} FCFA')
    return document_pdf('Liste des impayés', lines, 'impayes.pdf')


@role_required('comptable')
def recus(request):
    payments = Payment.objects.select_related('invoice__student').order_by('-created_at')[:100]
    return render(request, 'comptabilite/recus.html', {
        'payments': payments, 'section': 'recus',
    })


@role_required('comptable')
def recu_pdf(request, pk):
    p = get_object_or_404(Payment, pk=pk)
    lines = [
        f'Reçu N° {p.receipt_number}',
        f'Date : {p.payment_date.strftime("%d/%m/%Y")}',
        '',
        f'Élève : {p.invoice.student.full_name} ({p.invoice.student.matricule})',
        f'Motif : {p.invoice.fee_type.name} — {p.invoice.academic_year.name}',
        f'Mode de paiement : {p.get_method_display()}',
        f'Référence : {p.reference or "—"}',
        '',
        f'Montant : {p.amount} FCFA',
    ]
    if p.is_cancelled:
        lines.append('ANNULÉ — ' + p.cancelled_reason)
    return document_pdf('Reçu de paiement', lines, f'recu_{p.pk}.pdf')


@require_POST
@role_required('comptable')
def annuler_paiement(request, pk):
    p = get_object_or_404(Payment, pk=pk)
    if p.is_cancelled:
        messages.info(request, 'Ce paiement est déjà annulé.')
    else:
        p.is_cancelled = True
        p.cancelled_reason = request.POST.get('reason', 'Annulation administrative')[:255]
        p.cancelled_at = timezone.now()
        p.save(update_fields=['is_cancelled', 'cancelled_reason', 'cancelled_at'])
        p.invoice.refresh_status()
        messages.success(request, 'Paiement annulé.')
    return redirect('comptabilite:recus')


@role_required('comptable')
def rapports(request):
    year = _year()
    period = request.GET.get('periode', 'mois')
    start, end = _period_bounds(period, year)
    payments = Payment.objects.filter(is_cancelled=False, payment_date__range=(start, end))
    expenses = Expense.objects.filter(date__range=(start, end))
    recettes = payments.aggregate(s=Sum('amount'))['s'] or 0
    depenses = expenses.aggregate(s=Sum('amount'))['s'] or 0
    fmt = request.GET.get('format', '')
    if fmt == 'excel':
        return _excel_report(period, start, end, payments, expenses, recettes, depenses)
    if fmt == 'pdf':
        lines = [f'Période : {period} ({start.strftime("%d/%m/%Y")} → {end.strftime("%d/%m/%Y")})', '',
                 f'Recettes : {recettes} FCFA', f'Dépenses : {depenses} FCFA', f'Solde : {recettes - depenses} FCFA', '']
        for p in payments[:40]:
            lines.append(f'+ {p.payment_date} {p.invoice.student.matricule} {p.amount} FCFA')
        for e in expenses[:40]:
            lines.append(f'- {e.date} {e.get_category_display()} {e.amount} FCFA')
        return document_pdf('Rapport financier', lines, 'rapport_financier.pdf')
    return render(request, 'comptabilite/rapports.html', {
        'year': year, 'period': period, 'start': start, 'end': end,
        'recettes': recettes, 'depenses': depenses, 'solde': recettes - depenses,
        'payments': payments.order_by('-payment_date')[:30],
        'expenses': expenses.order_by('-date')[:30], 'section': 'rapports',
    })


def _excel_report(period, start, end, payments, expenses, recettes, depenses):
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = 'Rapport financier'
    ws.append(['SiraScol — Rapport financier', period, start.isoformat(), end.isoformat()])
    ws.append([])
    ws.append(['Recettes', float(recettes)])
    ws.append(['Dépenses', float(depenses)])
    ws.append(['Solde', float(recettes - depenses)])
    ws.append([])
    ws.append(['Date', 'Type', 'Détail', 'Montant'])
    for p in payments:
        ws.append([p.payment_date.isoformat(), 'Recette', f'{p.invoice.student.matricule} — {p.invoice.fee_type.name}', float(p.amount)])
    for e in expenses:
        ws.append([e.date.isoformat(), 'Dépense', e.motif, float(e.amount)])
    buf = BytesIO()
    wb.save(buf)
    response = HttpResponse(buf.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="rapport_{period}.xlsx"'
    return response


@role_required('comptable')
def factures(request):
    qs = Invoice.objects.select_related(
        'student', 'fee_type', 'academic_year'
    ).order_by('-due_date')[:150]
    return render(request, 'comptabilite/factures.html', {
        'invoices': qs, 'section': 'factures',
    })


@role_required('comptable')
def notifications(request):
    qs = Notification.objects.filter(user=request.user).order_by('-created_at')[:60]
    if request.method == 'POST':
        Notification.objects.filter(
            user=request.user, id__in=request.POST.getlist('ids')
        ).update(is_read=True)
        messages.success(request, 'Notifications marquées comme lues.')
        return redirect('comptabilite:notifications')
    return render(request, 'comptabilite/notifications.html', {
        'notifications': qs, 'section': 'notifications',
    })


@role_required('comptable')
def messagerie(request):
    qs = Message.objects.filter(
        Q(sender=request.user) | Q(recipient=request.user)
    ).order_by('-sent_at')
    if request.method == 'POST':
        recipient = User.objects.filter(pk=request.POST.get('recipient'), is_active=True).first()
        subject = request.POST.get('subject', '').strip()
        body = request.POST.get('body', '').strip()
        if recipient and subject and body:
            Message.objects.create(
                sender=request.user, recipient=recipient,
                subject=subject, body=body,
                attachment=request.FILES.get('attachment'),
            )
            messages.success(request, 'Message envoyé.')
        else:
            messages.error(request, 'Destinataire, objet et message sont obligatoires.')
        return redirect('comptabilite:messagerie')
    return render(request, 'comptabilite/messagerie.html', {
        'conversations': qs[:60], 'contacts': allowed_recipients(request.user),
        'section': 'messages',
    })


@role_required('comptable')
def profil(request):
    return render(request, 'comptabilite/profil.html', {
        'user': request.user, 'profile': request.user.profile, 'section': 'profil',
    })
