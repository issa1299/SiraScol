import json
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required

from .permissions import role_required
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.contrib import messages
from django.db.models import Sum, Count, Q
from django.urls import reverse

from students.models import Student, Enrollment, Parent
from teachers.models import Teacher
from academics.models import ClassRoom, AcademicYear
from attendance.models import Absence
from .models import SchoolSettings
from .forms import SchoolSettingsForm
from .year_context import get_selected_year, set_selected_year


@role_required('admin', 'directeur')
def set_academic_year(request):
    """POST ou GET ?year=id — change l'année de travail pour toute l'app."""
    year_id = request.POST.get('year') or request.GET.get('year')
    if year_id:
        year = get_object_or_404(AcademicYear, pk=year_id)
        set_selected_year(request, year.pk)
        # Si aucune classe sur cette année → reprendre la structure de l'année précédente
        from academics.models import ClassRoom
        from academics.views import clone_classrooms_to_year
        if not ClassRoom.objects.filter(academic_year=year).exists():
            prev = (
                AcademicYear.objects.filter(start_date__lt=year.start_date)
                .order_by('-start_date').first()
            )
            if prev:
                n = clone_classrooms_to_year(prev, year)
                if n:
                    messages.success(
                        request,
                        f'Année {year.name} : {n} classe(s) reprises de {prev.name} (sans élèves).'
                    )
                else:
                    messages.info(request, f'Année de travail : {year.name}')
            else:
                messages.info(request, f'Année de travail : {year.name}')
        else:
            messages.info(request, f'Année de travail : {year.name}')
    next_url = request.POST.get('next') or request.GET.get('next') or request.META.get('HTTP_REFERER') or reverse('core:dashboard')
    return redirect(next_url)


@login_required
def dashboard(request):
    """Tableau de bord adapté au rôle."""
    from core.permissions import (
        get_role, get_linked_teacher, get_linked_parent, get_linked_student,
        get_teacher_classrooms, get_parent_students,
    )
    role = get_role(request.user)
    year = get_selected_year(request)
    school = SchoolSettings.get_solo()
    today = date.today()

    if role == 'enseignant':
        return redirect('prof:dashboard')
    if role == 'parent':
        return redirect('parent:dashboard')
    if role == 'eleve':
        # L'élève dispose de son propre espace dédié (interface et navigation propres).
        return redirect('eleve:dashboard')
    if role == 'secretaire':
        return redirect('secretariat:dashboard')
    if role == 'comptable':
        return redirect('comptabilite:dashboard')
    if role == 'surveillant':
        return redirect('surveillant:dashboard')
    # directeur, admin, superuser → tableau de bord direction
    return _dashboard_staff(request, year, school, today)


def _dashboard_staff(request, year, school, today):
    first_day_month = today.replace(day=1)
    if year:
        enrollments = Enrollment.objects.filter(academic_year=year, is_active=True)
        n_students = enrollments.count()
        n_classrooms = ClassRoom.objects.filter(academic_year=year).count()
        by_cycle = (
            enrollments.values('classroom__level__cycle__name')
            .annotate(n=Count('id'))
            .order_by('classroom__level__cycle__order')
        )
    else:
        n_students = Student.objects.filter(status='actif').count()
        n_classrooms = ClassRoom.objects.count()
        by_cycle = []

    n_teachers = Teacher.objects.filter(is_active=True).count()
    n_parents = Parent.objects.count()
    try:
        abs_qs = Absence.objects.all()
        if year:
            ids = Enrollment.objects.filter(academic_year=year, is_active=True).values_list('student_id', flat=True)
            abs_qs = abs_qs.filter(student_id__in=ids)
        absences_month = abs_qs.filter(date__gte=first_day_month).count()
        recent_absences = abs_qs.select_related('student').order_by('-date')[:6]
    except Exception:
        absences_month = 0
        recent_absences = []

    unpaid = Decimal('0')
    paid_month = Decimal('0')
    paid_today = Decimal('0')
    expense_today = Decimal('0')
    expense_month = Decimal('0')
    n_unpaid_invoices = 0
    recent_payments = []
    fee_reminders = []
    recent_expenses = []
    recent_enrollments = []
    try:
        from finance.models import Invoice, Payment, Expense
        inv_qs = Invoice.objects.all()
        if year:
            inv_qs = inv_qs.filter(academic_year=year)
        unpaid_qs = inv_qs.exclude(status='paye').exclude(status='annule')
        n_unpaid_invoices = unpaid_qs.count()
        for inv in unpaid_qs.select_related('student', 'fee_type')[:20]:
            try:
                bal = inv.balance
            except Exception:
                bal = inv.amount
            unpaid += bal
            if bal > 0:
                fee_reminders.append({'invoice': inv, 'balance': bal})
        pay_qs = Payment.objects.select_related('invoice__student', 'invoice__fee_type')
        if year:
            pay_qs = pay_qs.filter(invoice__academic_year=year)
        paid_month = pay_qs.filter(payment_date__gte=first_day_month).aggregate(s=Sum('amount'))['s'] or Decimal('0')
        paid_today = pay_qs.filter(payment_date=today).aggregate(s=Sum('amount'))['s'] or Decimal('0')
        recent_payments = list(pay_qs.order_by('-payment_date', '-id')[:6])
        exp_qs = Expense.objects.all()
        if year:
            exp_qs = exp_qs.filter(academic_year=year)
        expense_today = exp_qs.filter(date=today).aggregate(s=Sum('amount'))['s'] or Decimal('0')
        expense_month = exp_qs.filter(date__gte=first_day_month).aggregate(s=Sum('amount'))['s'] or Decimal('0')
        recent_expenses = list(exp_qs.order_by('-date', '-id')[:6])
    except Exception:
        pass

    try:
        enr_qs = Enrollment.objects.filter(is_active=True).select_related('student', 'classroom')
        if year:
            enr_qs = enr_qs.filter(academic_year=year)
        recent_enrollments = list(enr_qs.order_by('-id')[:5])
    except Exception:
        recent_enrollments = []

    boys_present = girls_present = 0
    try:
        # Présents = inscrits actifs moins absents du jour (approx.)
        if year:
            enr = Enrollment.objects.filter(academic_year=year, is_active=True).select_related('student')
            absent_ids = set(
                Absence.objects.filter(date=today).values_list('student_id', flat=True)
            )
            for e in enr:
                if e.student_id in absent_ids:
                    continue
                g = getattr(e.student, 'gender', '') or ''
                if g == 'M':
                    boys_present += 1
                elif g == 'F':
                    girls_present += 1
    except Exception:
        pass


    # Genre inscrits (pour graphiques)
    n_boys = n_girls = 0
    try:
        if year:
            enr_g = Enrollment.objects.filter(academic_year=year, is_active=True).select_related('student')
        else:
            enr_g = Enrollment.objects.filter(is_active=True).select_related('student')
        for e in enr_g:
            g = getattr(e.student, 'gender', '') or ''
            if g == 'M':
                n_boys += 1
            elif g == 'F':
                n_girls += 1
    except Exception:
        n_boys = n_girls = 0

    cycle_labels = [row.get('classroom__level__cycle__name') or '—' for row in by_cycle]
    cycle_values = [int(row.get('n') or 0) for row in by_cycle]

    caisse = paid_month - expense_month

    n_pending_promo = n_promoted = n_repeated = 0
    if year:
        enr = Enrollment.objects.filter(academic_year=year)
        n_pending_promo = enr.filter(end_status='en_cours', is_active=True).count()
        n_promoted = enr.filter(end_status='promoted').count()
        n_repeated = enr.filter(end_status='repeated').count()

    try:
        from communication.models import Announcement
        announcements = Announcement.objects.order_by('-created_at')[:4]
    except Exception:
        announcements = []

    return render(request, 'core/dashboard.html', {
        'stats': {
            'students': n_students, 'teachers': n_teachers, 'classrooms': n_classrooms,
            'parents': n_parents, 'absences_month': absences_month, 'unpaid': unpaid,
            'paid_month': paid_month, 'paid_today': paid_today,
            'expense_today': expense_today, 'expense_month': expense_month,
            'caisse': caisse, 'solde_jour': paid_today - expense_today,
            'n_unpaid_invoices': n_unpaid_invoices,
            'pending_promo': n_pending_promo, 'promoted': n_promoted, 'repeated': n_repeated,
            'boys_present': boys_present, 'girls_present': girls_present,
            'boys': n_boys, 'girls': n_girls,
        },
        'current_year': year, 'selected_year': year, 'recent_absences': recent_absences,
        'recent_payments': recent_payments, 'recent_expenses': recent_expenses,
        'fee_reminders': fee_reminders[:8], 'recent_enrollments': recent_enrollments,
        'school': school, 'by_cycle': by_cycle, 'announcements': announcements, 'today': today,
        'dashboard_role': 'staff',
        'user_display': request.user.get_full_name() or request.user.username,
        'chart_cycles_json': {'labels': cycle_labels, 'values': cycle_values},
        'chart_finance_json': {
            'labels': ['Encaissé', 'Dépenses', 'Impayés'],
            'values': [float(paid_month or 0), float(expense_month or 0), float(unpaid or 0)],
        },
        'chart_gender_json': {'labels': ['Garçons', 'Filles'], 'values': [n_boys, n_girls]},
        'chart_promo_json': {
            'labels': ['En cours', 'Admis', 'Redoublants'],
            'values': [n_pending_promo, n_promoted, n_repeated],
        },
    })



def _dashboard_comptable(request, year, school, today):
    """Espace comptable — caisse, impayés, salaires."""
    first_day = today.replace(day=1)
    paid_month = paid_today = expense_month = expense_today = unpaid = Decimal('0')
    n_unpaid = 0
    recent_payments = []
    recent_expenses = []
    try:
        from finance.models import Payment, Invoice, Expense
        inv = Invoice.objects.all()
        if year:
            inv = inv.filter(academic_year=year)
        paid_qs = Payment.objects.filter(invoice__in=inv)
        paid_month = paid_qs.filter(date__gte=first_day).aggregate(s=Sum('amount'))['s'] or Decimal('0')
        paid_today = paid_qs.filter(date=today).aggregate(s=Sum('amount'))['s'] or Decimal('0')
        due = inv.aggregate(s=Sum('amount'))['s'] or Decimal('0')
        unpaid = max(Decimal('0'), due - (paid_qs.aggregate(s=Sum('amount'))['s'] or Decimal('0')))
        n_unpaid = inv.exclude(status__in=['paye', 'annule']).count()
        exp = Expense.objects.all()
        if year:
            exp = exp.filter(Q(academic_year=year) | Q(date__gte=year.start_date, date__lte=year.end_date))
        expense_month = exp.filter(date__gte=first_day).aggregate(s=Sum('amount'))['s'] or Decimal('0')
        expense_today = exp.filter(date=today).aggregate(s=Sum('amount'))['s'] or Decimal('0')
        recent_payments = list(paid_qs.select_related('invoice', 'invoice__student').order_by('-date')[:8])
        recent_expenses = list(exp.order_by('-date')[:6])
    except Exception:
        pass
    n_staff = Teacher.objects.filter(status='actif').count()
    salaries_pending = 0
    try:
        from teachers.models import StaffSalary
        salaries_pending = StaffSalary.objects.filter(status='en_attente').count()
    except Exception:
        pass
    return render(request, 'core/dashboard_comptable.html', {
        'school': school, 'selected_year': year, 'today': today,
        'paid_month': paid_month, 'paid_today': paid_today,
        'expense_month': expense_month, 'expense_today': expense_today,
        'unpaid': unpaid, 'n_unpaid': n_unpaid,
        'caisse': paid_month - expense_month,
        'n_staff': n_staff, 'salaries_pending': salaries_pending,
        'recent_payments': recent_payments, 'recent_expenses': recent_expenses,
        'user_display': request.user.get_full_name() or request.user.username,
    })


def _dashboard_secretaire(request, year, school, today):
    """Espace secrétaire — inscriptions, élèves, parents, appels."""
    first_day = today.replace(day=1)
    if year:
        enr = Enrollment.objects.filter(academic_year=year, is_active=True)
        n_students = enr.count()
        n_classrooms = ClassRoom.objects.filter(academic_year=year).count()
        recent_enr = list(
            enr.select_related('student', 'classroom').order_by('-id')[:8]
        )
    else:
        n_students = Student.objects.filter(status='actif').count()
        n_classrooms = ClassRoom.objects.count()
        recent_enr = []
    n_parents = Parent.objects.count()
    n_teachers = Teacher.objects.filter(is_active=True).count()
    absences_today = 0
    try:
        absences_today = Absence.objects.filter(date=today).count()
    except Exception:
        pass
    n_docs = 0
    try:
        from communication.models import SchoolDocument
        n_docs = SchoolDocument.objects.filter(is_published=True).count()
    except Exception:
        pass
    try:
        from communication.models import Announcement
        announcements = Announcement.objects.order_by('-published_at')[:5]
    except Exception:
        announcements = []
    return render(request, 'core/dashboard_secretaire.html', {
        'school': school, 'selected_year': year, 'today': today,
        'n_students': n_students, 'n_classrooms': n_classrooms,
        'n_parents': n_parents, 'n_teachers': n_teachers,
        'absences_today': absences_today, 'n_docs': n_docs,
        'recent_enrollments': recent_enr, 'announcements': announcements,
        'user_display': request.user.get_full_name() or request.user.username,
    })


def _dashboard_teacher(request, year, school, today):
    from core.permissions import get_linked_teacher, get_teacher_classrooms
    from academics.models import SubjectAssignment
    teacher = get_linked_teacher(request.user)
    classrooms = get_teacher_classrooms(request.user)
    if year:
        classrooms = classrooms.filter(academic_year=year)
    assignments = SubjectAssignment.objects.filter(teacher=teacher).select_related(
        'subject', 'classroom'
    ) if teacher else []
    if year and teacher:
        assignments = assignments.filter(classroom__academic_year=year)
    n_students = Enrollment.objects.filter(
        classroom__in=classrooms, is_active=True
    ).count() if classrooms.exists() else 0
    try:
        from communication.models import Announcement
        announcements = Announcement.objects.order_by('-created_at')[:5]
    except Exception:
        announcements = []
    return render(request, 'core/dashboard_teacher.html', {
        'teacher': teacher, 'classrooms': classrooms, 'assignments': assignments,
        'n_students': n_students, 'school': school, 'selected_year': year,
        'announcements': announcements, 'today': today,
    })


def _dashboard_parent(request, year, school, today):
    from core.permissions import get_linked_parent, get_parent_students
    parent = get_linked_parent(request.user)
    children = get_parent_students(request.user)
    child_rows = []
    for st in children:
        enr = None
        if year:
            enr = Enrollment.objects.filter(
                student=st, academic_year=year, is_active=True
            ).select_related('classroom', 'classroom__level').first()
        balance = Decimal('0')
        try:
            from finance.models import Invoice
            invs = Invoice.objects.filter(student=st).exclude(status='annule')
            if year:
                invs = invs.filter(academic_year=year)
            for inv in invs:
                try:
                    balance += inv.balance
                except Exception:
                    pass
        except Exception:
            pass
        child_rows.append({'student': st, 'enrollment': enr, 'balance': balance})
    try:
        from communication.models import Announcement
        announcements = Announcement.objects.order_by('-created_at')[:5]
    except Exception:
        announcements = []
    return render(request, 'core/dashboard_parent.html', {
        'parent': parent, 'child_rows': child_rows, 'school': school,
        'selected_year': year, 'announcements': announcements, 'today': today,
    })


def _dashboard_student(request, year, school, today):
    from core.permissions import get_linked_student
    student = get_linked_student(request.user)
    enr = None
    if student and year:
        enr = Enrollment.objects.filter(
            student=student, academic_year=year, is_active=True
        ).select_related('classroom', 'classroom__level').first()
    try:
        from communication.models import Announcement
        announcements = Announcement.objects.order_by('-created_at')[:5]
    except Exception:
        announcements = []
    return render(request, 'core/dashboard_student.html', {
        'student': student, 'enrollment': enr, 'school': school,
        'selected_year': year, 'announcements': announcements, 'today': today,
    })


@role_required('admin', 'directeur')
def school_settings(request):
    """Paramètres globaux style EduNet — une seule page."""
    from django.contrib.auth import get_user_model
    from academics.models import AcademicYear, ClassRoom
    from students.models import Student
    from teachers.models import Teacher
    from .models import SchoolPhoto
    from .forms import SchoolSettingsForm, SchoolPhotoForm

    settings_obj = SchoolSettings.get_solo()
    is_modal = request.GET.get('modal') == '1' or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    action = request.GET.get('action') or request.POST.get('action', '')

    # Upload photo école
    if request.method == 'POST' and action == 'photo':
        pform = SchoolPhotoForm(request.POST, request.FILES)
        if pform.is_valid():
            photo = pform.save()
            if not SchoolPhoto.objects.filter(is_primary=True).exclude(pk=photo.pk).exists():
                photo.is_primary = True
                photo.save(update_fields=['is_primary'])
            messages.success(request, 'Photo ajoutée avec succès !')
        else:
            messages.error(request, 'Erreur upload photo.')
        return redirect('core:settings')

    if request.method == 'POST' and action == 'delete_photo':
        pk = request.POST.get('photo_id')
        SchoolPhoto.objects.filter(pk=pk).delete()
        messages.success(request, 'Photo supprimée.')
        return redirect('core:settings')

    if request.method == 'POST' and action == 'toggle_maintenance':
        settings_obj.maintenance_mode = not settings_obj.maintenance_mode
        settings_obj.save(update_fields=['maintenance_mode'])
        if settings_obj.maintenance_mode:
            messages.warning(request, 'Mode maintenance ACTIVÉ — parents / enseignants / élèves sont bloqués.')
        else:
            messages.success(request, 'Mode maintenance désactivé. Application ouverte.')
        return redirect('core:settings')

    # Upload logo / cachet uniquement (ne touche pas aux autres champs)
    if request.method == 'POST' and action == 'logo_stamp':
        changed = []
        if request.FILES.get('logo'):
            settings_obj.logo = request.FILES['logo']
            changed.append('logo')
        if request.FILES.get('stamp'):
            settings_obj.stamp = request.FILES['stamp']
            changed.append('cachet')
        # Clear requested
        if request.POST.get('clear_logo') == '1' and settings_obj.logo:
            settings_obj.logo.delete(save=False)
            settings_obj.logo = None
            changed.append('logo supprimé')
        if request.POST.get('clear_stamp') == '1' and settings_obj.stamp:
            settings_obj.stamp.delete(save=False)
            settings_obj.stamp = None
            changed.append('cachet supprimé')
        if changed:
            settings_obj.save()
            messages.success(request, 'Enregistré : ' + ', '.join(changed) + '.')
        else:
            messages.warning(request, 'Aucun fichier sélectionné. Choisissez un logo ou un cachet puis cliquez Enregistrer.')
        return redirect('/parametres/?tab=logo')

    if request.method == 'POST':
        form = SchoolSettingsForm(request.POST, request.FILES, instance=settings_obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Paramètres enregistrés.")
            if is_modal:
                return render(request, 'core/settings_saved.html', {'school': settings_obj})
            tab = request.POST.get('tab') or request.GET.get('tab') or 'infos'
            return redirect(f'/parametres/?tab={tab}')
        else:
            messages.error(request, 'Formulaire invalide. Vérifiez les champs.')
    else:
        form = SchoolSettingsForm(instance=settings_obj)

    User = get_user_model()
    year = AcademicYear.objects.filter(is_current=True).first()
    stats = {
        'students': Student.objects.filter(is_active=True).count() if hasattr(Student, 'is_active') else Student.objects.count(),
        'classes': ClassRoom.objects.filter(academic_year=year).count() if year else ClassRoom.objects.count(),
        'teachers': Teacher.objects.filter(status='actif').count() if hasattr(Teacher, 'status') else Teacher.objects.count(),
        'users': User.objects.filter(is_active=True).count(),
    }
    years = AcademicYear.objects.all().order_by('-start_date')
    photos = SchoolPhoto.objects.all()[:20]
    photo_form = SchoolPhotoForm()

    ctx = {
        'form': form,
        'school': settings_obj,
        'stats': stats,
        'years': years,
        'photos': photos,
        'photo_form': photo_form,
        'tab': request.GET.get('tab', 'infos'),
    }
    if is_modal and action == 'edit':
        return render(request, 'core/settings_form_modal.html', ctx)
    if is_modal and action == 'photo_form':
        return render(request, 'core/settings_photo_modal.html', ctx)
    return render(request, 'core/settings.html', ctx)





def _collect_reports_data(request):
    """Données partagées page rapports + PDF."""
    year = get_selected_year(request)
    today = date.today()
    school = SchoolSettings.get_solo()

    enrollments = Enrollment.objects.filter(is_active=True).select_related(
        'classroom', 'classroom__level', 'classroom__level__cycle', 'student'
    )
    if year:
        enrollments = enrollments.filter(academic_year=year)
    n_eleves = enrollments.values('student_id').distinct().count()
    n_garcons = enrollments.filter(student__gender='M').values('student_id').distinct().count()
    n_filles = enrollments.filter(student__gender='F').values('student_id').distinct().count()
    n_classes = ClassRoom.objects.filter(academic_year=year).count() if year else ClassRoom.objects.count()
    n_parents = Parent.objects.count()

    by_cycle = []
    from academics.models import Cycle
    for cy in Cycle.objects.all().order_by('order'):
        cnt = enrollments.filter(classroom__level__cycle=cy).values('student_id').distinct().count()
        by_cycle.append({'name': cy.name, 'code': cy.code, 'n': cnt})

    by_class = []
    cr_qs = ClassRoom.objects.select_related('level', 'level__cycle').order_by(
        'level__cycle__order', 'level__order', 'name'
    )
    if year:
        cr_qs = cr_qs.filter(academic_year=year)
    for cr in cr_qs:
        cnt = enrollments.filter(classroom=cr).count()
        by_class.append({
            'name': cr.name,
            'level': cr.level.name if cr.level_id else '—',
            'cycle': cr.level.cycle.name if cr.level_id and cr.level.cycle_id else '—',
            'n': cnt,
        })

    staff_actif = Teacher.objects.filter(status='actif')
    personnel = {
        'total': staff_actif.count(),
        'enseignants': staff_actif.filter(category='enseignant').count(),
        'admin': staff_actif.filter(category='admin').count(),
        'service': staff_actif.filter(category='service').count(),
        'hommes': staff_actif.filter(gender='M').count(),
        'femmes': staff_actif.filter(gender='F').count(),
    }

    finance = {
        'encaisse': Decimal('0'),
        'impaye': Decimal('0'),
        'depenses': Decimal('0'),
        'n_paiements': 0,
    }
    try:
        from finance.models import Payment, Invoice, Expense
        inv_qs = Invoice.objects.exclude(status='annule')
        if year:
            inv_qs = inv_qs.filter(academic_year=year)
        pay_qs = Payment.objects.filter(invoice__in=inv_qs, is_cancelled=False)
        exp_qs = Expense.objects.all()
        if year:
            exp_qs = exp_qs.filter(Q(academic_year=year) | Q(date__gte=year.start_date, date__lte=year.end_date))
        finance['encaisse'] = pay_qs.aggregate(s=Sum('amount'))['s'] or Decimal('0')
        finance['n_paiements'] = pay_qs.count()
        due = inv_qs.aggregate(s=Sum('amount'))['s'] or Decimal('0')
        finance['impaye'] = max(Decimal('0'), due - finance['encaisse'])
        finance['depenses'] = exp_qs.aggregate(s=Sum('amount'))['s'] or Decimal('0')
    except Exception:
        pass

    attendance = {'pointages': 0, 'absences': 0, 'retards': 0}
    try:
        from attendance.models import AttendancePunch, Absence as AbsModel
        d0 = today - timedelta(days=30)
        attendance['pointages'] = AttendancePunch.objects.filter(date__gte=d0).count()
        attendance['absences'] = AbsModel.objects.filter(date__gte=d0, type='absence').count()
        attendance['retards'] = AbsModel.objects.filter(date__gte=d0, type='retard').count()
    except Exception:
        pass

    grades_info = {'n_notes': 0, 'n_evaluations': 0}
    try:
        from grades.models import Grade, Assessment
        gqs = Grade.objects.all()
        aqs = Assessment.objects.all()
        if year and hasattr(Assessment, 'period'):
            aqs = aqs.filter(period__academic_year=year)
            gqs = gqs.filter(assessment__period__academic_year=year)
        grades_info['n_notes'] = gqs.count()
        grades_info['n_evaluations'] = aqs.count()
    except Exception:
        pass

    return {
        'year': year,
        'school': school,
        'n_eleves': n_eleves,
        'n_garcons': n_garcons,
        'n_filles': n_filles,
        'n_classes': n_classes,
        'n_parents': n_parents,
        'by_cycle': by_cycle,
        'by_class': by_class,
        'personnel': personnel,
        'finance': finance,
        'attendance': attendance,
        'grades_info': grades_info,
        'today': today,
        'chart_cycles_json': {
            'labels': [c['name'] for c in by_cycle],
            'values': [c['n'] for c in by_cycle],
        },
        'chart_class_json': {
            'labels': [c['name'] for c in by_class[:15]],
            'values': [c['n'] for c in by_class[:15]],
        },
        'chart_finance_json': {
            'labels': ['Encaissé', 'Impayé', 'Dépenses'],
            'values': [float(finance['encaisse'] or 0), float(finance['impaye'] or 0), float(finance['depenses'] or 0)],
        },
        'chart_personnel_json': {
            'labels': ['Enseignants', 'Admin', 'Service'],
            'values': [personnel['enseignants'], personnel['admin'], personnel['service']],
        },
        'chart_gender_json': {
            'labels': ['Garçons', 'Filles'],
            'values': [n_garcons, n_filles],
        },
    }



@login_required
def reports_stats(request):
    """Rapports & statistiques globales de l'école (année de travail)."""
    from core.permissions import can
    if not can(request.user, 'nav.reports') and not request.user.is_superuser:
        messages.error(request, 'Accès refusé.')
        return redirect('core:dashboard')
    ctx = _collect_reports_data(request)
    return render(request, 'core/reports_stats.html', ctx)


@login_required
def reports_stats_pdf(request):
    """Export PDF du rapport global."""
    from core.permissions import can
    from io import BytesIO
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

    if not can(request.user, 'nav.reports') and not request.user.is_superuser:
        messages.error(request, 'Accès refusé.')
        return redirect('core:dashboard')

    data = _collect_reports_data(request)
    school = data['school']
    year = data['year']
    today = data['today']
    finance = data['finance']
    personnel = data['personnel']
    attendance = data['attendance']
    grades_info = data['grades_info']

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=14 * mm, rightMargin=14 * mm,
        topMargin=12 * mm, bottomMargin=12 * mm,
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        'T', parent=styles['Heading1'], fontSize=16, alignment=TA_CENTER,
        textColor=colors.HexColor('#1e40af'), spaceAfter=4,
    )
    sub = ParagraphStyle(
        'S', parent=styles['Normal'], fontSize=9, alignment=TA_CENTER,
        textColor=colors.HexColor('#64748b'), spaceAfter=8,
    )
    h2 = ParagraphStyle(
        'H2', parent=styles['Heading2'], fontSize=11, textColor=colors.HexColor('#0f172a'),
        spaceBefore=10, spaceAfter=4,
    )
    body = ParagraphStyle('B', parent=styles['Normal'], fontSize=9, leading=12)
    small = ParagraphStyle('SM', parent=styles['Normal'], fontSize=8, textColor=colors.HexColor('#64748b'))

    story = []
    school_name = getattr(school, 'name', None) or 'Établissement'
    story.append(Paragraph(str(school_name), title))
    story.append(Paragraph('Rapport &amp; statistiques — SiraScol', sub))
    year_name = year.name if year else '—'
    story.append(Paragraph(
        f'Année scolaire : <b>{year_name}</b> · Généré le {today.strftime("%d/%m/%Y")}',
        sub,
    ))
    story.append(HRFlowable(width='100%', thickness=1, color=colors.HexColor('#1e40af'), spaceAfter=8))

    # KPIs
    story.append(Paragraph('Indicateurs clés', h2))
    kpi = [
        ['Élèves', 'Garçons', 'Filles', 'Classes', 'Parents', 'Personnel'],
        [
            str(data['n_eleves']), str(data['n_garcons']), str(data['n_filles']),
            str(data['n_classes']), str(data['n_parents']), str(personnel['total']),
        ],
    ]
    t_kpi = Table(kpi, colWidths=[28*mm]*6)
    t_kpi.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e40af')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#eff6ff')),
        ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 1), (-1, 1), 11),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#cbd5e1')),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t_kpi)

    # Cycles
    story.append(Paragraph('Effectifs par cycle', h2))
    rows = [['Cycle', 'Élèves']]
    for c in data['by_cycle']:
        rows.append([c['name'], str(c['n'])])
    if len(rows) == 1:
        rows.append(['—', '0'])
    tc = Table(rows, colWidths=[120*mm, 40*mm])
    tc.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f1f5f9')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#e2e8f0')),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(tc)

    # Classes
    story.append(Paragraph('Effectifs par classe', h2))
    rows = [['Classe', 'Niveau', 'Cycle', 'Élèves']]
    for c in data['by_class']:
        rows.append([c['name'], c['level'], c['cycle'], str(c['n'])])
    if len(rows) == 1:
        rows.append(['—', '—', '—', '0'])
    tcl = Table(rows, colWidths=[55*mm, 40*mm, 40*mm, 25*mm])
    tcl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f1f5f9')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#e2e8f0')),
        ('ALIGN', (3, 0), (3, -1), 'RIGHT'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
    ]))
    story.append(tcl)

    # Personnel
    story.append(Paragraph('Personnel actif', h2))
    rows = [
        ['Total', 'Enseignants', 'Administration', 'Service', 'Hommes', 'Femmes'],
        [
            str(personnel['total']), str(personnel['enseignants']), str(personnel['admin']),
            str(personnel['service']), str(personnel['hommes']), str(personnel['femmes']),
        ],
    ]
    tp = Table(rows, colWidths=[28*mm]*6)
    tp.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f1f5f9')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(tp)

    # Finance
    story.append(Paragraph('Finance (année)', h2))
    rows = [
        ['Encaissé', 'Impayé', 'Dépenses', 'Nb paiements'],
        [
            f"{finance['encaisse']:,.0f} FCFA".replace(',', ' '),
            f"{finance['impaye']:,.0f} FCFA".replace(',', ' '),
            f"{finance['depenses']:,.0f} FCFA".replace(',', ' '),
            str(finance['n_paiements']),
        ],
    ]
    tf = Table(rows, colWidths=[42*mm]*4)
    tf.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#ecfdf5')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#a7f3d0')),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(tf)

    # Présences & notes
    story.append(Paragraph('Présences (30 derniers jours) & notes', h2))
    rows = [
        ['Pointages', 'Absences', 'Retards', 'Évaluations', 'Notes saisies'],
        [
            str(attendance['pointages']), str(attendance['absences']), str(attendance['retards']),
            str(grades_info['n_evaluations']), str(grades_info['n_notes']),
        ],
    ]
    ta = Table(rows, colWidths=[34*mm]*5)
    ta.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f1f5f9')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(ta)

    doc.build(story)
    pdf = buf.getvalue()
    buf.close()
    filename = f"rapport_sirascol_{year_name.replace(' ', '_') if year else 'global'}_{today.strftime('%Y%m%d')}.pdf"
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def page_not_found(request, exception=None):
    from django.shortcuts import render
    return render(request, '404.html', status=404)


def server_error(request):
    from django.shortcuts import render
    return render(request, '500.html', status=500)
