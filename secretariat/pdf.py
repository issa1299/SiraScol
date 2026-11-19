"""Génération de documents administratifs PDF (reportlab)."""

import io

from django.http import HttpResponse
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from core.models import SchoolSettings

# Helvetica gère l'essentiel de Latin-1 (accents français inclus).
FONT = 'Helvetica'
BOLD = 'Helvetica-Bold'


def _school_name():
    try:
        return SchoolSettings.get_solo().name or 'SiraScol'
    except Exception:
        return 'SiraScol'


def _draw_lines(pdf, lines, x, y, width=520, leading=16):
    for raw in lines:
        text = str(raw or '')
        while pdfmetrics.stringWidth(text, FONT, 10) > width and len(text) > 4:
            cut = int(len(text) * width / max(1, pdfmetrics.stringWidth(text, FONT, 10)))
            cut = max(4, min(len(text) - 1, cut))
            pdf.drawString(x, y, text[:cut])
            text = '   ' + text[cut:]
            y -= leading
        pdf.drawString(x, y, text)
        y -= leading
    return y


def document_pdf(title, lines, filename='document.pdf'):
    """Retourne une HttpResponse PDF avec un en-tête établissement."""
    buf = io.BytesIO()
    pdf = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    pdf.setFont(BOLD, 16)
    pdf.drawCentredString(width / 2, height - 60, _school_name())
    pdf.setFont(BOLD, 13)
    pdf.drawCentredString(width / 2, height - 90, title)
    pdf.line(60, height - 105, width - 60, height - 105)
    y = _draw_lines(pdf, lines, 70, height - 145)
    pdf.setFont(FONT, 8)
    pdf.drawCentredString(width / 2, 45, 'Document généré par SiraScol')
    pdf.showPage()
    pdf.save()
    response = HttpResponse(buf.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
