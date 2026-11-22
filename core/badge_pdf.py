# -*- coding: utf-8 -*-
"""PDF des badges — même géométrie et mêmes couleurs que l'aperçu HTML.

ReportLab est utilisé (pur Python, fiable en production) avec des polices TTF
embarquées et des tailles de texte converties depuis la grille 1012 × 638 px.
"""
import os

from django.conf import settings

from core.badge import CARD_H_MM, CARD_W_MM

_W_PT = None
_H_PT = None
_FONTS = {}


def _init():
    global _W_PT, _H_PT
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    if _W_PT is None:
        _W_PT, _H_PT = CARD_W_MM * mm, CARD_H_MM * mm
    folder = os.path.join(settings.BASE_DIR, 'static', 'fonts')
    for name, filename in (('Vera', 'Vera.ttf'), ('VeraBd', 'VeraBd.ttf')):
        if name not in _FONTS:
            path = os.path.join(folder, filename)
            if os.path.exists(path):
                try:
                    pdfmetrics.registerFont(TTFont(name, path))
                except Exception:
                    pass
                _FONTS[name] = name
    return _W_PT, _H_PT


def P(px):
    """px (grille 1012) -> points."""
    w, _ = _init()
    return px * w / 1012.0


def Y(top_px):
    """Coordonnée verticale depuis le HAUT -> y reportlab."""
    _, h = _init()
    return h - P(top_px)


def render_badges_pdf(badges):
    """Une carte par page, au format 85,6 × 54 mm."""
    from io import BytesIO
    from reportlab.pdfgen import canvas
    from students.card_mali import draw_badge_pdf

    _init()
    w, h = _init()
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(w, h))
    for badge in badges:
        draw_badge_pdf(c, badge, y0=0)
        c.showPage()
    c.save()
    buf.seek(0)
    return buf.getvalue()


def render_badge_pdf(badge):
    return render_badges_pdf([badge])
