"""
PDF bulletins — modèle secondaire/lycée N&B, compact (proche du papier).
- 1 élève → A4 portrait
- Classe → A4 paysage, 2 bulletins côte à côte
Logo en haut · Cachet en bas près de la signature
"""
from io import BytesIO
import os

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
    PageBreak, Image,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT


BLACK = colors.black
WHITE = colors.white
GRAY_HEADER = colors.Color(0.78, 0.78, 0.78)

HALF_W = 140 * mm
FULL_W = 190 * mm


def _fmt(v, digits=2):
    if v is None:
        return ''
    try:
        n = float(v)
        if digits == 0:
            return f'{n:.0f}'
        s = f'{n:.{digits}f}'.rstrip('0').rstrip('.')
        return s.replace('.', ',')
    except (TypeError, ValueError):
        return str(v)


def _styles(compact=False):
    base = getSampleStyleSheet()
    fs = 7 if compact else 8.5
    return {
        'small': ParagraphStyle('s', parent=base['Normal'], fontSize=fs, leading=fs + 1.5),
        'small_c': ParagraphStyle('sc', parent=base['Normal'], fontSize=fs, leading=fs + 1.5, alignment=TA_CENTER),
        'cell': ParagraphStyle('cell', parent=base['Normal'], fontSize=fs, leading=fs + 1.2),
        'cell_c': ParagraphStyle('cellc', parent=base['Normal'], fontSize=fs, leading=fs + 1.2, alignment=TA_CENTER),
        'school': ParagraphStyle(
            'sch', parent=base['Normal'], fontSize=10 if compact else 13,
            leading=12, alignment=TA_CENTER, fontName='Helvetica-Bold',
        ),
        'title': ParagraphStyle(
            'tit', parent=base['Normal'], fontSize=8.5 if compact else 10,
            leading=10, alignment=TA_CENTER, fontName='Helvetica-Bold',
        ),
        'th': ParagraphStyle(
            'th', parent=base['Normal'], fontSize=6.5 if compact else 7.5,
            leading=8, alignment=TA_CENTER, fontName='Helvetica-Bold',
        ),
        'sig': ParagraphStyle(
            'sig', parent=base['Normal'], fontSize=fs, leading=fs + 2, alignment=TA_LEFT,
        ),
    }


def _noop(canvas, doc):
    pass


def _page_number(canvas, doc):
    canvas.saveState()
    canvas.setFont('Helvetica', 7)
    canvas.setFillColor(colors.Color(0.4, 0.4, 0.4))
    w, h = doc.pagesize
    canvas.drawCentredString(w / 2, 4 * mm, f'Page {canvas.getPageNumber()}')
    canvas.restoreState()


def _school_image(field, size_mm=20):
    if not field:
        return None
    candidates = []
    try:
        if getattr(field, 'path', None):
            candidates.append(field.path)
    except Exception:
        pass
    try:
        if field.name:
            from django.conf import settings
            candidates.append(os.path.join(settings.MEDIA_ROOT, field.name))
    except Exception:
        pass
    for path in candidates:
        if path and os.path.isfile(path):
            try:
                img = Image(path, width=size_mm * mm, height=size_mm * mm, kind='proportional')
                img.hAlign = 'CENTER'
                return img
            except Exception:
                continue
    try:
        field.open('rb')
        data_bytes = field.read()
        field.close()
        if data_bytes:
            buf = BytesIO(data_bytes)
            img = Image(buf, width=size_mm * mm, height=size_mm * mm, kind='proportional')
            img.hAlign = 'CENTER'
            return img
    except Exception:
        pass
    return None


def _logo_cell(school, size_mm=14):
    """Logo école uniquement (pas le cachet)."""
    img = _school_image(getattr(school, 'logo', None) if school else None, size_mm=size_mm)
    if img:
        return img
    # Petit ovale placeholder discret
    data = [[Paragraph('<b>LOGO</b>', ParagraphStyle(
        'lg', fontSize=6, alignment=TA_CENTER, textColor=WHITE, fontName='Helvetica-Bold',
    ))]]
    t = Table(data, colWidths=[22 * mm], rowHeights=[8 * mm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), BLACK),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROUNDEDCORNERS', [5, 5, 5, 5]),
    ]))
    t.hAlign = 'CENTER'
    return t


def _build_one_bulletin(ctx, width, compact=True):
    st = _styles(compact=compact)
    school = ctx.get('school')
    student = ctx['student']
    enrollment = ctx.get('enrollment')
    period = ctx.get('period')
    current_year = ctx.get('current_year')
    rows = list(ctx.get('subject_results') or [])

    inner = width - 5 * mm
    pad = 1.0 if compact else 1.5
    elements = []

    # Logo (uniquement school.logo)
    elements.append([_logo_cell(school, size_mm=12 if compact else 16)])

    name = (school.name if school else '') or ''
    title_school = f'ECOLE PRIVÉE « {name} »' if name else 'ECOLE PRIVÉE «  »'
    elements.append([Paragraph(title_school, st['school'])])

    period_label = (period.name if period else '') or 'TRIMESTRE'
    banner_txt = period_label.upper()
    if 'COMPOSITION' not in banner_txt:
        banner_txt = f'COMPOSITION DU {banner_txt}'
    banner = Table([[Paragraph(f'<b>{banner_txt}</b>', st['title'])]], colWidths=[inner])
    banner.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.7, BLACK),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    elements.append([banner])

    classe = enrollment.classroom.name if enrollment else ''
    if enrollment and getattr(enrollment.classroom, 'serie', None):
        classe = f'{classe} ({enrollment.classroom.serie})'
    year_label = current_year.name if current_year else (
        getattr(school, 'academic_year_label', None) or ''
    )
    id_data = [
        [Paragraph('<b>Nom</b>', st['small']), Paragraph(student.last_name or '', st['small'])],
        [Paragraph('<b>Prénom</b>', st['small']), Paragraph(student.first_name or '', st['small'])],
        [Paragraph('<b>Classe</b>', st['small']), Paragraph(classe, st['small'])],
        [Paragraph('<b>Année Scolaire</b>', st['small']), Paragraph(str(year_label), st['small'])],
    ]
    id_t = Table(id_data, colWidths=[34 * mm, inner - 34 * mm])
    id_t.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.6, BLACK),
        ('INNERGRID', (0, 0), (-1, -1), 0.35, BLACK),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), pad),
        ('BOTTOMPADDING', (0, 0), (-1, -1), pad),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
    ]))
    elements.append([id_t])

    # Tableau notes — lignes = matières réelles + 2 vides max
    header = [
        Paragraph('<b>Matières</b>', st['th']),
        Paragraph('<b>Coef</b>', st['th']),
        Paragraph('<b>Classe<br/>Sur 20</b>', st['th']),
        Paragraph('<b>Comp<br/>Sur 40</b>', st['th']),
        Paragraph('<b>Moy</b>', st['th']),
        Paragraph('<b>Moy<br/>Coef</b>', st['th']),
    ]
    data = [header]
    for r in rows:
        data.append([
            Paragraph(str(r['subject'].name)[:32], st['cell']),
            Paragraph(_fmt(r.get('coefficient'), 0), st['cell_c']),
            Paragraph(_fmt(r.get('note_classe')), st['cell_c']),
            Paragraph(_fmt(r.get('note_composition_40')), st['cell_c']),
            Paragraph(_fmt(r.get('average')), st['cell_c']),
            Paragraph(_fmt(r.get('moy_coef')), st['cell_c']),
        ])
    # Seulement 2 lignes vides pour aérer un peu (pas 10)
    for _ in range(2):
        data.append(['', '', '', '', '', ''])

    col_w = [
        inner * 0.34, inner * 0.09, inner * 0.15,
        inner * 0.15, inner * 0.12, inner * 0.15,
    ]
    notes = Table(data, colWidths=col_w)
    notes.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 7 if compact else 8),
        ('BACKGROUND', (0, 0), (-1, 0), GRAY_HEADER),
        ('GRID', (0, 0), (-1, -1), 0.4, BLACK),
        ('BOX', (0, 0), (-1, -1), 0.7, BLACK),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), pad),
        ('BOTTOMPADDING', (0, 0), (-1, -1), pad),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
    ]))
    elements.append([notes])

    # Totaux + Appréciations (même hauteur visuelle)
    rank = ctx.get('rank')
    rank_total = ctx.get('rank_total')
    rank_str = f'{rank}e / {rank_total}' if rank and rank_total else (str(rank) if rank else '')

    left_w = inner * 0.48
    right_w = inner * 0.50
    left_rows = [
        [Paragraph('<b>Total Général :</b>', st['small']),
         Paragraph(_fmt(ctx.get('total_moy_coef')), st['small_c'])],
        [Paragraph('<b>Total des Coefficients :</b>', st['small']),
         Paragraph(_fmt(ctx.get('total_coef'), 0), st['small_c'])],
        [Paragraph('<b>Moyenne Obtenue :</b>', st['small']),
         Paragraph(_fmt(ctx.get('general_avg')), st['small_c'])],
        [Paragraph('<b>Moyenne du 1<sup>er</sup> ou 2<sup>ème</sup> :</b>', st['small']),
         Paragraph(_fmt(ctx.get('prev_avg')), st['small_c'])],
        [Paragraph('<b>Rang :</b>', st['small']),
         Paragraph(rank_str, st['small_c'])],
    ]
    left = Table(left_rows, colWidths=[left_w * 0.72, left_w * 0.28])
    left.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.4, BLACK),
        ('BOX', (0, 0), (-1, -1), 0.6, BLACK),
        ('TOPPADDING', (0, 0), (-1, -1), pad),
        ('BOTTOMPADDING', (0, 0), (-1, -1), pad),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))

    appr = ctx.get('appreciation') or ''
    # Hauteur appréciations ≈ hauteur bloc totaux
    appr_h = 22 * mm if compact else 26 * mm
    appr_box = Table(
        [
            [Paragraph('<b>Appréciations</b>', st['small_c'])],
            [Paragraph(appr, st['small'])],
        ],
        colWidths=[right_w],
        rowHeights=[6 * mm, appr_h],
    )
    appr_box.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.6, BLACK),
        ('LINEBELOW', (0, 0), (-1, 0), 0.35, BLACK),
        ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
        ('VALIGN', (0, 1), (-1, 1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
    ]))

    bottom = Table([[left, appr_box]], colWidths=[left_w, right_w])
    bottom.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (0, 0), 3),
    ]))
    elements.append([bottom])

    # Signature + cachet (stamp uniquement ici, pas en haut)
    director = (school.director_name if school and school.director_name else '') or ''
    stamp_img = _school_image(
        getattr(school, 'stamp', None) if school else None,
        size_mm=20 if compact else 26,
    )
    sig_txt = Paragraph(
        f'<b>Le Directeur</b><br/>{director}<br/><br/>______________',
        st['sig'],
    )
    if stamp_img:
        sig_row = Table(
            [[sig_txt, stamp_img]],
            colWidths=[inner * 0.55, inner * 0.42],
        )
        sig_row.setStyle(TableStyle([
            ('VALIGN', (0, 0), (0, 0), 'BOTTOM'),
            ('VALIGN', (1, 0), (1, 0), 'MIDDLE'),
            ('ALIGN', (1, 0), (1, 0), 'CENTER'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ]))
    else:
        sig_row = Table([[sig_txt]], colWidths=[inner])
        sig_row.setStyle(TableStyle([
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ]))
    elements.append([sig_row])

    body = Table(elements, colWidths=[inner])
    body.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),  # logo centré
        ('ALIGN', (0, 1), (-1, 1), 'CENTER'),  # titre centré
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 1.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))

    framed = Table([[body]], colWidths=[width])
    framed.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1.4, BLACK),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    return framed


def _build_primary_bulletin(ctx, width):
    st = _styles(compact=False)
    school = ctx.get('school')
    student = ctx['student']
    enrollment = ctx.get('enrollment')
    period = ctx.get('period')
    current_year = ctx.get('current_year')
    rows = list(ctx.get('subject_results') or [])
    inner = width - 6 * mm
    elements = []

    elements.append([_logo_cell(school, 14)])
    name = (school.name if school else '') or 'École'
    elements.append([Paragraph(f'ECOLE PRIVÉE « {name} »', st['school'])])
    elements.append([Paragraph('BULLETIN SCOLAIRE — PRIMAIRE', st['title'])])

    classe = enrollment.classroom.name if enrollment else '—'
    year_label = current_year.name if current_year else '—'
    period_label = period.name if period else ''
    elements.append([Paragraph(
        f'<b>Nom :</b> {student.last_name} &nbsp; <b>Prénom :</b> {student.first_name}<br/>'
        f'<b>Classe :</b> {classe} &nbsp; <b>Année :</b> {year_label} &nbsp; <b>Période :</b> {period_label}',
        st['small'],
    )])

    data = [[
        Paragraph('<b>Matière</b>', st['th']),
        Paragraph('<b>Moyenne /10</b>', st['th']),
        Paragraph('<b>Coef.</b>', st['th']),
        Paragraph('<b>Moy × Coef</b>', st['th']),
    ]]
    for r in rows:
        data.append([
            Paragraph(str(r['subject'].name)[:35], st['cell']),
            Paragraph(_fmt(r.get('average')), st['cell_c']),
            Paragraph(_fmt(r.get('coefficient'), 0), st['cell_c']),
            Paragraph(_fmt(r.get('moy_coef')), st['cell_c']),
        ])
    for _ in range(2):
        data.append(['', '', '', ''])
    t = Table(data, colWidths=[inner * 0.40, inner * 0.20, inner * 0.18, inner * 0.22])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), GRAY_HEADER),
        ('GRID', (0, 0), (-1, -1), 0.45, BLACK),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    elements.append([t])
    elements.append([Paragraph(
        f"<b>Moyenne générale :</b> {_fmt(ctx.get('general_avg'))} / 10<br/>"
        f"<b>Appréciation :</b> {ctx.get('appreciation') or '—'}",
        st['small'],
    )])
    director = (school.director_name if school and school.director_name else '') or ''
    stamp_img = _school_image(getattr(school, 'stamp', None) if school else None, size_mm=24)
    sig_left = Paragraph(
        f'<b>Le Directeur</b><br/>{director}<br/><br/>______________',
        st['sig'],
    )
    if stamp_img:
        elements.append([Table(
            [[sig_left, stamp_img]],
            colWidths=[inner * 0.55, inner * 0.40],
        )])
    else:
        elements.append([sig_left])

    body = Table(elements, colWidths=[inner])
    body.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, 1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    framed = Table([[body]], colWidths=[width])
    framed.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1.4, BLACK),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    return framed


def render_bulletin_pdf(contexts):
    buffer = BytesIO()
    multi = len(contexts) > 1
    all_secondary = multi and all(not c.get('is_primary') for c in contexts)

    if all_secondary:
        pagesize = landscape(A4)
        margin = 6 * mm
        col_w = HALF_W
        gap = 4 * mm
    else:
        pagesize = A4
        margin = 12 * mm
        col_w = FULL_W
        gap = 0

    doc = SimpleDocTemplate(
        buffer,
        pagesize=pagesize,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=margin,
        bottomMargin=margin,
        title='Bulletins scolaires',
        author='SiraScol',
    )
    story = []

    if all_secondary:
        for i in range(0, len(contexts), 2):
            if i > 0:
                story.append(PageBreak())
            left = _build_one_bulletin(contexts[i], width=col_w, compact=True)
            if i + 1 < len(contexts):
                right = _build_one_bulletin(contexts[i + 1], width=col_w, compact=True)
            else:
                right = Spacer(col_w, 1)
            row = Table([[left, right]], colWidths=[col_w, col_w])
            row.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (0, 0), gap / 2),
                ('LEFTPADDING', (1, 0), (1, 0), gap / 2),
            ]))
            story.append(row)
    else:
        for i, ctx in enumerate(contexts):
            if i > 0:
                story.append(PageBreak())
            if ctx.get('is_primary'):
                story.append(_build_primary_bulletin(ctx, width=col_w))
            else:
                story.append(_build_one_bulletin(ctx, width=col_w, compact=False))

    if not story:
        story.append(Paragraph('Aucun bulletin.', getSampleStyleSheet()['Normal']))

    doc.build(story, onFirstPage=_noop, onLaterPages=_noop)
    return buffer.getvalue()


def build_secondary_page(story, ctx):
    story.append(_build_one_bulletin(ctx, width=FULL_W, compact=False))


def build_primary_page(story, ctx):
    story.append(_build_primary_bulletin(ctx, width=FULL_W))
