# -*- coding: utf-8 -*-
"""Moteur de cartes CR80 professionnelles (85,6 × 54 mm, ~300 DPI, 1012 × 638 px).

Génération Recto et Verso haute fidélité pour élèves et personnel :
1. FORMAT : standard CR80 (85,6 × 54 mm), marges de sécurité 3 mm, optimisé PVC.
2. CARTE PERSONNEL : Logo, nom d'établissement, année scolaire, photo uniforme,
   nom & prénom en grand, fonction, service, matricule, QR code élargi.
3. CARTE ÉLÈVE : Logo, nom d'établissement, année scolaire, photo uniforme,
   nom & prénom en grand, matricule, classe, QR code élargi.
4. DESIGN : identité vert foncé, blanc et or. Typographie moderne et soignée,
   hiérarchie visuelle stricte, zéro texte illisible, photos protégées de toute déformation.
5. VERSO PROFESSIONNEL : République du Mali, règlement d'utilisation officiel,
   contact d'urgence ou mention officielle, délivrance, validité, cadre signature/cachet,
   coordonnées complètes de l'établissement.
6. QR & SCANNER : charge utile sécurisée (STU:<matricule> ou TCH:<matricule>),
   pointage immédiat avec affichage de la photo et des données.
7. IMPRESSION : prévisualisation recto/verso, PDF duplex CR80 300 DPI pixel-perfect.
"""
from io import BytesIO

from core.badge import (
    CARD_H_MM, CARD_W_MM, build_badge_context,
    parents_pair as _parents_pair,
)
from core.qr import qr_png, staff_display_code

# ── Grille de référence CR80 (~300 DPI) ───────────────────────────────────────
W_PX, H_PX = 1012, 638
PX_PER_MM = W_PX / CARD_W_MM  # ≈ 11.8224 px/mm

SAFE = 36                     # Marge de sécurité 3 mm (3 × 11.82 ≈ 35.5 px)
HEADER_H = 145                # En-tête vert
FOOTER_H = 80                 # Pied vert
ZONE_TOP = HEADER_H           # 145 px
ZONE_BOTTOM = H_PX - FOOTER_H # 558 px
ZONE_H = ZONE_BOTTOM - ZONE_TOP # 413 px
ZONE_CY = ZONE_TOP + ZONE_H // 2 # 351 px

# En-tête Recto
LOGO_D = 84
LOGO_X = SAFE
LOGO_Y = (HEADER_H - LOGO_D) // 2  # 30 px
SCHOOL_X = SAFE + LOGO_D + 18      # 138 px
RIGHT_X = W_PX - SAFE              # 976 px

# Photo uniforme (ratio standard passeport 4:5)
PHOTO_X = SAFE                     # 36 px
PHOTO_W = 205
PHOTO_H = 256
PHOTO_Y = int(ZONE_CY - PHOTO_H // 2)  # 223 px

# QR Code agrandi (200 × 200 px)
QR_SIZE = 200
QR_X = W_PX - SAFE - QR_SIZE       # 776 px (3 mm de la marge droite)
CAPTION_FS = 12                    # 12 px (8 pt)
CAPTION_GAP = 8                    # 8 px sous le QR
QR_BLOCK_H = QR_SIZE + CAPTION_GAP + 14  # 222 px
QR_Y = int(ZONE_CY - QR_BLOCK_H // 2)    # 240 px
CAPTION_Y = QR_Y + QR_SIZE + CAPTION_GAP # 448 px

# Informations de la personne
NAME_X = PHOTO_X + PHOTO_W + 28    # 269 px
NAME_FS = 32                       # 32 px gras
NAME_GAP = 16                      # 16 px sous le nom
LABEL_FS = 13                      # 13 px gras, étiquette lisible
LABEL_GAP = 4                      # 4 px étiquette → valeur
VALUE_FS = 20                      # 20 px gras
GROUP_GAP = 16                     # 16 px entre les groupes

# Pied de page
FOOTER_TOP = ZONE_BOTTOM           # 558 px
FOOTER_TEXT_Y = FOOTER_TOP + (FOOTER_H - 18) // 2  # 589 px
FOOTER_FS = 16

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
        'C:/Windows/Fonts/segoeuib.ttf' if bold else 'C:/Windows/Fonts/segoeui.ttf',
        'C:/Windows/Fonts/arialbd.ttf' if bold else 'C:/Windows/Fonts/arial.ttf',
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


def _spaced(dr, x, y, text, font, fill, spacing=1.1):
    """Texte avec espacement élégant des lettres."""
    for ch in str(text):
        dr.text((x, y), ch, fill=fill, font=font)
        x += dr.textlength(ch, font=font) + spacing


def _layout_school_name(dr, name, max_w):
    """Calcule le nom d'établissement sur 1 ou 2 lignes de 22 px jusqu'à 14 px.
    Ne tronque jamais avec des points de suspension."""
    name = (name or '').strip()
    if not name:
        return [], 22

    words = name.split()
    # 1 ligne de 22 à 14 px
    for size in range(22, 13, -1):
        f = _font(size, bold=True)
        if dr.textlength(name, font=f) <= max_w:
            return [name], size

    # 2 lignes équilibrées de 22 à 14 px
    for size in range(22, 13, -1):
        f = _font(size, bold=True)
        for i in range(1, len(words)):
            l1 = ' '.join(words[:i])
            l2 = ' '.join(words[i:])
            if dr.textlength(l1, font=f) <= max_w and dr.textlength(l2, font=f) <= max_w:
                return [l1, l2], size

    # Découpe forcée à 14 px
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
    return qr_png(payload, box_size=10, border=3, dark=QR_DARK, light=QR_LIGHT)


# ═══════════════════════════════ RECTO ══════════════════════════════════════
def render_badge_png(badge, side='front'):
    """Génère le PNG haute définition 300 DPI du badge (recto ou verso)."""
    if side in ('back', 'verso'):
        return render_badge_verso_png(badge)

    from PIL import Image, ImageDraw

    d = badge['design']
    school = badge['school']
    primary = _hex_rgb(d['primary'])
    accent = _hex_rgb(d['accent'])
    ink = _hex_rgb(d.get('ink', '#0f172a'))
    label_color = _hex_rgb(d.get('label_color', LABEL_COLOR))
    caption_color = _hex_rgb(d.get('caption', LABEL_COLOR))
    photo_bg = _hex_rgb(d.get('photo_bg', '#e7eee9'))

    card = Image.new('RGB', (W_PX, H_PX), _hex_rgb(d['bg']))
    dr = ImageDraw.Draw(card)

    # ── Filigrane de sécurité discret (fond guilloché) ──
    bg_line = (238, 243, 239)
    for y in range(HEADER_H + 16, FOOTER_TOP, 18):
        dr.line([0, y, W_PX, y], fill=bg_line, width=1)

    # Filigrane circulaire de sécurité au centre
    cx_wm, cy_wm = 540, ZONE_CY
    dr.ellipse([cx_wm - 130, cy_wm - 130, cx_wm + 130, cy_wm + 130], outline=(232, 239, 234), width=2)
    dr.ellipse([cx_wm - 95, cy_wm - 95, cx_wm + 95, cy_wm + 95], outline=(232, 239, 234), width=1)

    # ── En-tête vert avec liseré or ──
    dr.rectangle([0, 0, W_PX, HEADER_H], fill=primary)
    dr.rectangle([0, HEADER_H - 3, W_PX, HEADER_H], fill=accent)

    # Logo officiel dans disque blanc cerclé d'or
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

    # Titre du badge & Année scolaire à droite
    title_font = _font(23 if badge['kind'] == 'personnel' else 26, True)
    tw_title = dr.textlength(badge['title'], font=title_font)
    year_txt = f"Année scolaire {badge['year_label']}"
    year_font = _font(15)
    tw_year = dr.textlength(year_txt, font=year_font)
    right_block_w = max(tw_title, tw_year)

    dr.text((RIGHT_X - tw_title, 46), badge['title'], fill=accent, font=title_font)
    dr.text((RIGHT_X - tw_year, 84), year_txt, fill=(213, 230, 219), font=year_font)

    # Nom complet de l'établissement (sans points de suspension)
    school_max_w = RIGHT_X - right_block_w - 24 - SCHOOL_X
    school_name = school.get('name') or ''
    school_lines, school_fs = _layout_school_name(dr, school_name, school_max_w)
    place_txt = school.get('place') or ''
    line_h = school_fs + 5
    total_brand_h = len(school_lines) * line_h + (18 if place_txt else 0)
    sy = (HEADER_H - total_brand_h) // 2

    f_school = _font(school_fs, bold=True)
    for line in school_lines:
        dr.text((SCHOOL_X, sy), line, fill=(255, 255, 255), font=f_school)
        sy += line_h
    if place_txt:
        dr.text((SCHOOL_X, sy + 2), place_txt, fill=(213, 230, 219), font=_font(15))

    # ── Emplacement Photo uniforme (cadre double or/blanc, centré verticalement) ──
    # Cadre extérieur or
    dr.rounded_rectangle([PHOTO_X - 2, PHOTO_Y - 2, PHOTO_X + PHOTO_W + 2, PHOTO_Y + PHOTO_H + 2],
                         radius=10, outline=accent, width=2)
    # Passe-partout intérieur blanc
    dr.rounded_rectangle([PHOTO_X, PHOTO_Y, PHOTO_X + PHOTO_W, PHOTO_Y + PHOTO_H],
                         radius=8, fill=(255, 255, 255), outline=_hex_rgb('#d8e2da'), width=1)

    photo = _fit_image(badge.get('photo_path'), PHOTO_W - 6, PHOTO_H - 6)
    if photo:
        card.paste(photo, (PHOTO_X + 3, PHOTO_Y + 3))
    else:
        # Silhouette soignée et pleine sur fond doux
        dr.rounded_rectangle([PHOTO_X + 2, PHOTO_Y + 2, PHOTO_X + PHOTO_W - 2, PHOTO_Y + PHOTO_H - 2],
                             radius=7, fill=_hex_rgb('#e8ede9'))
        cx = PHOTO_X + PHOTO_W // 2
        cy = PHOTO_Y + PHOTO_H // 2 - 12
        fill_avatar = _hex_rgb('#789987')
        dr.ellipse([cx - 30, cy - 42, cx + 30, cy + 18], fill=fill_avatar)
        dr.pieslice([cx - 52, cy - 2, cx + 52, cy + 102], 180, 360, fill=fill_avatar)
        # Bandeau officiel au bas de la photo
        dr.rectangle([PHOTO_X + 2, PHOTO_Y + PHOTO_H - 28, PHOTO_X + PHOTO_W - 2, PHOTO_Y + PHOTO_H - 2], fill=primary)
        f_ph = _font(11, True)
        tw = dr.textlength("PHOTO OFFICIELLE", font=f_ph)
        dr.text((cx - tw / 2, PHOTO_Y + PHOTO_H - 22), "PHOTO OFFICIELLE", fill=accent, font=f_ph)

    # ── QR Code de sécurité dans cartouche blanc (3 mm de la marge droite) ──
    qr_card_w = QR_SIZE
    qr_card_h = QR_SIZE + 32
    qr_card_y = int(ZONE_CY - qr_card_h // 2)
    dr.rounded_rectangle([QR_X, qr_card_y, QR_X + qr_card_w, qr_card_y + qr_card_h],
                         radius=10, fill=(255, 255, 255), outline=_hex_rgb('#cbd5e1'), width=1)

    # Mini-bandeau supérieur de contrôle
    dr.rectangle([QR_X + 1, qr_card_y + 1, QR_X + qr_card_w - 1, qr_card_y + 22], fill=primary)
    f_qc = _font(10, True)
    tw_qc = dr.textlength("SÉCURITÉ • SCAN", font=f_qc)
    dr.text((QR_X + (qr_card_w - tw_qc) / 2, qr_card_y + 5), "SÉCURITÉ • SCAN", fill=accent, font=f_qc)

    qr_buf = _qr_buf(badge['qr_payload'])
    if qr_buf:
        from PIL import Image as PILImage
        qr_img = PILImage.open(qr_buf).convert('RGB')
        inner = QR_SIZE - 40
        qr_img = qr_img.resize((inner, inner), PILImage.Resampling.NEAREST)
        card.paste(qr_img, (QR_X + 20, qr_card_y + 30))

    legend = 'Scanner pour vérifier'
    cap_font = _font(11, True)
    cap_w = dr.textlength(legend, font=cap_font)
    cap_x = QR_X + (qr_card_w - cap_w) / 2
    dr.text((cap_x, qr_card_y + qr_card_h - 22), legend, fill=caption_color, font=cap_font)

    # ── Informations (Nom agrandi + Badges structurés, centré verticalement) ──
    full_name = f"{badge['first_name']} {badge['last_name']}".strip()
    info_max_w = QR_X - 24 - NAME_X
    name_size = NAME_FS
    name_font = _font(name_size, True)
    while dr.textlength(full_name, font=name_font) > info_max_w and name_size > 22:
        name_size -= 1
        name_font = _font(name_size, True)

    total_info_h = 190
    info_y = int(ZONE_CY - total_info_h // 2)

    # Nom et prénom de la personne
    dr.text((NAME_X, info_y), full_name, fill=ink, font=name_font)
    # Liseré or élégant sous le nom
    name_tw = min(dr.textlength(full_name, font=name_font) + 40, info_max_w)
    dr.line([NAME_X, info_y + name_size + 8, NAME_X + name_tw, info_y + name_size + 8], fill=accent, width=2)

    top_badges = info_y + name_size + 20

    if badge['kind'] == 'eleve':
        # ── Badges élèves : CLASSE (vert & or) + MATRICULE (blanc & ardoise) ──
        b_w1 = 210
        b_h = 46
        dr.rounded_rectangle([NAME_X, top_badges, NAME_X + b_w1, top_badges + b_h],
                             radius=7, fill=primary, outline=accent, width=2)
        _spaced(dr, NAME_X + 12, top_badges + 6, "CLASSE", _font(10, bold=True), accent)
        classe_val = str(badge.get('classe') or '—')
        dr.text((NAME_X + 12, top_badges + 20), classe_val, fill=(255, 255, 255), font=_font(19, bold=True))

        b_x2 = NAME_X + b_w1 + 16
        b_w2 = min(230, info_max_w - b_w1 - 16)
        dr.rounded_rectangle([b_x2, top_badges, b_x2 + b_w2, top_badges + b_h],
                             radius=7, fill=(255, 255, 255), outline=_hex_rgb('#cbd5e1'), width=2)
        _spaced(dr, b_x2 + 12, top_badges + 6, "N° MATRICULE", _font(10, bold=True), label_color)
        mat_val = str(badge.get('matricule') or '—')
        dr.text((b_x2 + 12, top_badges + 20), mat_val, fill=ink, font=_font(17, bold=True))

        # Ligne 2 : Date de naissance ou Statut
        top_row2 = top_badges + b_h + 16
        dob_val = badge.get('dob_display') or ''
        born_lbl = (badge.get('born_word') or 'NÉ(E) LE').upper()
        if dob_val:
            dr.text((NAME_X, top_row2), f"{born_lbl} :", fill=label_color, font=_font(12, bold=True))
            dr.text((NAME_X + 85, top_row2 - 1), str(dob_val), fill=ink, font=_font(15, bold=True))
        else:
            dr.text((NAME_X, top_row2), "STATUT :", fill=label_color, font=_font(12, bold=True))
            dr.text((NAME_X + 85, top_row2 - 1), "Élève régulier(e)", fill=primary, font=_font(15, bold=True))

        # Ligne 3 : Mention de validité officielle
        top_row3 = top_row2 + 24
        dr.text((NAME_X, top_row3), "VALIDITÉ :", fill=label_color, font=_font(11, bold=True))
        dr.text((NAME_X + 85, top_row3), f"Année scolaire {badge.get('year_label', '2026-2027')}", fill=_hex_rgb('#334155'), font=_font(13))

    else:
        # ── Badges personnel : FONCTION (vert & or) + SERVICE (blanc & ardoise) ──
        b_w1 = 210
        b_h = 46
        dr.rounded_rectangle([NAME_X, top_badges, NAME_X + b_w1, top_badges + b_h],
                             radius=7, fill=primary, outline=accent, width=2)
        _spaced(dr, NAME_X + 12, top_badges + 6, "FONCTION", _font(10, bold=True), accent)
        fn_val = str(badge.get('function') or 'Enseignant')
        dr.text((NAME_X + 12, top_badges + 20), fn_val, fill=(255, 255, 255), font=_font(18, bold=True))

        b_x2 = NAME_X + b_w1 + 16
        b_w2 = min(230, info_max_w - b_w1 - 16)
        dr.rounded_rectangle([b_x2, top_badges, b_x2 + b_w2, top_badges + b_h],
                             radius=7, fill=(255, 255, 255), outline=_hex_rgb('#cbd5e1'), width=2)
        _spaced(dr, b_x2 + 12, top_badges + 6, "SERVICE", _font(10, bold=True), label_color)
        srv_val = str(badge.get('service') or 'Pédagogique')
        dr.text((b_x2 + 12, top_badges + 20), srv_val, fill=ink, font=_font(16, bold=True))

        # Ligne 2 : Matricule
        top_row2 = top_badges + b_h + 16
        dr.text((NAME_X, top_row2), "MATRICULE :", fill=label_color, font=_font(12, bold=True))
        dr.text((NAME_X + 95, top_row2 - 1), str(badge.get('matricule', '—')), fill=ink, font=_font(16, bold=True))

        # Ligne 3 : Statut
        top_row3 = top_row2 + 24
        dr.text((NAME_X, top_row3), "STATUT :", fill=label_color, font=_font(11, bold=True))
        dr.text((NAME_X + 95, top_row3), f"Personnel titulaire · Année {badge.get('year_label', '2026-2027')}", fill=_hex_rgb('#334155'), font=_font(13))

    # ── Pied de page avec liseré or ──
    dr.rectangle([0, FOOTER_TOP, W_PX, FOOTER_TOP + 3], fill=accent)
    dr.rectangle([0, FOOTER_TOP + 3, W_PX, H_PX], fill=primary)
    f_foot = _font(14)
    dr.text((SAFE, FOOTER_TEXT_Y),
            "Carte strictement personnelle et incessible • Propriété de l'établissement",
            fill=(255, 255, 255), font=f_foot)
    valid_txt = f"Validité : {badge.get('year_label', '2026-2027')}"
    f_val = _font(14, True)
    tw_val = dr.textlength(valid_txt, font=f_val)
    dr.text((RIGHT_X - tw_val, FOOTER_TEXT_Y), valid_txt, fill=accent, font=f_val)

    out = BytesIO()
    card.save(out, format='PNG', optimize=True, dpi=(300, 300))
    out.seek(0)
    return out


# ═══════════════════════════════ VERSO ══════════════════════════════════════
def render_badge_verso_png(badge):
    """Génère le verso officiel CR80 haute définition 300 DPI."""
    from PIL import Image, ImageDraw

    d = badge['design']
    school = badge['school']
    primary = _hex_rgb(d['primary'])
    accent = _hex_rgb(d['accent'])
    ink = _hex_rgb(d.get('ink', '#0f172a'))
    label_color = _hex_rgb(d.get('label_color', LABEL_COLOR))

    card = Image.new('RGB', (W_PX, H_PX), _hex_rgb(d['bg']))
    dr = ImageDraw.Draw(card)

    # ── En-tête vert avec liseré or (105 px) ──
    dr.rectangle([0, 0, W_PX, 105], fill=primary)
    dr.rectangle([0, 102, W_PX, 105], fill=accent)

    # Liseré tricolore discret du drapeau du Mali (vert, or, rouge)
    fl_w = W_PX // 3
    dr.rectangle([0, 105, fl_w, 108], fill=_hex_rgb('#009a44'))
    dr.rectangle([fl_w, 105, fl_w * 2, 108], fill=_hex_rgb('#fed100'))
    dr.rectangle([fl_w * 2, 105, W_PX, 108], fill=_hex_rgb('#ce1126'))

    # Titre officiel centré
    f_rep = _font(22, bold=True)
    rep_txt = 'RÉPUBLIQUE DU MALI'
    tw = dr.textlength(rep_txt, font=f_rep)
    dr.text(((W_PX - tw) / 2, 24), rep_txt, fill=accent, font=f_rep)

    f_motto = _font(14)
    motto_txt = 'Un Peuple - Un But - Une Foi'
    tw = dr.textlength(motto_txt, font=f_motto)
    dr.text(((W_PX - tw) / 2, 58), motto_txt, fill=(255, 255, 255), font=f_motto)

    # ── Zone centrale (Conditions + Renseignements + Validation) ──
    # Section Conditions Générales
    top_cond = 122
    f_sec = _font(14, bold=True)
    dr.text((SAFE, top_cond), "CONDITIONS GÉNÉRALES D'UTILISATION", fill=primary, font=f_sec)
    dr.line([SAFE, top_cond + 20, SAFE + 320, top_cond + 20], fill=accent, width=2)

    rules = [
        "• Cette carte d'identité est strictement personnelle et demeure la propriété de l'école.",
        "• Le titulaire est tenu de la présenter lors de tout contrôle ou accès aux services scolaires.",
        "• En cas de perte, vol ou dégradation, aviser sans délai l'administration de l'établissement.",
        "• Toute personne trouvant cette carte est priée de la déposer auprès de l'établissement.",
    ]
    f_rule = _font(13)
    ry = top_cond + 28
    for r in rules:
        dr.text((SAFE, ry), r, fill=_hex_rgb('#334155'), font=f_rule)
        ry += 20

    # Cadre spécifique selon type (Élève vs Personnel)
    box_y = 232
    box_h = 76
    dr.rounded_rectangle([SAFE, box_y, RIGHT_X, box_y + box_h],
                         radius=8, fill=(255, 255, 255), outline=accent, width=2)

    f_box_t = _font(12, bold=True)
    f_box_v = _font(14, bold=True)
    if badge.get('kind') == 'eleve':
        em_contact = badge.get('emergency_contact')
        if em_contact:
            dr.text((SAFE + 16, box_y + 12), "CONTACT EN CAS D'URGENCE / PARENTS", fill=primary, font=f_box_t)
            dr.text((SAFE + 16, box_y + 38), f"Responsable : {em_contact}", fill=ink, font=f_box_v)
            if badge.get('parent_phone'):
                dr.text((SAFE + 560, box_y + 38), f"Tél. urgence : {badge['parent_phone']}", fill=primary, font=f_box_v)
        else:
            dr.text((SAFE + 16, box_y + 12), "RENSEIGNEMENTS ÉLÈVE & URGENCE", fill=primary, font=f_box_t)
            contact_parts = []
            if badge.get('phone') and badge.get('phone') != '—':
                contact_parts.append(f"Tél. élève : {badge['phone']}")
            if badge.get('address'):
                contact_parts.append(f"Adresse : {badge['address']}")
            contact_str = '  ·  '.join(contact_parts) if contact_parts else 'Élève régulièrement inscrit(e)'
            dr.text((SAFE + 16, box_y + 34), contact_str, fill=ink, font=_font(13, bold=True))
            dr.text((SAFE + 16, box_y + 54), "En cas d'urgence, aviser immédiatement l'administration de l'établissement.", fill=_hex_rgb('#475569'), font=_font(12))
    else:
        dr.text((SAFE + 16, box_y + 12), "MENTION OFFICIELLE DU PERSONNEL", fill=primary, font=f_box_t)
        srv = badge.get('service') or 'Administration & Pédagogie'
        fn = badge.get('function') or 'Enseignant'
        dr.text((SAFE + 16, box_y + 34), f"Fonction : {fn}  ·  Service : {srv}", fill=ink, font=f_box_v)
        dr.text((SAFE + 16, box_y + 54), "En cas d'urgence, aviser immédiatement la direction de l'établissement.", fill=_hex_rgb('#475569'), font=_font(12))

    # Zone Validation & Cachet (y = 328 à 542)
    # Colonne Gauche : Dates & Identifiant de sécurité
    val_y = 330
    dr.text((SAFE, val_y), "DÉLIVRANCE ET CONTRÔLE DE SÉCURITÉ", fill=label_color, font=_font(12, bold=True))
    dr.line([SAFE, val_y + 18, SAFE + 260, val_y + 18], fill=_hex_rgb('#d1d5db'), width=1)

    dr.text((SAFE, val_y + 28), f"Année scolaire : {badge.get('year_label', '2026-2027')}", fill=ink, font=_font(14, bold=True))
    dr.text((SAFE, val_y + 54), f"Date d'émission : {badge.get('issued_str', '—')}", fill=_hex_rgb('#475569'), font=_font(13))
    dr.text((SAFE, val_y + 78), f"Date de validité : 31/08/{str(badge.get('year_label', '2027')).split('-')[-1]}", fill=_hex_rgb('#475569'), font=_font(13))
    dr.text((SAFE, val_y + 104), f"N° de contrôle : {badge.get('matricule', '—')}", fill=primary, font=_font(13, bold=True))

    # Code-barres stylisé de sécurité
    bar_y = val_y + 126
    bar_x = SAFE
    bar_w = 340
    bar_h = 32
    dr.rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + bar_h], fill=(255, 255, 255))
    cur_x = bar_x + 12
    mat_code = str(badge.get('matricule', '') or '0000')
    seed_val = sum(ord(c) for c in mat_code)
    step = 0
    while cur_x < bar_x + bar_w - 12:
        w = 3 if ((step + seed_val) % 4 == 0 or (step * 2) % 7 == 0) else 1
        dr.rectangle([cur_x, bar_y, cur_x + w, bar_y + bar_h], fill=_hex_rgb('#0f172a'))
        cur_x += w + (3 if (step % 2 == 0) else 2)
        step += 1
    # Texte du matricule sous le code-barres
    f_mat = _font(12, bold=True)
    tw_mat = dr.textlength(mat_code, font=f_mat)
    dr.text((bar_x + (bar_w - tw_mat) / 2, bar_y + bar_h + 4), mat_code, fill=_hex_rgb('#0f172a'), font=f_mat)

    # Colonne Droite : Emplacement Cachet et Signature de la direction
    stamp_w, stamp_h = 360, 180
    stamp_x = RIGHT_X - stamp_w
    stamp_top = 328
    dr.rounded_rectangle([stamp_x, stamp_top, stamp_x + stamp_w, stamp_top + stamp_h],
                         radius=10, fill=(255, 255, 255), outline=accent, width=2)
    dr.text((stamp_x + 30, stamp_top + 12), "SIGNATURE & CACHET DE LA DIRECTION", fill=primary, font=_font(12, bold=True))
    dr.text((stamp_x + 130, stamp_top + 34), "La Direction", fill=_hex_rgb('#64748b'), font=_font(13))

    # Tampon officiel si présent
    stamp_img = _fit_image(school.get('stamp_path'), stamp_w - 40, stamp_h - 60, contain=True)
    if stamp_img:
        card.paste(stamp_img, (stamp_x + 20, stamp_top + 50), stamp_img)
    else:
        # Cercle propre symbolisant le tampon et ligne de signature
        cx = stamp_x + stamp_w // 2
        cy = stamp_top + 105
        dr.ellipse([cx - 42, cy - 42, cx + 42, cy + 42], outline=_hex_rgb('#cbd5e1'), width=1)
        dr.text((cx - 22, cy - 8), "Cachet", fill=_hex_rgb('#94a3b8'), font=_font(12, bold=True))
        dr.line([stamp_x + 30, stamp_top + stamp_h - 22, stamp_x + stamp_w - 30, stamp_top + stamp_h - 22],
                fill=_hex_rgb('#cbd5e1'), width=1)

    # ── Pied vert du verso avec coordonnées (80 px) ──
    dr.rectangle([0, FOOTER_TOP, W_PX, FOOTER_TOP + 3], fill=accent)
    dr.rectangle([0, FOOTER_TOP + 3, W_PX, H_PX], fill=primary)

    s_name = school.get('name') or 'Établissement scolaire'
    s_city = school.get('place') or school.get('city') or ''
    s_phone = school.get('phone') or ''
    s_email = school.get('email') or ''

    parts = [s_name]
    if s_city:
        parts.append(s_city)
    contact_p = []
    if s_phone:
        contact_p.append(f"Tél : {s_phone}")
    if s_email:
        contact_p.append(f"Email : {s_email}")

    line1 = ' · '.join(parts)
    line2 = '  |  '.join(contact_p) if contact_p else "Carte officielle d'identification scolaire"

    f_ft1 = _font(14, bold=True)
    tw1 = dr.textlength(line1, font=f_ft1)
    dr.text(((W_PX - tw1) / 2, FOOTER_TOP + 16), line1, fill=(255, 255, 255), font=f_ft1)

    f_ft2 = _font(13)
    tw2 = dr.textlength(line2, font=f_ft2)
    dr.text(((W_PX - tw2) / 2, FOOTER_TOP + 44), line2, fill=accent, font=f_ft2)

    out = BytesIO()
    card.save(out, format='PNG', optimize=True, dpi=(300, 300))
    out.seek(0)
    return out


def render_badge_both_png(badge):
    """Génère une image côte à côte Recto + Verso."""
    from PIL import Image, ImageDraw

    recto_buf = render_badge_png(badge, side='front')
    verso_buf = render_badge_verso_png(badge)

    img_r = Image.open(recto_buf)
    img_v = Image.open(verso_buf)

    pad = 30
    title_h = 50
    w = W_PX * 2 + pad * 3
    h = H_PX + pad * 2 + title_h

    combined = Image.new('RGB', (w, h), (241, 245, 249))
    dr = ImageDraw.Draw(combined)
    f_t = _font(24, bold=True)

    dr.text((pad, 16), "FACE AVANT (RECTO)", fill=_hex_rgb('#0c4a37'), font=f_t)
    dr.text((pad * 2 + W_PX, 16), "FACE ARRIÈRE (VERSO)", fill=_hex_rgb('#0c4a37'), font=f_t)

    combined.paste(img_r, (pad, pad + title_h))
    combined.paste(img_v, (pad * 2 + W_PX, pad + title_h))

    out = BytesIO()
    combined.save(out, format='PNG', optimize=True, dpi=(300, 300))
    out.seek(0)
    return out


def render_card_png(student, enrollment, school, design_key='official', side='front'):
    b = build_badge_context(student, 'eleve', school, enrollment, design_key)
    if side == 'both':
        return render_badge_both_png(b)
    elif side in ('back', 'verso'):
        return render_badge_verso_png(b)
    return render_badge_png(b)


# ═══════════════════════════════ PDF DUPLEX ══════════════════════════════════
def draw_badge_pdf(c, badge, y0=0, side='front'):
    """Dessine le recto ou le verso sur le canvas ReportLab au format 85,6 × 54 mm."""
    from reportlab.lib.units import mm as mm_unit
    from reportlab.lib.utils import ImageReader

    w_pt, h_pt = CARD_W_MM * mm_unit, CARD_H_MM * mm_unit
    png_buf = render_badge_verso_png(badge) if side in ('back', 'verso') else render_badge_png(badge)
    c.drawImage(ImageReader(png_buf), 0, y0, width=w_pt, height=h_pt)


def draw_card_pdf(c, student, enrollment, school, y0=0, design_key='official'):
    b = build_badge_context(student, 'eleve', school, enrollment, design_key)
    draw_badge_pdf(c, b, y0=y0, side='front')


def render_badge_pdf(badge, duplex=True):
    """PDF CR80 (85,6 × 54 mm) haute définition : Page 1 Recto, Page 2 Verso."""
    from reportlab.lib.units import mm as mm_unit
    from reportlab.pdfgen import canvas
    buf = BytesIO()
    w_pt, h_pt = CARD_W_MM * mm_unit, CARD_H_MM * mm_unit
    c = canvas.Canvas(buf, pagesize=(w_pt, h_pt))

    # Page 1 : Recto
    draw_badge_pdf(c, badge, y0=0, side='front')
    c.showPage()

    # Page 2 : Verso (si duplex demandé)
    if duplex:
        draw_badge_pdf(c, badge, y0=0, side='back')
        c.showPage()

    c.save()
    buf.seek(0)
    return buf
