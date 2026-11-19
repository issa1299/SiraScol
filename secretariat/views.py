# -*- coding: utf-8 -*-
"""Espace Secrétaire — gestion administrative (élèves, inscriptions, classes, documents)."""

from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.models import User
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from academics.models import AcademicYear, ClassRoom
from communication.models import Announcement, Message
from core.messaging import allowed_recipients
from core.models import Notification
from core.permissions import get_linked_teacher, role_required
from core.year_context import get_selected_year
from students.models import Enrollment, Parent, ParentStudent, Student
from teachers.models import Teacher

from .pdf import document_pdf


def _year():
    return get_selected_year(None) or AcademicYear.objects.filter(is_current=True).first() or \
        AcademicYear.objects.order_by('-start_date', '-id').first()


def _first_user_with_role(role):
    from django.contrib.auth.models import User
    return User.objects.filter(profile__role=role, is_active=True).first()


@role_required('secretaire')
def dashboard(request):
    year = _year()
    total_students = Student.objects.count()
    new_students = Student.objects.filter(
        created_at__date__gte=timezone.now().date() - timedelta(days=30)
    ).count()
    teachers = Teacher.objects.filter(is_active=True).count()
    classes = ClassRoom.objects.filter(academic_year=year).count() if year else ClassRoom.objects.count()
    pending = Student.objects.filter(
        enrollments__academic_year=year,
        enrollments__is_active=True,
        invoices__isnull=True,
    ).distinct().count() if year else 0

    activities = []
    for s in Student.objects.order_by('-created_at')[:5]:
        activities.append({'date': s.created_at, 'label': f'Nouvel élève : {s.full_name}', 'icon': 'user-plus'})
    for e in Enrollment.objects.select_related('student', 'classroom').order_by('-created_at')[:5]:
        activities.append({'date': e.created_at, 'label': f'Inscription : {e.student.full_name} → {e.classroom.name}', 'icon': 'clipboard'})
    activities.sort(key=lambda x: x['date'], reverse=True)

    unread = Notification.objects.filter(user=request.user, is_read=False).count()
    unread_messages = Message.objects.filter(recipient=request.user, is_read=False).count()
    return render(request, 'secretariat/dashboard.html', {
        'total_students': total_students, 'new_students': new_students,
        'teachers': teachers, 'classes': classes, 'pending': pending,
        'activities': activities[:10], 'year': year,
        'unread': unread, 'unread_messages': unread_messages,
        'section': 'accueil',
    })


@role_required('secretaire')
def eleves(request):
    q = request.GET.get('q', '').strip()
    qs = Student.objects.all().order_by('last_name', 'first_name')
    if q:
        qs = qs.filter(Q(last_name__icontains=q) | Q(first_name__icontains=q) | Q(matricule__icontains=q))
    page_qs = qs[:200]
    return render(request, 'secretariat/eleves.html', {
        'students': page_qs, 'q': q, 'total': qs.count(), 'section': 'eleves',
    })


@require_POST
@role_required('secretaire')
def eleve_archive(request, pk):
    student = get_object_or_404(Student, pk=pk)
    student.status = 'inactif' if student.status == 'actif' else 'actif'
    student.save(update_fields=['status'])
    if student.user_id:
        student.user.is_active = student.status == 'actif'
        student.user.save(update_fields=['is_active'])
    messages.success(request, 'Statut du dossier mis à jour.')
    return redirect('secretariat:eleves')


@role_required('secretaire')
def transfert(request, pk):
    student = get_object_or_404(Student, pk=pk)
    year = _year()
    classrooms = ClassRoom.objects.filter(academic_year=year).order_by('name')
    if request.method == 'POST':
        classroom_id = request.POST.get('classroom')
        target_year_id = request.POST.get('academic_year') or (year.pk if year else None)
        classroom = ClassRoom.objects.filter(pk=classroom_id).first()
        target_year = AcademicYear.objects.filter(pk=target_year_id).first()
        if not classroom or not target_year:
            messages.error(request, 'Choisissez une classe et une année valides.')
        else:
            Enrollment.objects.filter(student=student, is_active=True).update(
                is_active=False, end_status='transferred'
            )
            Enrollment.objects.update_or_create(
                student=student, academic_year=target_year,
                defaults={'classroom': classroom, 'enrollment_date': date.today(), 'is_active': True},
            )
            messages.success(request, f'{student.full_name} affecté(e) à {classroom.name}.')
            return redirect('secretariat:eleves')
    return render(request, 'secretariat/transfert.html', {
        'student': student, 'classrooms': classrooms,
        'years': AcademicYear.objects.order_by('-is_current', '-start_date'),
        'year': year, 'section': 'eleves',
    })


@role_required('secretaire')
def inscriptions(request):
    year = _year()
    qs = Enrollment.objects.select_related('student', 'classroom', 'academic_year').order_by('-created_at')
    if request.method == 'POST':
        student_id = request.POST.get('student')
        classroom_id = request.POST.get('classroom')
        academic_year_id = request.POST.get('academic_year')
        parent_name = request.POST.get('parent_name', '').strip()
        parent_phone = request.POST.get('parent_phone', '').strip()
        if not (student_id and classroom_id and academic_year_id):
            messages.error(request, 'Élève, classe et année sont obligatoires.')
        else:
            enr, created = Enrollment.objects.update_or_create(
                student_id=student_id, academic_year_id=academic_year_id,
                defaults={'classroom_id': classroom_id, 'enrollment_date': date.today(), 'is_active': True},
            )
            if parent_name and parent_phone:
                parts = parent_name.split()
                first = parts[0]
                last = ' '.join(parts[1:]) or first
                parent, _ = Parent.objects.get_or_create(
                    phone=parent_phone, first_name=first, last_name=last,
                )
                ParentStudent.objects.get_or_create(
                    parent=parent, student_id=student_id,
                    defaults={'relation': request.POST.get('relation', 'pere'), 'is_primary': True},
                )
            messages.success(request, 'Inscription enregistrée.')
            return redirect('secretariat:inscriptions')
    return render(request, 'secretariat/inscriptions.html', {
        'enrollments': qs[:150], 'students': Student.objects.order_by('last_name', 'first_name'),
        'classrooms': ClassRoom.objects.filter(academic_year=year).order_by('name') if year else ClassRoom.objects.none(),
        'years': AcademicYear.objects.order_by('-is_current', '-start_date'),
        'year': year, 'section': 'inscriptions',
    })


@role_required('secretaire')
def classes(request):
    year = _year()
    qs = ClassRoom.objects.filter(academic_year=year).annotate(
        n_students=Count('enrollments', filter=Q(enrollments__is_active=True), distinct=True)
    ).select_related('level').order_by('name') if year else ClassRoom.objects.none()
    return render(request, 'secretariat/classes.html', {
        'classes': qs, 'year': year, 'section': 'classes',
    })


@role_required('secretaire')
def classe_eleves(request, classroom_id):
    classroom = get_object_or_404(ClassRoom, pk=classroom_id)
    students = Student.objects.filter(
        enrollments__classroom=classroom, enrollments__is_active=True
    ).order_by('last_name', 'first_name')
    return render(request, 'secretariat/classe_eleves.html', {
        'classroom': classroom, 'students': students, 'section': 'classes',
    })


@role_required('secretaire')
def enseignants(request):
    qs = Teacher.objects.filter(is_active=True).annotate(
        n_classes=Count('assignments__classroom', distinct=True)
    ).order_by('last_name', 'first_name')
    return render(request, 'secretariat/enseignants.html', {
        'teachers': qs, 'section': 'enseignants',
    })


@role_required('secretaire')
def documents(request):
    return render(request, 'secretariat/documents.html', {
        'students': Student.objects.order_by('last_name', 'first_name')[:200],
        'classes': ClassRoom.objects.order_by('name'),
        'section': 'documents',
    })


@role_required('secretaire')
def doc_certificat(request, student_id):
    s = get_object_or_404(Student, pk=student_id)
    enr = s.current_enrollment()
    lines = [
        f'Je soussigné(e) responsable de {_school_name_short()},',
        'certifie que :',
        f'   {s.full_name}, matricule {s.matricule},',
        f'né(e) le {s.date_of_birth.strftime("%d/%m/%Y")} à {s.place_of_birth or "—"},',
        'est bien inscrit(e) dans notre établissement pour l\'année scolaire en cours.',
        '',
        f'Classe : {enr.classroom.name if enr else "—"}',
        f'Année scolaire : {enr.academic_year.name if enr else "—"}',
        '',
        'Certificat délivré pour servir et valoir ce que de droit.',
        '',
        f'Fait à Abidjan, le {date.today().strftime("%d/%m/%Y")}',
    ]
    return document_pdf('Certificat de scolarité', lines, f'certificat_{s.matricule}.pdf')


@role_required('secretaire')
def doc_attestation(request, student_id):
    s = get_object_or_404(Student, pk=student_id)
    enr = s.current_enrollment()
    lines = [
        'Attestation de fréquentation scolaire',
        '',
        f'Élève : {s.full_name} ({s.matricule})',
        f'Classe : {enr.classroom.name if enr else "—"}',
        f'Année scolaire : {enr.academic_year.name if enr else "—"}',
        '',
        'L\'intéressé(e) suit régulièrement les cours de cette classe.',
        f'Fait le {date.today().strftime("%d/%m/%Y")}',
    ]
    return document_pdf('Attestation', lines, f'attestation_{s.matricule}.pdf')


@role_required('secretaire')
def doc_fiche(request, student_id):
    s = get_object_or_404(Student, pk=student_id)
    enr = s.current_enrollment()
    links = ParentStudent.objects.filter(student=s).select_related('parent')
    lines = [
        f'Nom : {s.last_name}     Prénom : {s.first_name}',
        f'Matricule : {s.matricule}     Sexe : {s.get_gender_display()}',
        f'Date de naissance : {s.date_of_birth.strftime("%d/%m/%Y")}',
        f'Lieu : {s.place_of_birth or "—"}     Nationalité : {s.nationality}',
        f'Adresse : {s.address or "—"}     Tél : {s.phone or "—"}',
        '',
        f'Classe : {enr.classroom.name if enr else "—"}',
        f'Année scolaire : {enr.academic_year.name if enr else "—"}',
        '',
        'Parent(s) / tuteur(s) :',
    ]
    for l in links:
        lines.append(f'  - {l.parent.first_name} {l.parent.last_name} ({l.get_relation_display()}) : {l.parent.phone}')
    return document_pdf('Fiche d\'inscription', lines, f'fiche_{s.matricule}.pdf')


@role_required('secretaire')
def doc_liste_classe(request, classroom_id):
    c = get_object_or_404(ClassRoom, pk=classroom_id)
    students = Student.objects.filter(
        enrollments__classroom=c, enrollments__is_active=True
    ).order_by('last_name', 'first_name')
    lines = [f'Classe : {c.name}', f'Niveau : {c.level.name if c.level else "—"}',
             f'Effectif : {students.count()}', '']
    for i, s in enumerate(students, 1):
        lines.append(f'{i:2}. {s.last_name} {s.first_name} — {s.matricule}')
    return document_pdf('Liste des élèves', lines, f'liste_{c.name.replace(" ", "_")}.pdf')


def _school_name_short():
    try:
        from core.models import SchoolSettings
        return SchoolSettings.get_solo().name or 'l\'établissement'
    except Exception:
        return 'l\'établissement'


@role_required('secretaire')
def annonces(request):
    if request.method == 'POST' and request.POST.get('action') == 'message':
        recipient = User.objects.filter(
            pk=request.POST.get('recipient'), is_active=True
        ).first()
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
        return redirect('secretariat:annonces')

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        content = request.POST.get('content', '').strip()
        target = request.POST.get('target', 'all')
        if title and content:
            Announcement.objects.create(
                title=title, content=content, target=target,
                author=request.user, is_published=True,
                expires_at=timezone.now() + timedelta(days=30),
            )
            messages.success(request, 'Annonce publiée.')
            return redirect('secretariat:annonces')
        messages.error(request, 'Titre et contenu obligatoires.')

    qs = Announcement.objects.order_by('-published_at')[:30]
    incoming = Message.objects.filter(recipient=request.user).order_by('-sent_at')[:30]
    return render(request, 'secretariat/annonces.html', {
        'announcements': qs, 'messages': incoming,
        'contacts': allowed_recipients(request.user), 'section': 'annonces',
    })


@require_POST
@role_required('secretaire')
def transmettre_direction(request, pk):
    msg = get_object_or_404(Message, pk=pk)
    direction = _first_user_with_role('directeur')
    if not direction:
        messages.error(request, 'Aucun directeur trouvé.')
    else:
        Message.objects.create(
            sender=request.user, recipient=direction,
            subject=f'Transmission : {msg.subject}',
            body=f'Message de {msg.sender.get_full_name() or msg.sender.username} :\n\n{msg.body}',
        )
        messages.success(request, 'Message transmis à la direction.')
    return redirect('secretariat:annonces')


@role_required('secretaire')
def notifications(request):
    qs = Notification.objects.filter(user=request.user).order_by('-created_at')[:60]
    if request.method == 'POST':
        Notification.objects.filter(user=request.user, id__in=request.POST.getlist('ids')).update(is_read=True)
        messages.success(request, 'Notifications marquées comme lues.')
        return redirect('secretariat:notifications')
    return render(request, 'secretariat/notifications.html', {
        'notifications': qs, 'section': 'notifications',
    })


@role_required('secretaire')
def profil(request):
    return render(request, 'secretariat/profil.html', {
        'user': request.user, 'profile': request.user.profile,
        'section': 'profil',
    })
