import re

from core.account_sync import ensure_user_for_student, ensure_user_for_parent
from core.year_context import get_selected_year
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from core.permissions import (
    get_role, get_parent_students, is_staff_role, permission_required, can, role_required,
)
from core.access import filter_students_for_user, get_student_for_user, filter_classrooms_for_user
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.core.paginator import Paginator
from django.utils import timezone

from .models import Student, Enrollment, Parent, ParentStudent
from .forms import StudentForm, EnrollmentForm, ParentInfoForm
from .import_service import (
    parse_file, validate_rows, import_from_preview,
    sample_csv, sample_xlsx, error_report_xlsx,
)
from academics.models import ClassRoom, AcademicYear


def _ensure_fee_types():
    """Crée les types de frais Inscription et Scolarité s'ils n'existent pas."""
    try:
        from finance.models import FeeType
        ins, _ = FeeType.objects.get_or_create(
            name="Frais d'inscription",
            defaults={'default_amount': 0, 'is_active': True},
        )
        sco, _ = FeeType.objects.get_or_create(
            name='Scolarité',
            defaults={'default_amount': 0, 'is_active': True},
        )
        return ins, sco
    except Exception:
        return None, None


def _create_invoices_for_enrollment(student, classroom, year, enrollment_date):
    """Crée les factures inscription + scolarité. Retourne la liste des factures."""
    invoices = []
    try:
        from finance.models import Invoice
    except Exception:
        return invoices

    ins_type, sco_type = _ensure_fee_types()
    if not ins_type:
        return invoices

    due = enrollment_date or timezone.now().date()
    due_tuition = due + timedelta(days=30)

    if classroom.inscription_fee and classroom.inscription_fee > 0:
        inv, _ = Invoice.objects.get_or_create(
            student=student,
            academic_year=year,
            fee_type=ins_type,
            defaults={
                'amount': classroom.inscription_fee,
                'due_date': due,
                'status': 'en_attente',
                'description': f"Inscription — {classroom.name}",
            },
        )
        invoices.append(inv)
    if classroom.tuition_fee and classroom.tuition_fee > 0:
        inv, _ = Invoice.objects.get_or_create(
            student=student,
            academic_year=year,
            fee_type=sco_type,
            defaults={
                'amount': classroom.tuition_fee,
                'due_date': due_tuition,
                'status': 'en_attente',
                'description': f"Scolarité — {classroom.name}",
            },
        )
        invoices.append(inv)
    return invoices


def _apply_enrollment_payment(student, invoices, amount_paid, payment_date, received_by=''):
    """
    Répartit le montant payé sur les factures (inscription d'abord, puis scolarité).
    Retourne le total réellement enregistré.
    """
    if not amount_paid or amount_paid <= 0 or not invoices:
        return Decimal('0')
    try:
        from finance.models import Payment
    except Exception:
        return Decimal('0')

    remaining = Decimal(str(amount_paid))
    total_recorded = Decimal('0')
    pay_date = payment_date or timezone.now().date()

    for inv in invoices:
        if remaining <= 0:
            break
        # Montant déjà payé sur cette facture
        already = sum((p.amount for p in inv.payments.all()), Decimal('0'))
        due = Decimal(str(inv.amount)) - already
        if due <= 0:
            continue
        pay_amt = min(remaining, due)
        Payment.objects.create(
            invoice=inv,
            amount=pay_amt,
            payment_date=pay_date,
            method='especes',
            received_by=received_by or 'Inscription',
            notes="Paiement a l'inscription",
        )
        remaining -= pay_amt
        total_recorded += pay_amt
    return total_recorded


@login_required
@permission_required('students.view')
def student_list(request):
    year = get_selected_year(request)
    role = get_role(request.user)
    # Filtrage serveur selon le rôle (parent / enseignant / élève / staff)
    qs = filter_students_for_user(request.user).order_by('last_name', 'first_name')

    # Année de travail : uniquement les élèves inscrits cette année
    if year:
        qs = qs.filter(
            enrollments__academic_year=year,
            enrollments__is_active=True,
        ).distinct()

    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(
            Q(matricule__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q)
        )
    status = request.GET.get('status', '')
    if status:
        qs = qs.filter(status=status)
    classroom_id = request.GET.get('classroom', '')
    if classroom_id:
        qs = qs.filter(enrollments__classroom_id=classroom_id, enrollments__is_active=True)
    gender = request.GET.get('gender', '')
    if gender:
        qs = qs.filter(gender=gender)

    # Stats on filtered base (before pagination)
    n_total = qs.count()
    n_actifs = qs.filter(status='actif').count()
    n_boys = qs.filter(gender='M').count()
    n_girls = qs.filter(gender='F').count()

    students = Paginator(qs, 25).get_page(request.GET.get('page'))
    # Prefetch for table
    student_ids = [s.id for s in students]
    enr_map = {}
    parent_map = {}
    finance_map = {}
    if student_ids and year:
        for e in Enrollment.objects.filter(
            student_id__in=student_ids, academic_year=year, is_active=True
        ).select_related('classroom'):
            enr_map[e.student_id] = e
    if student_ids:
        for ps in ParentStudent.objects.filter(student_id__in=student_ids).select_related('parent'):
            if ps.student_id not in parent_map:
                parent_map[ps.student_id] = ps.parent
        try:
            from finance.models import Invoice, Payment
            from decimal import Decimal
            for inv in Invoice.objects.filter(student_id__in=student_ids).exclude(status='annule'):
                if year and inv.academic_year_id != year.id:
                    continue
                fm = finance_map.setdefault(inv.student_id, {'due': Decimal('0'), 'paid': Decimal('0')})
                fm['due'] += inv.amount
            for pay in Payment.objects.filter(invoice__student_id__in=student_ids):
                if year and pay.invoice.academic_year_id != year.id:
                    continue
                fm = finance_map.setdefault(pay.invoice.student_id, {'due': Decimal('0'), 'paid': Decimal('0')})
                fm['paid'] += pay.amount
        except Exception:
            pass

    rows = []
    from datetime import date as date_cls
    today = date_cls.today()
    for s in students:
        enr = enr_map.get(s.id)
        age = ''
        if s.date_of_birth:
            age = today.year - s.date_of_birth.year - (
                (today.month, today.day) < (s.date_of_birth.month, s.date_of_birth.day)
            )
        par = parent_map.get(s.id)
        fin = finance_map.get(s.id, {})
        due = fin.get('due', 0) or 0
        paid = fin.get('paid', 0) or 0
        rows.append({
            'student': s,
            'classroom': enr.classroom if enr else None,
            'age': age,
            'parent': par,
            'due': due,
            'paid': paid,
            'reste': (due - paid) if due else 0,
        })

    classrooms = ClassRoom.objects.select_related('level', 'academic_year').all()
    if year:
        classrooms = classrooms.filter(academic_year=year)
    from .forms import StudentForm, EnrollmentForm
    return render(request, 'students/student_list.html', {
        'students': students, 'rows': rows,
        'q': q, 'status': status, 'gender': gender,
        'classroom_id': classroom_id, 'classrooms': classrooms,
        'status_choices': Student.STATUS_CHOICES,
        'stats': {'total': n_total, 'actifs': n_actifs, 'boys': n_boys, 'girls': n_girls},
        'form': StudentForm(initial={'enrollment_date': timezone.now().date(), 'status': 'actif'}),
        'enr_form': EnrollmentForm(),
        'classrooms_fees': [
            {
                'id': c['id'],
                'name': c['name'],
                'inscription_fee': str(c['inscription_fee'] or 0),
                'tuition_fee': str(c['tuition_fee'] or 0),
            }
            for c in (
                ClassRoom.objects.filter(academic_year=year).values('id', 'name', 'inscription_fee', 'tuition_fee')
                if year else ClassRoom.objects.values('id', 'name', 'inscription_fee', 'tuition_fee')
            )
        ],
        'selected_year': year,
    })


@login_required
@permission_required('students.view')
def student_detail(request, pk):
    # Anti-contournement URL : parent/élève/enseignant ne voient que leurs élèves
    student = get_student_for_user(request.user, pk)
    enrollments = student.enrollments.select_related('classroom', 'academic_year').order_by('-academic_year__start_date')
    parents = student.parents.select_related('parent').all()
    recent_grades = student.grades.select_related('assessment__subject', 'assessment').order_by('-assessment__date')[:15]
    absences = student.absences.order_by('-date')[:10]
    # Finance summary
    invoices = []
    payments = []
    total_due = total_paid = balance = 0
    try:
        from finance.models import Invoice, Payment
        from decimal import Decimal
        from django.db.models import Sum
        invoices = list(
            Invoice.objects.filter(student=student)
            .select_related('fee_type', 'academic_year')
            .order_by('-created_at')
        )
        payments = list(
            Payment.objects.filter(invoice__student=student)
            .select_related('invoice__fee_type')
            .order_by('-payment_date')[:20]
        )
        total_due = sum((Decimal(str(i.amount)) for i in invoices), Decimal('0'))
        total_paid = Payment.objects.filter(invoice__student=student).aggregate(s=Sum('amount'))['s'] or Decimal('0')
        balance = total_due - total_paid
    except Exception:
        pass

    ctx = {
        'student': student, 'enrollments': enrollments, 'parents': parents,
        'recent_grades': recent_grades, 'absences': absences,
        'current_enrollment': student.current_enrollment(),
        'invoices': invoices, 'payments': payments,
        'total_due': total_due, 'total_paid': total_paid, 'balance': balance,
    }
    if request.GET.get('modal') == '1' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'students/student_detail_modal.html', ctx)
    return render(request, 'students/student_detail.html', ctx)


@login_required
@permission_required('students.create')
def student_create(request):
    year = get_selected_year(request)
    qs = ClassRoom.objects.select_related('level', 'academic_year')
    if year:
        qs_year = qs.filter(academic_year=year)
        if qs_year.exists():
            qs = qs_year
    classrooms_fees = list(qs.values('id', 'name', 'inscription_fee', 'tuition_fee'))
    for c in classrooms_fees:
        c['inscription_fee'] = str(c.get('inscription_fee') or 0)
        c['tuition_fee'] = str(c.get('tuition_fee') or 0)

    if request.method == 'POST':
        form = StudentForm(request.POST, request.FILES)
        enr_form = EnrollmentForm(request.POST)
        parent_form = ParentInfoForm(request.POST, prefix='parent')
        success_msg = ''
        if form.is_valid() and enr_form.is_valid() and parent_form.is_valid():
            classroom = enr_form.cleaned_data.get('classroom')
            enr_year = enr_form.cleaned_data.get('academic_year')
            if not classroom or not enr_year:
                messages.error(request, "Choisissez la classe et l'année scolaire de l'élève.")
            else:
                with transaction.atomic():
                    student = form.save()  # matricule généré automatiquement
                    Enrollment.objects.create(
                        student=student, classroom=classroom,
                        academic_year=enr_year,
                        enrollment_date=student.enrollment_date or timezone.now().date(),
                        is_active=True,
                    )
                    invoices = _create_invoices_for_enrollment(
                        student, classroom, enr_year, student.enrollment_date
                    )
                    paid_msg = ''
                    paid_raw = (request.POST.get('amount_paid') or '').strip().replace(',', '.')
                    if paid_raw:
                        try:
                            amount_paid = Decimal(paid_raw)
                        except Exception:
                            amount_paid = Decimal('0')
                        if amount_paid > 0:
                            received = request.user.get_full_name() or request.user.username
                            recorded = _apply_enrollment_payment(
                                student, invoices, amount_paid,
                                student.enrollment_date, received_by=received,
                            )
                            paid_msg = f' Paiement enregistré : {recorded}.'

                    pdata = parent_form.cleaned_data
                    parent = pdata.get('existing_parent')
                    pfirst = (pdata.get('first_name') or '').strip()
                    plast = (pdata.get('last_name') or '').strip()
                    pphone = (pdata.get('phone') or '').strip()
                    parent_msg = ''
                    parent_created = False
                    if not parent and (pfirst or plast or pphone):
                        parent, parent_created = Parent.objects.get_or_create(
                            phone=pphone or 'NON-RENSEIGNE',
                            first_name=pfirst or 'Parent',
                            last_name=plast or student.last_name,
                            defaults={
                                'phone2': pdata.get('phone2') or '',
                                'email': pdata.get('email') or '',
                            },
                        )
                    if parent:
                        ParentStudent.objects.get_or_create(
                            parent=parent, student=student,
                            defaults={
                                'relation': pdata.get('relation') or 'pere',
                                'is_primary': bool(pdata.get('is_primary')),
                            },
                        )
                        pu, p_user_created, p_pwd = ensure_user_for_parent(parent)
                        # Le signal crée déjà le compte :pwd est alors None.
                        # Mot de passe initial = téléphone (ou identifiant si absent).
                        if parent_created or p_user_created:
                            parent_msg = (
                                f" Compte parent : {pu.username} / mdp : "
                                f"{p_pwd or parent.phone or pu.username}."
                            )

                    user_acc, _created_acc, pwd = ensure_user_for_student(student)
                    # Le signal post_save crée le compte avant cet appel : pwd vaut None.
                    # Le mot de passe initial est donc le matricule (voir account_sync).
                    cred = (
                        f" Compte élève : {user_acc.username} / mdp : "
                        f"{pwd or student.matricule}."
                    )
                    success_msg = (
                        f"Élève {student} inscrit (matricule {student.matricule}) "
                        f"en {classroom.name} — {enr_year.name}."
                        + paid_msg + ' ' + cred + ' ' + parent_msg
                    )
                messages.success(request, success_msg)
                return redirect('students:detail', pk=student.pk)
    else:
        form = StudentForm(initial={'enrollment_date': timezone.now().date(), 'status': 'actif'})
        enr_form = EnrollmentForm()
        parent_form = ParentInfoForm(prefix='parent')

    ctx = {
        'form': form, 'enr_form': enr_form, 'parent_form': parent_form,
        'title': 'Nouvel élève', 'is_edit': False,
        'classrooms_fees': classrooms_fees,
    }
    if request.GET.get('modal') == '1' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        ctx['form_action'] = request.path
        return render(request, 'students/student_form_modal.html', ctx)
    return render(request, 'students/student_form.html', ctx)


@login_required
@permission_required('students.edit')
def student_edit(request, pk):
    student = get_student_for_user(request.user, pk)
    if request.method == 'POST':
        form = StudentForm(request.POST, request.FILES, instance=student)
        if form.is_valid():
            form.save()
            messages.success(request, f"Élève {student} modifié.")
            return redirect('students:detail', pk=student.pk)
    else:
        form = StudentForm(instance=student)
    if request.GET.get('modal') == '1' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'students/student_form_modal.html', {
            'form': form, 'title': f'Modifier — {student}',
            'is_edit': True, 'student': student,
            'form_action': request.path,
        })
    return render(request, 'students/student_form.html', {
        'form': form, 'enr_form': None, 'title': f'Modifier — {student}',
        'is_edit': True, 'student': student, 'classrooms_fees': [],
    })


@login_required
def student_qr(request, pk):
    """Modal QR code élève (matricule)."""
    student = get_student_for_user(request.user, pk)
    ctx = {'student': student}
    if request.GET.get('modal') == '1' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'students/student_qr_modal.html', ctx)
    return render(request, 'students/student_qr_modal.html', ctx)


@login_required
def student_card(request, pk):
    """Carte scolaire seule — impression / téléchargement PDF (navigateur)."""
    student = get_student_for_user(request.user, pk)
    enrollment = student.current_enrollment()
    parents = student.parents.select_related('parent').all()
    parent = parents[0].parent if parents else None
    try:
        from core.models import SchoolSettings
        school = SchoolSettings.get_solo()
    except Exception:
        school = None
    year = get_selected_year(request)
    from datetime import date
    today = date.today()
    age = None
    if student.date_of_birth:
        age = today.year - student.date_of_birth.year - (
            (today.month, today.day) < (student.date_of_birth.month, student.date_of_birth.day)
        )
    from students.card_mali import _parents_pair
    father_name, mother_name = _parents_pair(student)
    return render(request, 'students/student_card.html', {
        'student': student,
        'enrollment': enrollment,
        'parent': parent,
        'father_name': father_name,
        'mother_name': mother_name,
        'school': school,
        'selected_year': year,
        'age': age,
        'today': today,
    })


@login_required
def student_card_pdf(request, pk):
    """Télécharger la carte scolaire en PDF — modèle Mali 85,6 × 54 mm."""
    from io import BytesIO
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
    from django.http import HttpResponse
    from students.card_mali import draw_card_pdf

    student = get_student_for_user(request.user, pk)
    enrollment = student.current_enrollment()
    try:
        from core.models import SchoolSettings
        school = SchoolSettings.get_solo()
    except Exception:
        school = None

    w, h = 85.6 * mm, 54 * mm
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(w, h))
    draw_card_pdf(c, student, enrollment, school, y0=0)
    c.showPage()
    c.save()
    buf.seek(0)

    filename = f"carte_{student.matricule}.pdf".replace(' ', '_')
    resp = HttpResponse(buf.read(), content_type='application/pdf')
    resp['Content-Disposition'] = f'attachment; filename="{filename}"'
    return resp



def student_card_image(request, pk):
    """Télécharger la carte scolaire (recto) en PNG — modèle Mali exact."""
    from django.http import HttpResponse
    from students.card_mali import render_card_png

    student = get_student_for_user(request.user, pk)
    enrollment = student.current_enrollment()
    try:
        from core.models import SchoolSettings
        school = SchoolSettings.get_solo()
    except Exception:
        school = None

    buf = render_card_png(student, enrollment, school)
    filename = f"carte_{student.matricule}.png".replace(' ', '_')
    disp = 'inline' if request.GET.get('preview') == '1' else 'attachment'
    resp = HttpResponse(buf.read(), content_type='image/png')
    resp['Content-Disposition'] = f'{disp}; filename="{filename}"'
    return resp


@login_required
def student_card_preview(request, pk):
    """Aperçu carte en modal (image modèle Mali)."""
    student = get_student_for_user(request.user, pk)
    return render(request, 'students/student_card_preview_modal.html', {
        'student': student,
        'preview_image_url': f'/eleves/{student.pk}/carte/image/?preview=1',
        'pdf_url': f'/eleves/{student.pk}/carte/pdf/',
        'img_url': f'/eleves/{student.pk}/carte/image/',
    })


@login_required
def cards_home(request):
    """Gestion des cartes scolaires : modèles + classes."""
    from academics.models import ClassRoom
    from students.card_designs import CARD_DESIGNS
    year = get_selected_year(request)
    try:
        from core.models import SchoolSettings
        school = SchoolSettings.get_solo()
    except Exception:
        school = None

    if request.method == 'POST' and request.POST.get('action') == 'set_template':
        key = request.POST.get('card_template', 'modern')
        if school and key in CARD_DESIGNS:
            school.card_template = key
            school.save(update_fields=['card_template'])
            from django.contrib import messages
            messages.success(request, f'Modèle de carte « {CARD_DESIGNS[key]["label"]} » enregistré.')
        return redirect('students:cards_home')

    classrooms = ClassRoom.objects.select_related('level', 'academic_year').order_by('level__order', 'name')
    if year:
        classrooms = classrooms.filter(academic_year=year)
    # counts
    from students.models import Enrollment
    rows = []
    for c in classrooms:
        n = Enrollment.objects.filter(classroom=c, is_active=True).count()
        rows.append({'classroom': c, 'count': n})
    current = getattr(school, 'card_template', 'modern') if school else 'modern'
    return render(request, 'students/cards_home.html', {
        'rows': rows,
        'designs': CARD_DESIGNS,
        'current_template': current,
        'school': school,
        'selected_year': year,
    })


@login_required
def cards_class(request, classroom_id):
    """Cartes d'une classe : aperçu + téléchargements individuels / lot."""
    from academics.models import ClassRoom
    from students.models import Enrollment
    from students.card_designs import CARD_DESIGNS, get_design
    classroom = get_object_or_404(ClassRoom, pk=classroom_id)
    enrollments = (
        Enrollment.objects.filter(classroom=classroom, is_active=True)
        .select_related('student')
        .order_by('student__last_name', 'student__first_name')
    )
    try:
        from core.models import SchoolSettings
        school = SchoolSettings.get_solo()
    except Exception:
        school = None
    current = getattr(school, 'card_template', 'modern') if school else 'modern'
    # override via GET
    template_key = request.GET.get('template') or current
    return render(request, 'students/cards_class.html', {
        'classroom': classroom,
        'enrollments': enrollments,
        'designs': CARD_DESIGNS,
        'current_template': template_key,
        'school': school,
    })


@login_required
def cards_class_pdf(request, classroom_id):
    """PDF groupé : une carte Mali (recto) par page pour la classe."""
    from io import BytesIO
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
    from django.http import HttpResponse
    from academics.models import ClassRoom
    from students.models import Enrollment
    from students.card_mali import draw_card_pdf

    classroom = get_object_or_404(ClassRoom, pk=classroom_id)
    enrollments = (
        Enrollment.objects.filter(classroom=classroom, is_active=True)
        .select_related('student')
        .order_by('student__last_name', 'student__first_name')
    )
    try:
        from core.models import SchoolSettings
        school = SchoolSettings.get_solo()
    except Exception:
        school = None

    w, h = 85.6 * mm, 54 * mm
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(w, h))
    for enr in enrollments:
        draw_card_pdf(c, enr.student, enr, school, y0=0)
        c.showPage()
    c.save()
    buf.seek(0)
    filename = f"cartes_{classroom.name}.pdf".replace(' ', '_')
    resp = HttpResponse(buf.read(), content_type='application/pdf')
    resp['Content-Disposition'] = f'attachment; filename="{filename}"'
    return resp


@login_required
def student_list_pdf(request):
    """Liste des élèves en PDF propre (sans interface)."""
    from core.year_context import get_selected_year
    from core.list_pdf import build_list_pdf
    from core.models import SchoolSettings
    
    year = get_selected_year(request)
    school = SchoolSettings.get_solo()
    q = (request.GET.get('q') or '').strip()
    classroom_id = request.GET.get('classroom') or ''
    status = request.GET.get('status') or ''

    qs = Student.objects.all().order_by('last_name', 'first_name')
    if status:
        qs = qs.filter(status=status)
    if q:
        qs = qs.filter(
            Q(last_name__icontains=q) | Q(first_name__icontains=q) | Q(matricule__icontains=q)
        )

    enrollments = {}
    enr_qs = Enrollment.objects.filter(is_active=True).select_related('classroom')
    if year:
        enr_qs = enr_qs.filter(academic_year=year)
    if classroom_id:
        enr_qs = enr_qs.filter(classroom_id=classroom_id)
        qs = qs.filter(id__in=enr_qs.values_list('student_id', flat=True))
    for e in enr_qs:
        enrollments[e.student_id] = e

    rows = []
    for s in qs:
        e = enrollments.get(s.pk)
        if classroom_id and not e:
            continue
        cls = e.classroom.name if e else '—'
        age = '—'
        if s.date_of_birth:
            from datetime import date
            today = date.today()
            age = str(today.year - s.date_of_birth.year - (
                (today.month, today.day) < (s.date_of_birth.month, s.date_of_birth.day)
            ))
        parent_name = '—'
        try:
            link = ParentStudent.objects.filter(student=s).select_related('parent').first()
            if link and link.parent:
                parent_name = f"{link.parent.last_name} {link.parent.first_name}"
        except Exception:
            pass
        rows.append([
            s.matricule or '—',
            f"{s.last_name} {s.first_name}",
            s.get_gender_display() if hasattr(s, 'get_gender_display') else (s.gender or '—'),
            cls,
            age,
            parent_name,
            s.get_status_display() if hasattr(s, 'get_status_display') else (s.status or '—'),
        ])

    school_name = getattr(school, 'name', None) or 'Établissement'
    year_name = year.name if year else ''
    return build_list_pdf(
        title=school_name,
        subtitle=f"Liste des élèves{' — ' + year_name if year_name else ''} · {len(rows)} élève(s)",
        headers=['Matricule', 'Nom et prénom', 'Sexe', 'Classe', 'Âge', 'Parent', 'Statut'],
        rows=rows,
        filename=f"liste_eleves_{year_name or 'all'}.pdf".replace(' ', '_'),
        landscape_mode=True,
    )


@role_required('directeur', 'secretaire')
def student_import(request):
    """Import d'élèves CLASSE PAR CLASSE : modèle Excel → aperçu → confirmation → rapport."""
    years = AcademicYear.objects.order_by('-is_current', '-start_date', '-id')
    default_year = get_selected_year(request)

    year_id = request.GET.get('year') or request.POST.get('academic_year') or ''
    selected_year = (
        AcademicYear.objects.filter(pk=year_id).first() if year_id else default_year
    ) or default_year

    classrooms = ClassRoom.objects.select_related('level', 'level__cycle').filter(
        academic_year=selected_year
    ).order_by('level__cycle__order', 'level__order', 'name')
    classrooms = filter_classrooms_for_user(request.user, classrooms)

    selected_classroom = None
    class_id = request.POST.get('classroom') or request.GET.get('classroom', '')
    if class_id:
        selected_classroom = classrooms.filter(pk=class_id).first()

    action = request.POST.get('action') or request.GET.get('action') or ''

    # ── Téléchargement du modèle Excel (CSV conservé pour compatibilité) ──
    if request.GET.get('sample') == '1':
        suffix = f"_{selected_classroom.name}" if selected_classroom else ''
        suffix = re.sub(r'[^A-Za-z0-9]+', '_', suffix).strip('_')
        if request.GET.get('format') == 'csv':
            response = HttpResponse(sample_csv(), content_type='text/csv; charset=utf-8')
            response['Content-Disposition'] = (
                f'attachment; filename="modele_import{suffix}.csv"'
            )
        else:
            response = HttpResponse(
                sample_xlsx(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            )
            response['Content-Disposition'] = (
                f'attachment; filename="modele_import{suffix}.xlsx"'
            )
        return response

    # ── Rapport d'erreurs (Excel) ──
    if request.GET.get('report_errors') == '1':
        data = request.session.get('import_error_report')
        if not data:
            messages.error(request, "Aucun rapport d'erreurs disponible.")
            return redirect('students:import')
        response = HttpResponse(
            error_report_xlsx(data),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        response['Content-Disposition'] = 'attachment; filename="rapport_erreurs_import.xlsx"'
        return response

    preview = None
    report = None
    error = ''
    if request.method == 'POST':
        if action == 'verify':
            # Étape 2 : analyse SANS écriture en base.
            if not selected_classroom:
                error = "Veuillez choisir la classe dans laquelle importer les élèves."
            else:
                uploaded = request.FILES.get('file')
                if not uploaded:
                    error = "Veuillez choisir un fichier CSV ou Excel (.csv, .xlsx)."
                else:
                    try:
                        rows = parse_file(uploaded, uploaded.name)
                    except Exception as exc:
                        error = f"Lecture du fichier impossible : {exc}"
                    else:
                        if not rows:
                            error = "Le fichier ne contient aucune ligne d'élève."
                        else:
                            preview = validate_rows(rows, selected_classroom)
                            request.session['import_preview'] = {
                                'classroom_id': selected_classroom.pk,
                                'create_parents': request.POST.get('create_parents') == 'on',
                                'create_invoices': request.POST.get('create_invoices') == 'on',
                                'rows': preview['rows'],
                            }
        elif action == 'confirm':
            # Étape 3 : import définitif des lignes validées.
            stored = request.session.get('import_preview')
            if not stored:
                error = "L'aperçu a expiré. Veuillez déposer à nouveau le fichier."
            else:
                target = ClassRoom.objects.filter(pk=stored.get('classroom_id')).first()
                if not target:
                    error = "La classe sélectionnée n'existe plus."
                else:
                    report = import_from_preview(
                        stored['rows'], target,
                        create_parents=stored.get('create_parents', True),
                        create_invoices=stored.get('create_invoices', True),
                    )
                    request.session['import_error_report'] = {
                        'classroom': target.name,
                        'year': target.academic_year.name,
                        'created': report['created'],
                        'exists': report['exists'],
                        'errors': report['errors'],
                    }
                    request.session.pop('import_preview', None)
                    messages.success(
                        request,
                        f"Import dans {target.name} terminé : "
                        f"{report['created']} élève(s) créé(s), "
                        f"{report['exists']} déjà existant(s), "
                        f"{len(report['errors'])} erreur(s).",
                    )
        # action vide = simple changement d'année : on réaffiche le formulaire.

    existing_count = 0
    if selected_classroom:
        existing_count = Enrollment.objects.filter(
            classroom=selected_classroom, is_active=True
        ).count()

    return render(request, 'students/student_import.html', {
        'preview': preview,
        'report': report,
        'error': error,
        'years': years,
        'selected_year': selected_year,
        'classrooms': classrooms,
        'selected_classroom': selected_classroom,
        'existing_count': existing_count,
        'stored_preview': request.session.get('import_preview'),
    })
