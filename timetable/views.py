from functools import wraps

from core.year_context import get_selected_year
from core.permissions import get_role, get_teacher_classrooms
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.http import HttpResponse

from .models import TimetableEntry, TimeSlot, Room
from academics.models import ClassRoom, AcademicYear, Subject
from teachers.models import Teacher


DAYS = [
    (1, 'Lundi'), (2, 'Mardi'), (3, 'Mercredi'),
    (4, 'Jeudi'), (5, 'Vendredi'), (6, 'Samedi'),
]

# Couleurs légères par matière (hash)
COLORS = [
    ('bg-blue-50', 'border-blue-200', 'text-blue-900'),
    ('bg-emerald-50', 'border-emerald-200', 'text-emerald-900'),
    ('bg-amber-50', 'border-amber-200', 'text-amber-900'),
    ('bg-violet-50', 'border-violet-200', 'text-violet-900'),
    ('bg-rose-50', 'border-rose-200', 'text-rose-900'),
    ('bg-cyan-50', 'border-cyan-200', 'text-cyan-900'),
    ('bg-orange-50', 'border-orange-200', 'text-orange-900'),
]


def _students_use_portal(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if get_role(request.user) == 'eleve' and not request.user.is_superuser:
            return redirect('eleve:timetable')
        return view_func(request, *args, **kwargs)
    return _wrapped


def _color_for(name):
    if not name:
        return COLORS[0]
    return COLORS[sum(ord(c) for c in name) % len(COLORS)]


DEFAULT_SLOTS_TEXT = """07:00 - 10:00
10:00 - 12:00
Récréation
14:00 - 16:00
16:00 - 18:00
Soir"""


def _is_break_slot(slot_or_name):
    """Créneau spécial (Récréation, Soir, Pause...) sans cours."""
    name = slot_or_name if isinstance(slot_or_name, str) else (slot_or_name.name or '')
    n = name.strip().lower()
    return n in ('récréation', 'recreation', 'recréation', 'soir', 'pause', 'déjeuner', 'dejeuner') or n.startswith('pause:')


def ensure_default_slots():
    """Crée les créneaux par défaut s'il n'y en a aucun."""
    if TimeSlot.objects.exists():
        return
    from datetime import time
    lines = [ln.strip() for ln in DEFAULT_SLOTS_TEXT.strip().splitlines() if ln.strip()]
    for i, line in enumerate(lines, start=1):
        if _is_break_slot(line) or (':' not in line and '-' not in line):
            # Pause : mêmes heures fictives pour l'ordre
            TimeSlot.objects.create(
                name=line.replace('PAUSE:', '').strip(),
                start_time=time(0, 0),
                end_time=time(0, 0),
                order=i,
            )
            continue
        parts = line.replace('–', '-').split('-')
        if len(parts) != 2:
            continue
        def parse_t(s):
            s = s.strip().replace('h', ':')
            hh, mm = s.split(':')
            return time(int(hh), int(mm))
        try:
            st, et = parse_t(parts[0]), parse_t(parts[1])
        except Exception:
            continue
        TimeSlot.objects.create(
            name=f'{st.strftime("%H:%M")}-{et.strftime("%H:%M")}',
            start_time=st,
            end_time=et,
            order=i,
        )


@login_required
@_students_use_portal
def timetable_home(request):
    from datetime import date
    ensure_default_slots()
    current_year = get_selected_year(request)
    classrooms = ClassRoom.objects.select_related('level', 'level__cycle', 'academic_year').order_by(
        'level__cycle__order', 'level__order', 'name'
    )
    if current_year:
        classrooms = classrooms.filter(academic_year=current_year)

    role = get_role(request.user)
    if role == 'enseignant' and not request.user.is_superuser:
        classrooms = classrooms.filter(
            id__in=get_teacher_classrooms(request.user).values_list('id', flat=True)
        )

    tab = request.GET.get('tab', 'horaires')
    classroom_id = request.GET.get('classroom', '')
    classroom = None
    slots = list(TimeSlot.objects.order_by('order'))
    rows = []
    subjects = Subject.objects.filter(is_active=True).order_by('name')
    teachers = Teacher.objects.filter(is_active=True).order_by('last_name')
    rooms = Room.objects.all().order_by('name')

    if classroom_id:
        classroom = get_object_or_404(ClassRoom, pk=classroom_id)
        tab = 'horaires'
        entries = {
            (e.day, e.time_slot_id): e
            for e in TimetableEntry.objects.filter(classroom=classroom).select_related(
                'subject', 'teacher', 'room', 'time_slot'
            )
        }
        for slot in slots:
            is_break = _is_break_slot(slot) or (
                slot.start_time.hour == 0 and slot.end_time.hour == 0
                and slot.start_time.minute == 0 and slot.end_time.minute == 0
            )
            cells = []
            if not is_break:
                for d, label in DAYS:
                    entry = entries.get((d, slot.id))
                    color = _color_for(entry.subject.name) if entry and entry.subject_id else None
                    cells.append({
                        'day': d, 'label': label, 'entry': entry, 'color': color,
                    })
            rows.append({'slot': slot, 'cells': cells, 'is_break': is_break})

    def _slot_line(s):
        if _is_break_slot(s):
            return s.name
        if s.start_time.hour == 0 and s.start_time.minute == 0 and s.end_time.hour == 0:
            return s.name
        return f'{s.start_time.strftime("%H:%M")} - {s.end_time.strftime("%H:%M")}'
    slots_text = '\n'.join(_slot_line(s) for s in slots)

    stats = {
        'enseignants': teachers.count(),
        'classes': classrooms.count(),
        'creneaux': len(slots),
        'cours': TimetableEntry.objects.filter(
            classroom__academic_year=current_year
        ).count() if current_year else TimetableEntry.objects.count(),
    }

    read_only = role in ('enseignant', 'parent', 'eleve') and not request.user.is_superuser
    return render(request, 'timetable/pedagogique.html', {
        'read_only': read_only,
        'classrooms': classrooms,
        'classroom_id': str(classroom_id),
        'classroom': classroom,
        'slots': slots,
        'slots_text': slots_text,
        'days': DAYS,
        'rows': rows,
        'current_year': current_year,
        'subjects': subjects,
        'teachers': teachers,
        'rooms': rooms,
        'tab': tab,
        'stats': stats,
        'today': date.today(),
    })


@login_required
@_students_use_portal
@require_POST
def slots_save(request):
    """Enregistre les créneaux (un par ligne: HH:MM - HH:MM)."""
    from datetime import time
    text = request.POST.get('slots_text', '')
    lines = [ln.strip() for ln in text.replace('–', '-').splitlines() if ln.strip()]
    parsed = []
    for i, line in enumerate(lines, start=1):
        # Ligne pause : "Récréation" ou "Soir" ou "PAUSE:Récréation"
        if _is_break_slot(line) or ('-' not in line and ':' not in line):
            label = line.replace('PAUSE:', '').strip()
            parsed.append((i, None, None, label))
            continue
        if '-' not in line:
            continue
        left, right = line.split('-', 1)
        def parse_t(s):
            s = s.strip().replace('h', ':').replace('.', ':')
            parts = s.split(':')
            return time(int(parts[0]), int(parts[1]) if len(parts) > 1 else 0)
        try:
            st, et = parse_t(left), parse_t(right)
        except Exception:
            continue
        parsed.append((i, st, et, None))
    if not parsed:
        messages.error(request, 'Aucun créneau valide. Format: 07:30 - 08:20')
        return redirect('/emploi-du-temps/?tab=configuration')
    # Rebuild slots carefully: update existing by order or recreate if count differs
    existing = list(TimeSlot.objects.order_by('order'))
    # If entries reference slots, prefer update in place
    from datetime import time as dtime
    for i, item in enumerate(parsed):
        order, st, et, break_label = item
        if break_label:
            name = break_label
            st = st or dtime(0, 0)
            et = et or dtime(0, 0)
        else:
            name = f'{st.strftime("%H:%M")}-{et.strftime("%H:%M")}'
        if i < len(existing):
            slot = existing[i]
            slot.name = name
            slot.start_time = st
            slot.end_time = et
            slot.order = order
            slot.save()
        else:
            TimeSlot.objects.create(name=name, start_time=st, end_time=et, order=order)
    # Delete extra slots only if no entries
    if len(existing) > len(parsed):
        for slot in existing[len(parsed):]:
            if not slot.entries.exists():
                slot.delete()
    messages.success(request, f'{len(parsed)} créneau(x) enregistré(s).')
    return redirect('/emploi-du-temps/?tab=configuration')


@login_required
@_students_use_portal
def timetable_entry_save(request, classroom_id):
    classroom = get_object_or_404(ClassRoom, pk=classroom_id)
    role = get_role(request.user)
    if role in ('enseignant', 'parent', 'eleve') and not request.user.is_superuser:
        messages.error(request, "Modification de l'emploi du temps réservée à l'administration.")
        return redirect('timetable:home')
    if request.method != 'POST':
        return redirect('timetable:home')
    day = request.POST.get('day')
    slot = request.POST.get('time_slot')
    subject = request.POST.get('subject')
    teacher = request.POST.get('teacher') or None
    room = request.POST.get('room') or None
    if not day or not slot or not subject:
        messages.error(request, 'Jour, créneau et matière sont obligatoires.')
        return redirect(f'/emploi-du-temps/?classroom={classroom_id}')
    try:
        TimetableEntry.objects.update_or_create(
            classroom=classroom,
            day=int(day),
            time_slot_id=slot,
            defaults={
                'subject_id': subject,
                'teacher_id': teacher or None,
                'room_id': room or None,
            },
        )
        messages.success(request, 'Créneau enregistré.')
    except Exception as e:
        messages.error(request, f'Erreur : {e}')
    return redirect(f'/emploi-du-temps/?classroom={classroom_id}')


@login_required
@_students_use_portal
@require_POST
def timetable_entry_delete(request, pk):
    entry = get_object_or_404(TimetableEntry, pk=pk)
    cid = entry.classroom_id
    entry.delete()
    messages.success(request, 'Créneau supprimé.')
    return redirect(f'/emploi-du-temps/?classroom={cid}')


# Ancien formulaire (compat)
@login_required
@_students_use_portal
def timetable_entry_form(request, classroom_id):
    return redirect(f'/emploi-du-temps/?classroom={classroom_id}')


@login_required
@_students_use_portal
def export_pdf(request, classroom_id):
    """PDF emploi du temps — style propre type modèle école."""
    from io import BytesIO
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

    classroom = get_object_or_404(
        ClassRoom.objects.select_related('level', 'academic_year'), pk=classroom_id
    )
    slots = list(TimeSlot.objects.order_by('order'))
    entries = {
        (e.day, e.time_slot_id): e
        for e in TimetableEntry.objects.filter(classroom=classroom).select_related(
            'subject', 'teacher'
        )
    }
    year = classroom.academic_year

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=landscape(A4),
        leftMargin=15 * mm, rightMargin=15 * mm,
        topMargin=15 * mm, bottomMargin=15 * mm,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'T', parent=styles['Heading1'], fontSize=18, alignment=1,
        spaceAfter=2, textColor=colors.HexColor('#0f172a'),
    )
    sub_style = ParagraphStyle(
        'S', parent=styles['Normal'], fontSize=11, alignment=1,
        textColor=colors.HexColor('#64748b'), spaceAfter=14,
    )
    cell_style = ParagraphStyle(
        'C', parent=styles['Normal'], fontSize=8, leading=11, alignment=1,
        textColor=colors.HexColor('#0f172a'),
    )
    hour_style = ParagraphStyle(
        'H', parent=styles['Normal'], fontSize=8, leading=10,
        textColor=colors.HexColor('#475569'),
    )
    break_style = ParagraphStyle(
        'B', parent=styles['Normal'], fontSize=10, leading=12, alignment=1,
        textColor=colors.HexColor('#64748b'),
    )
    head_style = ParagraphStyle(
        'Hd', parent=styles['Normal'], fontSize=9, leading=11, alignment=1,
        textColor=colors.white,
    )

    story = []
    story.append(Paragraph(f"Emploi du temps : {classroom.name}", title_style))
    sub = f"{classroom.level.name}"
    if year:
        sub += f" · {year.name}"
    story.append(Paragraph(sub, sub_style))

    header = [Paragraph('<b>Heures</b>', head_style)] + [
        Paragraph(f'<b>{label}</b>', head_style) for _, label in DAYS
    ]
    data = [header]
    span_cmds = []  # for break rows
    row_idx = 1
    for slot in slots:
        is_break = _is_break_slot(slot) or (
            slot.start_time.hour == 0 and slot.end_time.hour == 0 and slot.start_time.minute == 0
        )
        if is_break:
            label = slot.name
            row = [Paragraph(f'<i>{label}</i>', break_style)] + [''] * 6
            data.append(row)
            span_cmds.append(('SPAN', (0, row_idx), (-1, row_idx)))
            span_cmds.append(('BACKGROUND', (0, row_idx), (-1, row_idx), colors.HexColor('#e8eef7')))
            span_cmds.append(('ALIGN', (0, row_idx), (-1, row_idx), 'CENTER'))
            row_idx += 1
            continue
        row = [
            Paragraph(
                f"{slot.start_time.strftime('%H:%M')} – {slot.end_time.strftime('%H:%M')}",
                hour_style,
            )
        ]
        for d, _ in DAYS:
            e = entries.get((d, slot.id))
            if e:
                txt = f"<b>{e.subject.name}</b>"
                if e.teacher:
                    txt += f"<br/><font size='7' color='#64748b'>Prof : {e.teacher.last_name}</font>"
                row.append(Paragraph(txt, cell_style))
            else:
                row.append(Paragraph('—', cell_style))
        data.append(row)
        row_idx += 1

    col_w = (doc.width - 32 * mm) / 6
    widths = [32 * mm] + [col_w] * 6
    table = Table(data, colWidths=widths, repeatRows=1)
    style_cmds = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563eb')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('BACKGROUND', (0, 1), (0, -1), colors.HexColor('#f8fafc')),
        ('GRID', (0, 0), (-1, -1), 0.6, colors.HexColor('#3b82f6')),
        ('BOX', (0, 0), (-1, -1), 1.2, colors.HexColor('#2563eb')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
    ] + span_cmds
    table.setStyle(TableStyle(style_cmds))
    story.append(table)
    doc.build(story)
    buf.seek(0)
    filename = f"emploi_{classroom.name}.pdf".replace(' ', '_')
    resp = HttpResponse(buf.read(), content_type='application/pdf')
    resp['Content-Disposition'] = f'attachment; filename="{filename}"'
    return resp



@login_required
@_students_use_portal
def export_word(request, classroom_id):
    """Word (.doc) — même mise en page que le PDF."""
    classroom = get_object_or_404(
        ClassRoom.objects.select_related('level', 'academic_year'), pk=classroom_id
    )
    slots = list(TimeSlot.objects.order_by('order'))
    entries = {
        (e.day, e.time_slot_id): e
        for e in TimetableEntry.objects.filter(classroom=classroom).select_related(
            'subject', 'teacher'
        )
    }
    year = classroom.academic_year
    year_label = f" · {year.name}" if year else ""

    rows_html = []
    for slot in slots:
        is_break = _is_break_slot(slot) or (
            slot.start_time.hour == 0 and slot.end_time.hour == 0 and slot.start_time.minute == 0
        )
        if is_break:
            rows_html.append(
                f'<tr><td colspan="7" style="padding:10px;border:1px solid #3b82f6;'
                f'background:#e8eef7;text-align:center;color:#64748b;font-style:italic;">{slot.name}</td></tr>'
            )
            continue
        cells = [
            f'<td style="padding:8px;border:1px solid #3b82f6;background:#f8fafc;font-size:11px;">'
            f'{slot.start_time.strftime("%H:%M")} – {slot.end_time.strftime("%H:%M")}</td>'
        ]
        for d, _ in DAYS:
            e = entries.get((d, slot.id))
            if e:
                tname = e.teacher.last_name if e.teacher else ''
                cells.append(
                    f'<td style="padding:8px;border:1px solid #3b82f6;text-align:center;font-size:11px;">'
                    f'<b>{e.subject.name}</b><br/>'
                    f'<span style="color:#64748b;font-size:10px;">Prof : {tname}</span></td>'
                )
            else:
                cells.append(
                    '<td style="padding:8px;border:1px solid #3b82f6;text-align:center;color:#94a3b8;">—</td>'
                )
        rows_html.append('<tr>' + ''.join(cells) + '</tr>')

    day_headers = ''.join(
        f'<th style="padding:10px;border:1px solid #2563eb;background:#2563eb;color:#fff;font-size:12px;">{label}</th>'
        for _, label in DAYS
    )
    html = (
        '<html xmlns:o="urn:schemas-microsoft-com:office:office" '
        'xmlns:w="urn:schemas-microsoft-com:office:word" '
        'xmlns="http://www.w3.org/TR/REC-html40">'
        '<head><meta charset="utf-8">'
        '<style>body{font-family:Arial,sans-serif;}</style></head><body>'
        f'<h1 style="text-align:center;font-size:20px;margin-bottom:4px;">Emploi du temps : {classroom.name}</h1>'
        f'<p style="text-align:center;color:#64748b;margin-top:0;">{classroom.level.name}{year_label}</p>'
        '<table style="border-collapse:collapse;width:100%;">'
        '<tr>'
        '<th style="padding:10px;border:1px solid #2563eb;background:#2563eb;color:#fff;font-size:12px;">Heures</th>'
        f'{day_headers}</tr>'
        f'{"".join(rows_html)}'
        '</table></body></html>'
    )
    filename = f"emploi_{classroom.name}.doc".replace(' ', '_')
    resp = HttpResponse(html.encode('utf-8'), content_type='application/msword')
    resp['Content-Disposition'] = f'attachment; filename="{filename}"'
    return resp
