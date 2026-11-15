# -*- coding: utf-8 -*-
"""
Carte d'identité scolaire — modèle Mali exact (85,6 × 54 mm).
Bandeau bleu + titre + champs gauche + photo/cachet droite.
"""
from io import BytesIO


def _parents_pair(student):
    """Retourne (père_ou_tuteur, mère) pour Fils/Fille de / Et de."""
    father = mother = None
    try:
        links = list(student.parents.select_related('parent').all())
    except Exception:
        links = []
    for link in links:
        rel = (getattr(link, 'relation', '') or '').lower()
        p = link.parent
        name = f'{p.last_name} {p.first_name}'.strip()
        if rel in ('pere', 'père', 'father') and not father:
            father = name
        elif rel in ('mere', 'mère', 'mother') and not mother:
            mother = name
        elif rel in ('tuteur',) and not father:
            father = name
        elif not father:
            father = name
        elif not mother:
            mother = name
    return father or '—', mother or '—'


def _school_ctx(school):
    name = (school.name if school else 'Établissement scolaire') or 'Établissement scolaire'
    motto = ''
    if school and school.motto:
        motto = school.motto
    else:
        motto = 'TRAVAIL - DISCIPLINE - REUSSITE'

    left_raw = (school.header_left if school and school.header_left else '') or ''
    if not left_raw and school:
        parts = ['M.E.N']
        if getattr(school, 'inspection', None):
            parts.append(school.inspection)
        if getattr(school, 'commune', None) or getattr(school, 'city', None):
            place = school.commune or school.city
            parts.append(f'A.E DE {place}'.upper())
        left_raw = '\n'.join(parts)
    left_lines = [ln.strip() for ln in left_raw.replace('|', '\n').split('\n') if ln.strip()][:3]
    if not left_lines:
        left_lines = ['M.E.N']

    right_raw = (school.header_right if school and school.header_right else '') or ''
    if not right_raw:
        country = (school.country if school and school.country else 'MALI').upper()
        right_raw = f'REPUBLIQUE DU {country}\nUN PEUPLE - UN BUT - UNE FOI'
    right_lines = [ln.strip() for ln in right_raw.replace('|', '\n').split('\n') if ln.strip()][:2]

    director = (school.director_name if school and school.director_name else '') or '—'

    logo_path = None
    stamp_path = None
    if school:
        if school.logo:
            try:
                logo_path = school.logo.path
            except Exception:
                pass
        if school.stamp:
            try:
                stamp_path = school.stamp.path
            except Exception:
                pass

    return {
        'name': name,
        'motto': motto.upper(),
        'left_lines': left_lines,
        'right_lines': right_lines,
        'director': director,
        'logo_path': logo_path,
        'stamp_path': stamp_path,
    }


def draw_card_pdf(c, student, enrollment, school, y0=0):
    """Dessine le recto carte Mali — page 85.6 × 54 mm."""
    from reportlab.lib.units import mm
    from reportlab.lib.utils import ImageReader
    from reportlab.lib.colors import HexColor, Color, white

    w, h = 85.6 * mm, 54 * mm
    ctx = _school_ctx(school)
    father, mother = _parents_pair(student)

    BLUE = HexColor('#1e40af')
    BLUE_TITLE = HexColor('#1d4ed8')
    INK = HexColor('#0f172a')
    GRAY_BG = HexColor('#f1f5f9')

    # Fond
    c.setFillColor(white)
    c.rect(0, y0, w, h, fill=1, stroke=0)

    # ── Bandeau bleu (≈ 15 mm) ──
    banner_h = 15 * mm
    c.setFillColor(BLUE)
    c.rect(0, y0 + h - banner_h, w, banner_h, fill=1, stroke=0)

    # Gauche en-tête
    c.setFillColor(white)
    c.setFont('Helvetica', 4.5)
    ly = y0 + h - 3.5 * mm
    for ln in ctx['left_lines']:
        c.drawString(2.8 * mm, ly, ln[:30].upper())
        ly -= 3.5 * mm

    # Droite en-tête
    c.setFont('Helvetica', 4.5)
    ry = y0 + h - 3.5 * mm
    for ln in ctx['right_lines']:
        c.drawRightString(w - 2.8 * mm, ry, ln[:34].upper())
        ry -= 3.5 * mm

    # Nom école (centré, gras)
    c.setFont('Helvetica-Bold', 9)
    school_name = ctx['name'][:36].upper()
    c.drawCentredString(w / 2, y0 + h - 9 * mm, school_name)

    # Devise
    if ctx['motto']:
        c.setFont('Helvetica-Bold', 5.5)
        c.drawCentredString(w / 2, y0 + h - 12.8 * mm, ctx['motto'][:50])

    # ── Titre ──
    c.setFillColor(BLUE_TITLE)
    c.setFont('Helvetica-Bold', 12)
    c.drawCentredString(w / 2, y0 + h - banner_h - 5.5 * mm, "CARTE D'IDENTITÉ SCOLAIRE")

    # ── Champs ──
    gender = (getattr(student, 'gender', '') or '').upper()
    nee_label = 'Née le :' if gender == 'F' else 'Né le :'
    fils_label = 'Fille de :' if gender == 'F' else 'Fils de :'
    dob = student.date_of_birth.strftime('%d/%m/%Y') if student.date_of_birth else '—'
    classe = str(enrollment.classroom) if enrollment else '—'

    rows = [
        ('Nom :', (student.last_name or '').upper()),
        ('Prénom :', student.first_name or ''),
        ('Classe :', classe),
        (nee_label, dob),
        (fils_label, father),
        ('Et de :', mother),
        ('Directeur :', ctx['director']),
    ]

    # Zone champs : sous le titre jusqu'en bas
    top_fields = y0 + h - banner_h - 10 * mm
    c.setFillColor(INK)
    yy = top_fields
    for label, val in rows:
        c.setFont('Helvetica-Bold', 7.5)
        c.drawString(3.5 * mm, yy, label)
        c.setFont('Helvetica', 7.5)
        c.drawString(26 * mm, yy, (val or '—')[:30])
        yy -= 4.2 * mm

    # ── Photo ──
    pw, ph = 23 * mm, 29 * mm
    px = w - pw - 3.5 * mm
    py = y0 + 6 * mm

    c.setStrokeColor(HexColor('#1e3a8a'))
    c.setLineWidth(1.5)
    c.setFillColor(GRAY_BG)
    c.roundRect(px, py, pw, ph, 1.2 * mm, fill=1, stroke=1)

    photo_drawn = False
    if student.photo:
        try:
            c.drawImage(
                ImageReader(student.photo.path),
                px + 1 * mm, py + 1 * mm,
                width=pw - 2 * mm, height=ph - 2 * mm,
                preserveAspectRatio=True, mask='auto',
            )
            photo_drawn = True
        except Exception:
            pass
    if not photo_drawn:
        c.setFillColor(HexColor('#64748b'))
        c.setFont('Helvetica-Bold', 14)
        init = ((student.last_name or '?')[:1] + (student.first_name or '?')[:1]).upper()
        c.drawCentredString(px + pw / 2, py + ph / 2 - 2 * mm, init)

    # ── Cachet école (image réelle) ──
    stamp_path = ctx.get('stamp_path')
    stamp_size = 14 * mm
    sx = px - 5 * mm
    sy = py - 1 * mm
    if stamp_path:
        try:
            c.drawImage(
                ImageReader(stamp_path),
                sx, sy,
                width=stamp_size, height=stamp_size,
                preserveAspectRatio=True, mask='auto',
            )
        except Exception:
            stamp_path = None
    if not stamp_path:
        # Placeholder discret uniquement si aucun cachet uploadé
        c.setStrokeColor(HexColor('#b91c1c'))
        c.setFillColor(Color(0.85, 0.15, 0.15, alpha=0.08))
        c.setLineWidth(1.2)
        cx = sx + stamp_size / 2
        cy = sy + stamp_size / 2
        c.circle(cx, cy, stamp_size / 2 - 0.5 * mm, fill=1, stroke=1)
        c.setFont('Helvetica', 3.5)
        c.setFillColor(HexColor('#991b1b'))
        c.drawCentredString(cx, cy - 1 * mm, 'CACHET ÉCOLE')


def render_card_png(student, enrollment, school, scale=4):
    """PNG haute résolution du même modèle Mali."""
    from PIL import Image, ImageDraw, ImageFont

    # ~300 dpi CR80
    W, H = 1012, 638
    card = Image.new('RGB', (W, H), (252, 252, 250))
    draw = ImageDraw.Draw(card)

    def font(size, bold=False):
        paths = [
            '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
            'C:/Windows/Fonts/arialbd.ttf' if bold else 'C:/Windows/Fonts/arial.ttf',
            'C:/Windows/Fonts/segoeuib.ttf' if bold else 'C:/Windows/Fonts/segoeui.ttf',
        ]
        for path in paths:
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
        return ImageFont.load_default()

    ctx = _school_ctx(school)
    father, mother = _parents_pair(student)
    BLUE = (30, 64, 175)

    # Bandeau
    banner_h = int(H * 0.28)
    draw.rectangle([0, 0, W, banner_h], fill=BLUE)

    f_tiny = font(13, False)
    f_school = font(30, True)
    f_motto = font(15, True)
    f_title = font(34, True)
    f_lab = font(22, True)
    f_val = font(22, False)

    # Header left
    y = 14
    for ln in ctx['left_lines']:
        draw.text((18, y), ln.upper()[:36], fill=(255, 255, 255), font=f_tiny)
        y += 18

    # Header right
    y = 14
    for ln in ctx['right_lines']:
        text = ln.upper()[:40]
        tw = draw.textlength(text, font=f_tiny)
        draw.text((W - 18 - tw, y), text, fill=(255, 255, 255), font=f_tiny)
        y += 18

    # School name
    name = ctx['name'].upper()[:38]
    tw = draw.textlength(name, font=f_school)
    draw.text(((W - tw) / 2, banner_h // 2 - 24), name, fill=(255, 255, 255), font=f_school)
    if ctx['motto']:
        m = ctx['motto'][:48]
        tw = draw.textlength(m, font=f_motto)
        draw.text(((W - tw) / 2, banner_h // 2 + 14), m, fill=(226, 232, 240), font=f_motto)

    # Title
    title = "CARTE D'IDENTITÉ SCOLAIRE"
    tw = draw.textlength(title, font=f_title)
    draw.text(((W - tw) / 2, banner_h + 16), title, fill=BLUE, font=f_title)

    # Fields
    gender = (getattr(student, 'gender', '') or '').upper()
    nee_label = 'Née le :' if gender == 'F' else 'Né le :'
    fils_label = 'Fille de :' if gender == 'F' else 'Fils de :'
    dob = student.date_of_birth.strftime('%d/%m/%Y') if student.date_of_birth else '—'
    classe = str(enrollment.classroom) if enrollment else '—'
    rows = [
        ('Nom :', (student.last_name or '').upper()),
        ('Prénom :', student.first_name or ''),
        ('Classe :', classe),
        (nee_label, dob),
        (fils_label, father),
        ('Et de :', mother),
        ('Directeur :', ctx['director']),
    ]
    yy = banner_h + 68
    label_w = 170
    for label, val in rows:
        draw.text((28, yy), label, fill=(15, 23, 42), font=f_lab)
        draw.text((28 + label_w, yy), (val or '—')[:32], fill=(30, 41, 59), font=f_val)
        yy += 40

    # Photo
    pw, ph = 230, 290
    px = W - pw - 28
    py = banner_h + 55
    draw.rounded_rectangle([px, py, px + pw, py + ph], radius=10, outline=(30, 58, 138), width=4, fill=(241, 245, 249))

    if student.photo:
        try:
            photo = Image.open(student.photo.path).convert('RGB')
            # crop center to fit
            photo = photo.resize((pw - 12, ph - 12), Image.Resampling.LANCZOS)
            card.paste(photo, (px + 6, py + 6))
        except Exception:
            init = ((student.last_name or '?')[:1] + (student.first_name or '?')[:1]).upper()
            tw = draw.textlength(init, font=font(42, True))
            draw.text((px + (pw - tw) / 2, py + ph // 2 - 20), init, fill=(100, 116, 139), font=font(42, True))
    else:
        init = ((student.last_name or '?')[:1] + (student.first_name or '?')[:1]).upper()
        tw = draw.textlength(init, font=font(42, True))
        draw.text((px + (pw - tw) / 2, py + ph // 2 - 20), init, fill=(100, 116, 139), font=font(42, True))

    # Cachet école
    stamp_path = ctx.get('stamp_path')
    if stamp_path:
        try:
            stamp = Image.open(stamp_path).convert('RGBA')
            stamp.thumbnail((150, 150), Image.Resampling.LANCZOS)
            # position: bas gauche de la photo
            sx = px - 40
            sy = py + ph - 100
            card.paste(stamp, (sx, sy), stamp)
        except Exception:
            stamp_path = None
    if not stamp_path:
        overlay = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        sx, sy, sr = px + 10, py + ph - 30, 58
        od.ellipse([sx - sr, sy - sr, sx + sr, sy + sr], outline=(185, 28, 28, 180), width=3)
        od.ellipse([sx - sr + 10, sy - sr + 10, sx + sr - 10, sy + sr - 10], outline=(185, 28, 28, 140), width=2)
        od.text((sx - 42, sy - 8), 'CACHET ÉCOLE', fill=(153, 27, 27, 200), font=font(12, True))
        card = Image.alpha_composite(card.convert('RGBA'), overlay).convert('RGB')

    out = BytesIO()
    card.save(out, format='PNG', optimize=True)
    out.seek(0)
    return out
