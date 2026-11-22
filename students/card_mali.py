# -*- coding: utf-8 -*-
"""Cartes CR80 — grille unique 1012 × 638 px (~300 dpi), 85,6 × 54 mm.

Le même modèle (vert & or) est rendu en PNG, PDF et HTML avec les mêmes
positions : marges de sécurité 36 px, pied de page complet, étiquettes
gris foncé espacées, légende QR sur une ligne.
"""
from io import BytesIO

from core.badge import (
    CARD_H_MM, CARD_W_MM, build_badge_context,
    parents_pair as _parents_pair,  # compatibilité ascendante
)
from core.qr import qr_png

# ── Grille de référence ──────────────────────────────────────────────────────
W_PX, H_PX = 1012, 638
PX_PER_MM = W_PX / CARD_W_MM  # ≈ 11.82

SAFE = 36                     # marge de sécurité (≈ 3 mm)
HEADER_H = 150
LOGO_D, LOGO_X, LOGO_Y = 82, SAFE, 32
SCHOOL_X = SAFE + LOGO_D + 20
SCHOOL_NAME_Y, SCHOOL_NAME_FS = 42, 40
PLACE_Y, PLACE_FS = 88, 20
RIGHT_X = W_PX - SAFE
TITLE_Y, TITLE_FS = 45, 34
YEAR_Y, YEAR_FS = 88, 19

PHOTO_X, PHOTO_Y, PHOTO_W, PHOTO_H = SAFE, 182, 200, 250
NAME_X, NAME_Y, NAME_FS = SAFE + PHOTO_W + 28, 180, 48

FIELDS_X = NAME_X
FIELDS_TOP = 292
LABEL_FS, VALUE_FS = 15, 30
LABEL_GAP = 4                 # écart étiquette → valeur
GROUP_GAP = 20                # écart entre deux groupes
PITCH = LABEL_FS + LABEL_GAP + VALUE_FS + GROUP_GAP  # 69 px

QR_SIZE = 190
QR_X = W_PX - SAFE - QR_SIZE
QR_Y = 170
CAPTION_Y = QR_Y + QR_SIZE + 14
CAPTION_FS = 15

FOOTER_H = 80
FOOTER_TOP = H_PX - FOOTER_H
FOOTER_TEXT_Y = 584           # → ~37 px de marge en bas
FOOTER_FS = 17

LABEL_COLOR = '#4f5f54'
QR_DARK = '#000000'
QR_LIGHT = '#ffffff'


def mm(px):
    """Conversion px -> mm pour le PDF."""
    return px / PX_PER_MM


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


def _fit_image(path, box_w, box_h, contain=False):
    from PIL import Image
    if not path:
        return None
    try:
        img = Image.open(path).convert('RGBA')
        src_ratio = img.width / img.height
        dst_ratio = box_w / box_h
        if contain:
            if src_ratio > dst_ratio:
                new_w, new_h = box_w, int(box_w / src_ratio)
            else:
                new_w, new_h = int(box_h * src_ratio), box_h
        else:
            if src_ratio > dst_ratio:
                new_w = int(img.height * dst_ratio)
                left = (img.width - new_w) // 2
                img = img.crop((left, 0, left + new_w, img.height))
            else:
                new_h = int(img.width / dst_ratio)
                top = (img.height - new_h) // 2
                img = img.crop((0, top, img.width, top + new_h))
            new_w, new_h = box_w, box_h
        return img.resize((max(1, int(new_w)), max(1, int(new_h))),
                          Image.Resampling.LANCZOS)
    except Exception:
        return None


def _spaced(dr, x, y, text, font, fill, spacing=1.4):
    """Texte avec léger espacement des lettres (PIL n'a pas letter-spacing)."""
    for ch in str(text):
        dr.text((x, y), ch, fill=fill, font=font)
        x += dr.textlength(ch, font=font) + spacing


def _qr_buf(payload):
    return qr_png(payload, box_size=10, border=4, dark=QR_DARK, light=QR_LIGHT)


# ═══════════════════════════════ PNG ════════════════════════════════════════
def render_badge_png(badge):
    from PIL import Image, ImageDraw

    d = badge['design']
    school = badge['school']
    primary = _hex_rgb(d['primary'])
    accent = _hex_rgb(d['accent'])
    ink = _hex_rgb(d['ink'])
    label_color = _hex_rgb(d.get('label', LABEL_COLOR))
    caption_color = _hex_rgb(d.get('caption', LABEL_COLOR))
    photo_bg = _hex_rgb(d.get('photo_bg', '#e7eee9'))

    card = Image.new('RGB', (W_PX, H_PX), _hex_rgb(d['bg']))
    dr = ImageDraw.Draw(card)

    # ── En-tête ──
    dr.rectangle([0, 0, W_PX, HEADER_H], fill=primary)

    logo = _fit_image(school.get('logo_path'), LOGO_D, LOGO_D, contain=True)
    if logo:
        disc = Image.new('RGBA', (LOGO_D, LOGO_D), (255, 255, 255, 255))
        disc.alpha_composite(logo)
        mask = Image.new('L', (LOGO_D, LOGO_D), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, LOGO_D, LOGO_D), fill=255)
        card.paste(disc, (LOGO_X, LOGO_Y), mask)
    dr.ellipse([LOGO_X, LOGO_Y, LOGO_X + LOGO_D, LOGO_Y + LOGO_D],
               outline=accent, width=3)
    if not logo:
        f_logo = _font(15, True)
        tw = dr.textlength('LOGO', font=f_logo)
        dr.text((LOGO_X + (LOGO_D - tw) / 2, LOGO_Y + LOGO_D / 2 - 9),
                'LOGO', fill=accent, font=f_logo)

    if school.get('name'):
        dr.text((SCHOOL_X, SCHOOL_NAME_Y), _trim(school['name'], 32),
                fill=(255, 255, 255), font=_font(SCHOOL_NAME_FS, True))
    if school.get('place'):
        dr.text((SCHOOL_X, PLACE_Y), _trim(school['place'], 32),
                fill=(229, 231, 235), font=_font(PLACE_FS))

    title_font = _font(TITLE_FS, True)
    tw = dr.textlength(badge['title'], font=title_font)
    dr.text((RIGHT_X - tw, TITLE_Y), badge['title'], fill=accent, font=title_font)
    year_txt = f"Année scolaire {badge['year_label']}"
    year_font = _font(YEAR_FS)
    tw = dr.textlength(year_txt, font=year_font)
    dr.text((RIGHT_X - tw, YEAR_Y), year_txt, fill=(229, 231, 235), font=year_font)

    # ── Photo ──
    dr.rounded_rectangle([PHOTO_X, PHOTO_Y, PHOTO_X + PHOTO_W, PHOTO_Y + PHOTO_H],
                         radius=10, fill=photo_bg, outline=_hex_rgb('#d8e2da'), width=2)
    photo = _fit_image(badge.get('photo_path'), PHOTO_W - 10, PHOTO_H - 10)
    if photo:
        card.paste(photo, (PHOTO_X + 5, PHOTO_Y + 5))
    else:
        cx = PHOTO_X + PHOTO_W / 2
        cy = PHOTO_Y + PHOTO_H / 2 - 18
        stroke = _hex_rgb('#6b8a78')
        dr.ellipse([cx - 26, cy - 26, cx + 26, cy + 26], outline=stroke, width=4)
        dr.arc([cx - 42, cy + 12, cx + 42, cy + 60], 180, 360, fill=stroke, width=4)
        f_ph = _font(15, True)
        tw = dr.textlength('PHOTO', font=f_ph)
        dr.text((cx - tw / 2, cy + 46), 'PHOTO', fill=stroke, font=f_ph)

    # ── Nom + champs ──
    dr.text((NAME_X, NAME_Y),
            _trim(f"{badge['first_name']} {badge['last_name']}", 26),
            fill=ink, font=_font(NAME_FS, True))

    fl = _font(LABEL_FS, True)
    fv = _font(VALUE_FS, True)
    top = FIELDS_TOP
    for label, value in badge['main_fields']:
        _spaced(dr, FIELDS_X, top, label, fl, label_color)
        dr.text((FIELDS_X, top + LABEL_FS + LABEL_GAP),
                _trim(value, 26), fill=ink, font=fv)
        top += PITCH

    # ── QR (zone blanche tout autour, noir sur blanc) ──
    dr.rounded_rectangle([QR_X, QR_Y, QR_X + QR_SIZE, QR_Y + QR_SIZE],
                         radius=12, fill=(255, 255, 255),
                         outline=_hex_rgb('#d1d5db'), width=2)
    qr_buf = _qr_buf(badge['qr_payload'])
    if qr_buf:
        from PIL import Image as PILImage
        qr_img = PILImage.open(qr_buf).convert('RGB')
        inner = QR_SIZE - 16
        qr_img = qr_img.resize((inner, inner), PILImage.Resampling.NEAREST)
        card.paste(qr_img, (QR_X + 8, QR_Y + 8))
    legend = 'Scanner pour vérifier la carte'
    cap_font = _font(CAPTION_FS)
    tw = dr.textlength(legend, font=cap_font)
    dr.text((QR_X + (QR_SIZE - tw) / 2, CAPTION_Y), legend,
            fill=caption_color, font=cap_font)

    # ── Pied de page complet ──
    dr.rectangle([0, FOOTER_TOP, W_PX, H_PX], fill=primary)
    f_foot = _font(FOOTER_FS)
    dr.text((SAFE, FOOTER_TEXT_Y),
            'Cette carte est personnelle et doit être présentée à l’entrée.',
            fill=(255, 255, 255), font=f_foot)
    stamp_txt = 'Cachet de la direction'
    f_stamp = _font(FOOTER_FS, True)
    tw = dr.textlength(stamp_txt, font=f_stamp)
    dr.text((RIGHT_X - tw, FOOTER_TEXT_Y), stamp_txt, fill=accent, font=f_stamp)

    out = BytesIO()
    card.save(out, format='PNG', optimize=True, dpi=(300, 300))
    out.seek(0)
    return out


def render_card_png(student, enrollment, school, design_key='official'):
    return render_badge_png(build_badge_context(student, 'eleve', school, enrollment, design_key))


# ═══════════════════════════════ PDF ════════════════════════════════════════
def draw_badge_pdf(c, badge, y0=0):
    from reportlab.lib.units import mm as mm_unit
    from reportlab.lib.utils import ImageReader
    from reportlab.lib.colors import HexColor, white

    d = badge['design']
    school = badge['school']

    def Y(top_px):
        return y0 + (H_PX - top_px) * mm_unit / PX_PER_MM

    def W(px):
        return px * mm_unit / PX_PER_MM

    primary = HexColor(d['primary'])
    accent = HexColor(d['accent'])
    ink = HexColor(d['ink'])
    label_color = HexColor(d.get('label', LABEL_COLOR))
    caption_color = HexColor(d.get('caption', LABEL_COLOR))

    # Fond + en-tête
    c.setFillColor(HexColor(d['bg']))
    c.rect(0, y0, W(W_PX), W(H_PX), fill=1, stroke=0)
    c.setFillColor(primary)
    c.rect(0, Y(HEADER_H), W(W_PX), W(HEADER_H), fill=1, stroke=0)

    # Logo circulaire unique
    cx, cy, r = W(LOGO_X + LOGO_D / 2), Y(LOGO_Y + LOGO_D / 2), W(LOGO_D / 2)
    logo_drawn = False
    if school.get('logo_path'):
        try:
            c.saveState()
            path = c.beginPath()
            path.circle(cx, cy, r - 1)
            c.clipPath(path, stroke=0, fill=0)
            c.setFillColor(white)
            c.rect(cx - r, cy - r, 2 * r, 2 * r, fill=1, stroke=0)
            c.drawImage(ImageReader(school['logo_path']), cx - r, cy - r,
                        width=2 * r, height=2 * r,
                        preserveAspectRatio=True, anchor='c', mask='auto')
            c.restoreState()
            logo_drawn = True
        except Exception:
            logo_drawn = False
    c.setStrokeColor(accent)
    c.setLineWidth(1.6)
    c.circle(cx, cy, r, fill=0, stroke=1)
    if not logo_drawn:
        c.setFillColor(accent)
        c.setFont('Helvetica-Bold', 7)
        c.drawCentredString(cx, Y(LOGO_Y + LOGO_D / 2 + 2), 'LOGO')

    if school.get('name'):
        c.setFillColor(white)
        c.setFont('Helvetica-Bold', 11)
        c.drawString(W(SCHOOL_X), Y(SCHOOL_NAME_Y), _trim(school['name'], 32))
    if school.get('place'):
        c.setFillColor(HexColor('#e5e7eb'))
        c.setFont('Helvetica', 6)
        c.drawString(W(SCHOOL_X), Y(PLACE_Y), _trim(school['place'], 32))

    c.setFillColor(accent)
    c.setFont('Helvetica-Bold', 9.6)
    c.drawRightString(W(RIGHT_X), Y(TITLE_Y), _trim(badge['title'], 22))
    c.setFillColor(HexColor('#e5e7eb'))
    c.setFont('Helvetica', 5.6)
    c.drawRightString(W(RIGHT_X), Y(YEAR_Y),
                      _trim(f"Année scolaire {badge['year_label']}", 28))

    # Photo
    c.setFillColor(HexColor(d.get('photo_bg', '#e7eee9')))
    c.setStrokeColor(HexColor('#d8e2da'))
    c.setLineWidth(0.8)
    c.roundRect(W(PHOTO_X), Y(PHOTO_Y + PHOTO_H), W(PHOTO_W), W(PHOTO_H),
                W(10), fill=1, stroke=1)
    photo_drawn = False
    if badge.get('photo_path'):
        try:
            c.drawImage(ImageReader(badge['photo_path']),
                        W(PHOTO_X + 5), Y(PHOTO_Y + PHOTO_H) + W(5),
                        width=W(PHOTO_W - 10), height=W(PHOTO_H - 10),
                        preserveAspectRatio=True, anchor='c', mask='auto')
            photo_drawn = True
        except Exception:
            photo_drawn = False
    if not photo_drawn:
        c.setStrokeColor(HexColor('#6b8a78'))
        c.setLineWidth(1.6)
        cx2, cy2 = W(PHOTO_X + PHOTO_W / 2), Y(PHOTO_Y + PHOTO_H / 2 + 3)
        c.circle(cx2, cy2 + W(4), W(5), fill=0, stroke=1)
        c.arc(cx2 - W(8), cy2 - W(3), cx2 + W(8), cy2 + W(3), 180, 180)
        c.setFillColor(HexColor('#6b8a78'))
        c.setFont('Helvetica-Bold', 4.5)
        c.drawCentredString(cx2, cy2 - W(6), 'PHOTO')

    # Nom et champs
    c.setFillColor(ink)
    c.setFont('Helvetica-Bold', 13)
    c.drawString(W(NAME_X), Y(NAME_Y),
                 _trim(f"{badge['first_name']} {badge['last_name']}", 26))

    fl, fv = 4.2, 8.2
    top = FIELDS_TOP
    for label, value in badge['main_fields']:
        c.setFillColor(label_color)
        c.setFont('Helvetica-Bold', fl)
        x = W(FIELDS_X)
        for ch in label.upper():
            c.drawString(x, Y(top), ch)
            x += c.stringWidth(ch, 'Helvetica-Bold', fl) + 0.45
        c.setFillColor(ink)
        c.setFont('Helvetica-Bold', fv)
        c.drawString(W(FIELDS_X), Y(top + LABEL_FS + LABEL_GAP), _trim(value, 26))
        top += PITCH

    # QR
    c.setFillColor(white)
    c.setStrokeColor(HexColor('#d1d5db'))
    c.setLineWidth(0.8)
    c.roundRect(W(QR_X), Y(QR_Y + QR_SIZE), W(QR_SIZE), W(QR_SIZE),
                W(12), fill=1, stroke=1)
    qr_buf = _qr_buf(badge['qr_payload'])
    if qr_buf:
        try:
            inner = QR_SIZE - 16
            c.drawImage(ImageReader(qr_buf), W(QR_X + 8), Y(QR_Y + QR_SIZE) + W(8),
                        width=W(inner), height=W(inner), mask='auto')
        except Exception:
            pass
    c.setFillColor(caption_color)
    c.setFont('Helvetica', 4.3)
    c.drawCentredString(W(QR_X + QR_SIZE / 2), Y(CAPTION_Y),
                        'Scanner pour vérifier la carte')

    # Pied complet — une seule mention, pas de second logo
    c.setFillColor(primary)
    c.rect(0, Y(H_PX), W(W_PX), W(FOOTER_H), fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont('Helvetica', 4.8)
    c.drawString(W(SAFE), Y(FOOTER_TEXT_Y),
                 'Cette carte est personnelle et doit être présentée à l’entrée.')
    c.setFillColor(accent)
    c.setFont('Helvetica-Bold', 4.8)
    c.drawRightString(W(RIGHT_X), Y(FOOTER_TEXT_Y), 'Cachet de la direction')


def draw_card_pdf(c, student, enrollment, school, y0=0, design_key='official'):
    draw_badge_pdf(c, build_badge_context(student, 'eleve', school, enrollment, design_key), y0)


def render_badge_pdf(badge):
    from reportlab.lib.units import mm as mm_unit
    from reportlab.pdfgen import canvas
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(CARD_W_MM * mm_unit, CARD_H_MM * mm_unit))
    draw_badge_pdf(c, badge, y0=0)
    c.showPage()
    c.save()
    buf.seek(0)
    return buf
