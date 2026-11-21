# -*- coding: utf-8 -*-
"""Moteur de rendu des badges (élèves ET personnel) — format CR80 85,6 × 54 mm.

Les badges HTML, PNG et PDF partagent le même contexte (core.badge) et le même
QR local (core.qr). Cette module ne contient que le dessin.
"""
from io import BytesIO

from core.badge import (
    CARD_H_MM, CARD_W_MM, build_badge_context, get_badge_design,
    parents_pair as _parents_pair,  # compatibilité ascendante
)
from core.qr import qr_png

# ── Géométrie commune (en mm) ────────────────────────────────────────────────
BAND_W = 2.2
HEADER_H = 13.0
# Repères EN HAUT (comme le CSS et PIL) pour garantir un rendu identique partout.
PHOTO = (4.0, 21.0, 21.0, 26.5)          # x, top, largeur, hauteur
FIELD_X = 28.0
FIELD_TOP = 21.0
FIELD_STEP = 3.3
QR = (64.4, 24.0, 15.6)                  # x, top, taille
MAX_LINES = 8


def _trim(text, n):
    text = str(text or '—')
    return text if len(text) <= n else text[: n - 1] + '…'


def _hex_rgb(value):
    value = (value or '#0f172a').lstrip('#')
    if len(value) != 6:
        return (15, 23, 42)
    try:
        return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return (15, 23, 42)


# ═══════════════════════════════ PDF ════════════════════════════════════════
def draw_badge_pdf(c, badge, y0=0):
    """Dessine un badge complet sur un canvas reportlab (page 85.6 × 54 mm)."""
    from reportlab.lib.units import mm
    from reportlab.lib.utils import ImageReader
    from reportlab.lib.colors import HexColor, white

    d = badge['design']
    school = badge['school']
    w, h = CARD_W_MM, CARD_H_MM
    primary = HexColor(d['primary'])
    secondary = HexColor(d['secondary'])
    accent = HexColor(d['accent'])
    ink = HexColor(d['ink'])
    muted = HexColor(d['muted'])
    bg = HexColor(d['bg'])

    def B(top):
        """Ligne de base reportlab pour une coordonnée verticale mesurée depuis le HAUT."""
        return y0 + (h - top) * mm

    # Fond + bande latérale
    c.setFillColor(bg)
    c.rect(0, y0, w * mm, h * mm, fill=1, stroke=0)
    c.setFillColor(HexColor(d['band']))
    c.rect(0, y0, BAND_W * mm, h * mm, fill=1, stroke=0)

    # ── Bandeau ──
    c.setFillColor(primary)
    c.rect(0, B(HEADER_H), w * mm, HEADER_H * mm, fill=1, stroke=0)

    c.setFillColor(white)
    c.setFont('Helvetica', 4.2)
    for i, ln in enumerate(school['left_lines']):
        c.drawString(3.4 * mm, B(3.0 + i * 3.0), _trim(ln.upper(), 30))
    for i, ln in enumerate(school['right_lines']):
        c.drawRightString(w * mm - 3.4 * mm, B(3.0 + i * 3.0), _trim(ln.upper(), 34))

    c.setFont('Helvetica-Bold', 8.4)
    c.drawCentredString(w * mm / 2, B(7.6), _trim(school['name'].upper(), 36))
    c.setFont('Helvetica-Bold', 4.6)
    c.drawCentredString(w * mm / 2, B(11.2), _trim(school['motto'], 48))

    # ── Titre ──
    c.setFillColor(secondary)
    c.setFont('Helvetica-Bold', 8.0)
    c.drawCentredString(w * mm / 2, B(17.4), badge['title'])
    c.setStrokeColor(accent)
    c.setLineWidth(0.7)
    c.line(4 * mm, B(19.3), (w - 4) * mm, B(19.3))

    # ── Photo ──
    px, ptop, pw, ph = PHOTO
    pbottom = CARD_H_MM - ptop - ph
    c.setStrokeColor(accent)
    c.setLineWidth(0.9)
    c.setFillColor(HexColor('#e2e8f0'))
    c.roundRect(px * mm, B(ptop + ph), pw * mm, ph * mm, 1.2 * mm, fill=1, stroke=1)
    drawn = False
    if badge.get('photo_path'):
        try:
            c.drawImage(
                ImageReader(badge['photo_path']),
                px * mm + 0.8 * mm, (pbottom + 0.8) * mm,
                width=(pw - 1.6) * mm, height=(ph - 1.6) * mm,
                preserveAspectRatio=True, anchor='c', mask='auto',
            )
            drawn = True
        except Exception:
            drawn = False
    if not drawn:
        c.setFillColor(HexColor('#94a3b8'))
        c.setFont('Helvetica-Bold', 16)
        c.drawCentredString((px + pw / 2) * mm, B(ptop + ph / 2 + 2), badge['initials'])

    # ── Champs ──
    yy = FIELD_TOP
    for label, value in badge['lines'][:MAX_LINES]:
        c.setFillColor(muted)
        c.setFont('Helvetica-Bold', 4.5)
        c.drawString(FIELD_X * mm, B(yy), _trim(label, 14))
        c.setFillColor(ink)
        c.setFont('Helvetica', 5.4)
        c.drawString((FIELD_X + 16) * mm, B(yy), _trim(value, 30))
        yy += FIELD_STEP

    # ── QR (pointage) ──
    qx, qtop, qs = QR
    qbottom = CARD_H_MM - qtop - qs
    c.setFillColor(white)
    c.setStrokeColor(accent)
    c.setLineWidth(0.6)
    c.roundRect((qx - 1) * mm, (qbottom - 1) * mm, (qs + 2) * mm, (qs + 2) * mm,
                1 * mm, fill=1, stroke=1)
    qr_buf = qr_png(badge['qr_payload'], box_size=10, border=1)
    if qr_buf:
        try:
            c.drawImage(
                ImageReader(qr_buf), qx * mm, qbottom * mm,
                width=qs * mm, height=qs * mm, mask='auto',
            )
        except Exception:
            pass
    c.setFillColor(muted)
    c.setFont('Helvetica-Bold', 3.6)
    c.drawCentredString((qx + qs / 2) * mm, B(qtop - 1.6), 'POINTAGE')
    c.setFont('Helvetica', 4.6)
    c.setFillColor(ink)
    c.drawCentredString((qx + qs / 2) * mm, B(qtop + qs + 2.4), _trim(badge['matricule'], 16))

    # ── Pied ──
    c.setFillColor(muted)
    c.setFont('Helvetica', 3.9)
    c.drawString(4 * mm, B(50.6), f"Valable jusqu'au {badge['valid_until_str']}")
    c.setFont('Helvetica-Bold', 4.0)
    c.drawRightString((w - 4) * mm, B(50.6), _trim(f"Dir. {badge['director']}", 26))


def draw_card_pdf(c, student, enrollment, school, y0=0, design_key='official'):
    """Compatibilité : construit le badge élève puis délègue au rendu unifié."""
    badge = build_badge_context(student, 'eleve', school, enrollment, design_key)
    draw_badge_pdf(c, badge, y0)


def render_badge_pdf(badge):
    """PDF d'un seul badge, prêt à être envoyé."""
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(CARD_W_MM * mm, CARD_H_MM * mm))
    draw_badge_pdf(c, badge, y0=0)
    c.showPage()
    c.save()
    buf.seek(0)
    return buf


# ═══════════════════════════════ PNG ════════════════════════════════════════
W_PX, H_PX = 1012, 638


def _px(mm_value):
    return int(round(mm_value * W_PX / CARD_W_MM))


def _font(size, bold=False):
    from PIL import ImageFont
    candidates = [
        'C:/Windows/Fonts/arialbd.ttf' if bold else 'C:/Windows/Fonts/arial.ttf',
        'C:/Windows/Fonts/segoeuib.ttf' if bold else 'C:/Windows/Fonts/segoeui.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold
        else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _fit_photo(path, box_w, box_h):
    from PIL import Image
    if not path:
        return None
    try:
        img = Image.open(path).convert('RGB')
        # recadrage central pour remplir sans déformer
        src_ratio = img.width / img.height
        dst_ratio = box_w / box_h
        if src_ratio > dst_ratio:
            new_w = int(img.height * dst_ratio)
            left = (img.width - new_w) // 2
            img = img.crop((left, 0, left + new_w, img.height))
        else:
            new_h = int(img.width / dst_ratio)
            top = (img.height - new_h) // 2
            img = img.crop((0, top, img.width, top + new_h))
        return img.resize((box_w, box_h), Image.Resampling.LANCZOS)
    except Exception:
        return None


def render_badge_png(badge):
    """PNG haute définition du même badge."""
    from PIL import Image, ImageDraw

    d = badge['design']
    school = badge['school']
    primary = _hex_rgb(d['primary'])
    secondary = _hex_rgb(d['secondary'])
    accent = _hex_rgb(d['accent'])
    ink = _hex_rgb(d['ink'])
    muted = _hex_rgb(d['muted'])
    bg = _hex_rgb(d['bg'])

    card = Image.new('RGB', (W_PX, H_PX), bg)
    dr = ImageDraw.Draw(card)

    # Bande latérale
    dr.rectangle([0, 0, _px(BAND_W), H_PX], fill=_hex_rgb(d['band']))

    # Bandeau
    header_px = _px(HEADER_H)
    dr.rectangle([0, 0, W_PX, header_px], fill=primary)

    f_tiny = _font(13)
    f_school = _font(27, True)
    f_motto = _font(14, True)
    f_title = _font(23, True)
    f_label = _font(13, True)
    f_value = _font(15)
    f_small = _font(12)
    f_micro = _font(11, True)

    y = 10
    for ln in school['left_lines']:
        dr.text((_px(3.4), y), _trim(ln.upper(), 30), fill=(255, 255, 255), font=f_tiny)
        y += 17
    y = 10
    for ln in school['right_lines']:
        text = _trim(ln.upper(), 34)
        tw = dr.textlength(text, font=f_tiny)
        dr.text((W_PX - _px(3.4) - tw, y), text, fill=(255, 255, 255), font=f_tiny)
        y += 17

    name = _trim(school['name'].upper(), 36)
    tw = dr.textlength(name, font=f_school)
    dr.text(((W_PX - tw) / 2, _px(5.6)), name, fill=(255, 255, 255), font=f_school)
    motto = _trim(school['motto'], 48)
    tw = dr.textlength(motto, font=f_motto)
    dr.text(((W_PX - tw) / 2, _px(9.6)), motto, fill=(226, 232, 240), font=f_motto)

    tw = dr.textlength(badge['title'], font=f_title)
    dr.text(((W_PX - tw) / 2, _px(15.2)), badge['title'], fill=secondary, font=f_title)
    dr.line([(_px(4), _px(19.3)), (W_PX - _px(4), _px(19.3))], fill=accent, width=3)

    # Photo
    px, py, pw, ph = PHOTO
    box = (_px(px), _px(py), _px(px + pw), _px(py + ph))
    dr.rounded_rectangle(box, radius=10, outline=accent, width=3,
                         fill=_hex_rgb('#e2e8f0'))
    photo = _fit_photo(badge.get('photo_path'), box[2] - box[0] - 10, box[3] - box[1] - 10)
    if photo:
        card.paste(photo, (box[0] + 5, box[1] + 5))
    else:
        tw = dr.textlength(badge['initials'], font=_font(46, True))
        dr.text((box[0] + (box[2] - box[0] - tw) / 2, box[1] + (box[3] - box[1]) / 2 - 28),
                badge['initials'], fill=muted, font=_font(46, True))

    # Champs
    yy = FIELD_TOP
    for label, value in badge['lines'][:MAX_LINES]:
        dr.text((_px(FIELD_X), _px(yy)), _trim(label, 14), fill=muted, font=f_label)
        dr.text((_px(FIELD_X + 16), _px(yy)), _trim(value, 30), fill=ink, font=f_value)
        yy += FIELD_STEP

    # QR
    qx, qy, qs = QR
    qr_box = (_px(qx - 1), _px(qy - 1), _px(qx + qs + 1), _px(qy + qs + 1))
    dr.rounded_rectangle(qr_box, radius=8, outline=accent, width=2, fill=(255, 255, 255))
    qr_buf = qr_png(badge['qr_payload'], box_size=10, border=1)
    if qr_buf:
        try:
            qr_img = Image.open(qr_buf).convert('RGB')
            qr_img = qr_img.resize((_px(qs), _px(qs)), Image.Resampling.NEAREST)
            card.paste(qr_img, (_px(qx), _px(qy)))
        except Exception:
            pass
    caption = 'POINTAGE'
    tw = dr.textlength(caption, font=f_micro)
    dr.text((_px(qx + qs / 2) - tw / 2, _px(qy - 2.6)), caption, fill=muted, font=f_micro)
    mat = _trim(badge['matricule'], 16)
    tw = dr.textlength(mat, font=f_small)
    dr.text((_px(qx + qs / 2) - tw / 2, _px(qy + qs + 1.4)), mat, fill=ink, font=f_small)

    # Pied
    dr.text((_px(4), _px(50.0)), f"Valable jusqu'au {badge['valid_until_str']}",
            fill=muted, font=f_small)
    dir_txt = _trim(f"Dir. {badge['director']}", 26)
    tw = dr.textlength(dir_txt, font=f_small)
    dr.text((W_PX - _px(4) - tw, _px(50.0)), dir_txt, fill=muted, font=f_small)

    out = BytesIO()
    card.save(out, format='PNG', optimize=True)
    out.seek(0)
    return out


def render_card_png(student, enrollment, school, design_key='official'):
    """Compatibilité ascendante : PNG d'un badge élève."""
    return render_badge_png(build_badge_context(student, 'eleve', school, enrollment, design_key))
