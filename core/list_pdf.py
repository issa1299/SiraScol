"""Export PDF propres (tableaux) sans interface web."""
from io import BytesIO
from datetime import date

from django.http import HttpResponse
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT


def build_list_pdf(title, subtitle, headers, rows, filename, landscape_mode=False):
    buf = BytesIO()
    pagesize = landscape(A4) if landscape_mode else A4
    doc = SimpleDocTemplate(
        buf, pagesize=pagesize,
        leftMargin=12 * mm, rightMargin=12 * mm,
        topMargin=12 * mm, bottomMargin=12 * mm,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'T', parent=styles['Heading1'], fontSize=14, alignment=TA_CENTER,
        textColor=colors.HexColor('#1e40af'), spaceAfter=2,
    )
    sub_style = ParagraphStyle(
        'S', parent=styles['Normal'], fontSize=9, alignment=TA_CENTER,
        textColor=colors.HexColor('#64748b'), spaceAfter=10,
    )
    story = []
    story.append(Paragraph(str(title), title_style))
    if subtitle:
        story.append(Paragraph(str(subtitle), sub_style))

    data = [headers]
    for r in rows:
        data.append([str(c) if c is not None else '—' for c in r])
    if len(data) == 1:
        data.append(['—'] * len(headers))

    n = len(headers)
    page_w = pagesize[0] - 24 * mm
    col_w = page_w / n
    table = Table(data, colWidths=[col_w] * n, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e40af')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#cbd5e1')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(table)
    doc.build(story)
    pdf = buf.getvalue()
    buf.close()
    resp = HttpResponse(pdf, content_type='application/pdf')
    resp['Content-Disposition'] = f'attachment; filename="{filename}"'
    return resp
