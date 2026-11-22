# -*- coding: utf-8 -*-
"""Cartes CR80 — grille unique 1012 × 638 px (~300 dpi), 85,6 × 54 mm.

Même géométrie exacte pour PNG, PDF et HTML :
1. NOM DE L'ÉCOLE : pas de troncature, jusqu'à 2 lignes dans l'en-tête,
   réduction automatique de la taille de 22 px jusqu'à 14 px si nécessaire.
   Accents et casse d'origine conservés.
2. HIÉRARCHIE : nom de la personne en 32 px gras (plus grand texte du bloc),
   valeurs en 20 px gras, étiquettes en 13 px (#4F5F54), 16 px sous le nom,
   4 px entre étiquette et valeur, 18 px entre chaque groupe.
   Minuscules sur les particules de noms (de, du, des, la, le, et).
3. QR CODE : placé à droite, à 3 mm de la marge droite (x = 786).
   Légende « Scanner pour vérifier la carte » directement sous le QR code,
   centrée par rapport à lui, avec 8 px d'espace, sur une ligne en 12 px (8 pt) #4F5F54.
4. CENTRAGE VERTICAL : bloc photo + informations + QR code centré verticalement
   dans la zone crème entre l'en-tête (150 px) et le pied (80 px), avec le même
   espace au-dessus et en dessous.
5. PDF IDENTIQUE AU PNG : rendu ReportLab à partir du même rendu graphique 300 DPI,
   taille 85,6 × 54 mm, visuellement 100% identique au PNG sans étiquettes
   plus petites ni légende plus grande.
"""
from io import BytesIO

from core.badge import (
    CARD_H_MM, CARD_W_MM, build_badge_context,
    parents_pair as _parents_pair,
)
from core.qr import qr_png, staff_display_code

# ── Grille de référence ──────────────────────────────────────────────────────
W_PX, H_PX = 1012, 638
PX_PER_MM = W_PX / CARD_W_MM  # ≈ 11.8224

SAFE = 36                     # marge de sécurité (≈ 3 mm)
HEADER_H = 150
FOOTER_H = 80
ZONE_TOP = HEADER_H           # 150 px
ZONE_BOTTOM = H_PX - FOOTER_H # 558 px
ZONE_H = ZONE_BOTTOM - ZONE_TOP # 408 px
ZONE_CY = ZONE_TOP + ZONE_H / 2 # 354 px

# En-tête
LOGO_D = 82
LOGO_X = SAFE
LOGO_Y = (HEADER_H - LOGO_D) // 2  # 34 px
SCHOOL_X = SAFE + LOGO_D + 20      # 138 px
RIGHT_X = W_PX - SAFE              # 976 px

# Photo
PHOTO_X = SAFE                     # 36 px
PHOTO_W = 200
PHOTO_H = 250
PHOTO_Y = int(ZONE_CY - PHOTO_H / 2) # 229 px

# QR Code
QR_SIZE = 190
QR_X = W_PX - SAFE - QR_SIZE       # 786 px (à 3 mm du bord droit)
CAPTION_FS = 12                    # 12 px (8 pt)
CAPTION_GAP = 8                    # 8 px sous le QR
QR_BLOCK_H = QR_SIZE + CAPTION_GAP + 14  # 212 px
QR_Y = int(ZONE_CY - QR_BLOCK_H / 2)    # 248 px
CAPTION_Y = QR_Y + QR_SIZE + CAPTION_GAP # 446 px

# Informations
NAME_X = PHOTO_X + PHOTO_W + 28    # 264 px
NAME_FS = 32                       # 32 px, gras (environ 30 à 34 px)
NAME_GAP = 16                      # 16 px sous le nom
LABEL_FS = 13                      # 13 px
LABEL_GAP = 4                      # 4 px étiquette → valeur
VALUE_FS = 20                      # 20 px, gras
GROUP_GAP = 18                     # 18 px entre chaque groupe

# Pied de page
FOOTER_TOP = ZONE_BOTTOM           # 558 px
FOOTER_TEXT_Y = FOOTER_TOP + (FOOTER_H - 18) // 2  # 589 px
FOOTER_FS = 17

LABEL_COLOR = '#4f5f54'
QR_DARK = '#000000'
QR_LIGHT = '#ffffff'


def mm(px):
    """Conversion px -> mm pour le PDF."""
    return px / PX_PER_MM


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


def _spaced(dr, x, y, text, font, fill, spacing=1.0):
    """Texte avec léger espacement des lettres (PIL n'a pas letter-spacing)."""
    for ch in str(text):
        dr.text((x, y), ch, fill=fill, font=font)
        x += dr.textlength(ch, font=font) + spacing


def _layout_school_name(dr, name, max_w):
    """Calcule les lignes et la taille de police pour le nom de l'école.
    Autorise jusqu'à 2 lignes, réduit la taille de police de 22 px jusqu'à 14 px.
    Ne tronque jamais avec des points de suspension."""
    name = (name or '').strip()
    if not name:
        return [], 22

    words = name.split()
    # 1. Tenter sur 1 ligne de 22 à 14 px
    for size in range(22, 13, -1):
        f = _font(size, bold=True)
        if dr.textlength(name, font=f) <= max_w:
            return [name], size

    # 2. Tenter sur 2 lignes de 22 à 14 px
    for size in range(22, 13, -1):
        f = _font(size, bold=True)
        for i in range(1, len(words)):
            l1 = ' '.join(words[:i])
            l2 = ' '.join(words[i:])
            if dr.textlength(l1, font=f) <= max_w and dr.textlength(l2, font=f) <= max_w:
                return [l1, l2], size

    # 3. Forcer 14 px avec découpe sur 2 lignes
    f = _font(14, bold=True)
    l1, l2 = '', ''
    for w in words:
        candidate = f"{l1} {w}".strip()
        if dr.textlength(candidate, font=f) <= max_w and not l2:
            l1 = candidate
        else:
            l2 = f"{l2} {w}".strip()
    return ([l1, l2] if l2 else [l1]), 14


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
    label_color = _hex_rgb(d.get('label_color', LABEL_COLOR))
    caption_color = _hex_rgb(d.get('caption', LABEL_COLOR))
    photo_bg = _hex_rgb(d.get('photo_bg', '#e7eee9'))

    card = Image.new('RGB', (W_PX, H_PX), _hex_rgb(d['bg']))
    dr = ImageDraw.Draw(card)

    # ── En-tête ──
    dr.rectangle([0, 0, W_PX, HEADER_H], fill=primary)

    # Logo
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

    # Bloc titre & année à droite
    title_font = _font(24 if badge['kind'] == 'personnel' else 30, True)
    tw_title = dr.textlength(badge['title'], font=title_font)
    year_txt = f"Année scolaire {badge['year_label']}"
    year_font = _font(16)
    tw_year = dr.textlength(year_txt, font=year_font)
    right_block_w = max(tw_title, tw_year)

    dr.text((RIGHT_X - tw_title, 48), badge['title'], fill=accent, font=title_font)
    dr.text((RIGHT_X - tw_year, 84), year_txt, fill=(213, 230, 219), font=year_font)

    # Nom de l'école (1 ou 2 lignes, jusqu'à 14 px, sans troncature)
    school_max_w = RIGHT_X - right_block_w - 24 - SCHOOL_X
    school_name = school.get('name') or ''
    school_lines, school_fs = _layout_school_name(dr, school_name, school_max_w)
    place_txt = school.get('place') or ''
    line_h = school_fs + 5
    total_brand_h = len(school_lines) * line_h + (20 if place_txt else 0)
    sy = (HEADER_H - total_brand_h) // 2

    f_school = _font(school_fs, bold=True)
    for line in school_lines:
        dr.text((SCHOOL_X, sy), line, fill=(255, 255, 255), font=f_school)
        sy += line_h
    if place_txt:
        dr.text((SCHOOL_X, sy + 2), place_txt, fill=(213, 230, 219), font=_font(16))

    # ── Photo (centrée verticalement dans la zone crème) ──
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

    # ── QR Code + Légende (à 3 mm de la marge droite, centré verticalement) ──
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
    cap_w = dr.textlength(legend, font=cap_font)
    cap_x = QR_X + (QR_SIZE - cap_w) / 2
    dr.text((cap_x, CAPTION_Y), legend, fill=caption_color, font=cap_font)

    # ── Informations : nom + champs (centré verticalement dans la zone crème) ──
    full_name = f"{badge['first_name']} {badge['last_name']}"
    info_max_w = QR_X - 24 - NAME_X
    name_size = NAME_FS
    name_font = _font(name_size, True)
    while dr.textlength(full_name, font=name_font) > info_max_w and name_size > 22:
        name_size -= 1
        name_font = _font(name_size, True)

    valid_fields = [(l, v) for l, v in badge.get('main_fields', []) if v]
    name_h = name_size + 2
    field_h = LABEL_FS + LABEL_GAP + VALUE_FS + 2
    fields_total_h = (len(valid_fields) * field_h +
                      max(0, len(valid_fields) - 1) * GROUP_GAP) if valid_fields else 0
    total_info_h = name_h + (NAME_GAP + fields_total_h if valid_fields else 0)

    info_y = int(ZONE_CY - total_info_h / 2)

    dr.text((NAME_X, info_y), full_name, fill=ink, font=name_font)

    fl = _font(LABEL_FS, bold=True)
    fv = _font(VALUE_FS, bold=True)
    top = info_y + name_h + NAME_GAP
    for label, value in valid_fields:
        _spaced(dr, NAME_X, top, str(label).upper(), fl, label_color, spacing=1.1)
        dr.text((NAME_X, top + LABEL_FS + LABEL_GAP), str(value), fill=ink, font=fv)
        top += field_h + GROUP_GAP

    # ── Pied de page ──
    dr.rectangle([0, FOOTER_TOP, W_PX, H_PX], fill=primary)
    f_foot = _font(FOOTER_FS)
    dr.text((SAFE, FOOTER_TEXT_Y),
            "Cette carte est personnelle et doit être présentée à l'entrée.",
            fill=(255, 255, 255), font=f_foot)
    stamp_txt = 'Cachet de la direction'
    f_stamp = _font(FOOTER_FS, True)
    tw_stamp = dr.textlength(stamp_txt, font=f_stamp)
    dr.text((RIGHT_X - tw_stamp, FOOTER_TEXT_Y), stamp_txt, fill=accent, font=f_stamp)

    out = BytesIO()
    card.save(out, format='PNG', optimize=True, dpi=(300, 300))
    out.seek(0)
    return out


def render_card_png(student, enrollment, school, design_key='official'):
    return render_badge_png(build_badge_context(student, 'eleve', school, enrollment, design_key))


# ═══════════════════════════════ PDF ════════════════════════════════════════
def draw_badge_pdf(c, badge, y0=0):
    """Rendu PDF strictement identique au PNG (taille 85,6 × 54 mm, 300 DPI)."""
    from reportlab.lib.units import mm as mm_unit
    from reportlab.lib.utils import ImageReader

    w_pt, h_pt = CARD_W_MM * mm_unit, CARD_H_MM * mm_unit
    png_buf = render_badge_png(badge)
    c.drawImage(ImageReader(png_buf), 0, y0, width=w_pt, height=h_pt)


def draw_card_pdf(c, student, enrollment, school, y0=0, design_key='official'):
    draw_badge_pdf(c, build_badge_context(student, 'eleve', school, enrollment, design_key), y0)


def render_badge_pdf(badge):
    """PDF CR80 (85,6 × 54 mm) strictement identique au PNG."""
    from reportlab.lib.units import mm as mm_unit
    from reportlab.pdfgen import canvas
    buf = BytesIO()
    w_pt, h_pt = CARD_W_MM * mm_unit, CARD_H_MM * mm_unit
    c = canvas.Canvas(buf, pagesize=(w_pt, h_pt))
    draw_badge_pdf(c, badge, y0=0)
    c.showPage()
    c.save()
    buf.seek(0)
    return buf
