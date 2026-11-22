# -*- coding: utf-8 -*-
"""Moteur de rendu des badges (élèves ET personnel) — format CR80 85,6 × 54 mm.

Le modèle « officiel » reproduit la maquette vert & or :
  en-tête vert avec logo circulaire + nom d'école + « CARTE SCOLAIRE »,
  corps clair avec photo, nom, 3 champs et QR, pied vert avec mention et cachet.

HTML (templates/core/badge.html), PNG et PDF partagent la même géométrie.
"""
from io import BytesIO

from core.badge import (
    CARD_H_MM, CARD_W_MM, build_badge_context,
    parents_pair as _parents_pair,  # compatibilité ascendante
)
from core.qr import qr_png


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


def _geometry():
    """Repères en millimètres, mesurés depuis le HAUT de la carte."""
    return {
        'pad': 3.4,
        'header_h': 11.0,
        'footer_h': 5.0,
        'logo_d': 7.2,
        'logo_top': 1.9,
        'name_x': 25.25,
        'name_top': 17.6,
        'photo_x': 3.4, 'photo_top': 14.9, 'photo_w': 18.0, 'photo_h': 22.3,
        'qr_x': 66.4, 'qr_top': 14.9, 'qr_size': 15.8,
        'fields_top': 24.0, 'fields_step': 7.0,
        'footer_text_top': 52.1,
    }


# ═══════════════════════════════ PDF ════════════════════════════════════════
def draw_badge_pdf(c, badge, y0=0):
    from reportlab.lib.units import mm
    from reportlab.lib.utils import ImageReader
    from reportlab.lib.colors import HexColor, white

    g = _geometry()
    d = badge['design']
    school = badge['school']
    w, h = CARD_W_MM, CARD_H_MM

    def Y(top):
        return y0 + (h - top) * mm

    primary = HexColor(d['primary'])
    accent = HexColor(d['accent'])
    ink = HexColor(d['ink'])
    muted = HexColor(d['muted'])

    # Fond
    c.setFillColor(HexColor(d['bg']))
    c.rect(0, y0, w * mm, h * mm, fill=1, stroke=0)

    # ── En-tête ──
    c.setFillColor(primary)
    c.rect(0, Y(g['header_h']), w * mm, g['header_h'] * mm, fill=1, stroke=0)

    lx, ld, lt = g['pad'], g['logo_d'], g['logo_top']
    cx, cy, radius = (lx + ld / 2) * mm, Y(lt + ld / 2), (ld / 2) * mm
    logo_drawn = False
    if school.get('logo_path'):
        try:
            c.saveState()
            path = c.beginPath()
            path.circle(cx, cy, radius - 0.2 * mm)
            c.clipPath(path, stroke=0, fill=0)
            c.setFillColor(white)
            c.rect(cx - radius, cy - radius, 2 * radius, 2 * radius, fill=1, stroke=0)
            c.drawImage(ImageReader(school['logo_path']),
                        cx - radius, cy - radius, width=2 * radius, height=2 * radius,
                        preserveAspectRatio=True, anchor='c', mask='auto')
            c.restoreState()
            logo_drawn = True
        except Exception:
            logo_drawn = False
    c.setStrokeColor(accent)
    c.setLineWidth(0.55)
    c.circle(cx, cy, radius, fill=0, stroke=1)
    if not logo_drawn:
        c.setFillColor(accent)
        c.setFont('Helvetica-Bold', 4.5)
        c.drawCentredString(cx, Y(lt + ld / 2 + 1.4), 'LOGO')

    tx = lx + ld + 1.9
    c.setFillColor(white)
    c.setFont('Helvetica-Bold', 11.2)
    c.drawString(tx * mm, Y(4.9), _trim(school['name'].upper(), 30))
    c.setFont('Helvetica', 5.4)
    c.setFillColor(HexColor('#e5e7eb'))
    c.drawString(tx * mm, Y(8.5), _trim(f"[{school.get('place') or ''}]", 34))

    c.setFont('Helvetica-Bold', 9.6)
    c.setFillColor(accent)
    c.drawRightString((w - g['pad']) * mm, Y(4.9), _trim(badge['title'], 22))
    c.setFont('Helvetica', 5.4)
    c.setFillColor(HexColor('#e5e7eb'))
    c.drawRightString((w - g['pad']) * mm, Y(8.5),
                      _trim(f"Année scolaire {badge['year_label']}", 28))

    # ── Photo ──
    px, ptop, pw, ph = g['photo_x'], g['photo_top'], g['photo_w'], g['photo_h']
    c.setFillColor(HexColor(d.get('photo_bg', '#e7eee9')))
    c.setStrokeColor(HexColor('#d8e2da'))
    c.setLineWidth(0.4)
    c.roundRect(px * mm, Y(ptop + ph), pw * mm, ph * mm, 2 * mm, fill=1, stroke=1)
    photo_drawn = False
    if badge.get('photo_path'):
        try:
            c.drawImage(ImageReader(badge['photo_path']),
                        px * mm + 0.6 * mm, Y(ptop + ph) + 0.6 * mm,
                        width=(pw - 1.2) * mm, height=(ph - 1.2) * mm,
                        preserveAspectRatio=True, anchor='c', mask='auto')
            photo_drawn = True
        except Exception:
            photo_drawn = False
    if not photo_drawn:
        c.setStrokeColor(HexColor('#6b8a78'))
        c.setLineWidth(0.7)
        cx, cy = (px + pw / 2) * mm, Y(ptop + ph / 2 + 1.5)
        c.circle(cx, cy + 2.2 * mm, 2.1 * mm, fill=0, stroke=1)
        c.setLineWidth(0.7)
        c.arc(cx - 3.3 * mm, cy - 1.6 * mm, cx + 3.3 * mm, cy + 1.6 * mm, 180, 180)
        c.setFillColor(HexColor('#6b8a78'))
        c.setFont('Helvetica-Bold', 4.5)
        c.drawCentredString(cx, cy - 2.6 * mm, 'PHOTO')

    # ── Nom + champs ──
    nx = g['name_x']
    c.setFillColor(ink)
    c.setFont('Helvetica-Bold', 13.5)
    c.drawString(nx * mm, Y(g['name_top']),
                 _trim(f"{badge['first_name']} {badge['last_name']}", 28))

    ftop = g['fields_top']
    for label, value in badge['main_fields']:
        c.setFillColor(accent)
        c.setFont('Helvetica-Bold', 4.6)
        c.drawString(nx * mm, Y(ftop), _trim(label.upper(), 18))
        c.setFillColor(ink)
        c.setFont('Helvetica-Bold', 8.2)
        c.drawString(nx * mm, Y(ftop + 3.9), _trim(value, 26))
        ftop += g['fields_step']

    # ── QR ──
    qx, qtop, qs = g['qr_x'], g['qr_top'], g['qr_size']
    c.setFillColor(white)
    c.setStrokeColor(HexColor('#d1d5db'))
    c.setLineWidth(0.4)
    c.roundRect(qx * mm, Y(qtop + qs), qs * mm, qs * mm, 1.4 * mm, fill=1, stroke=1)
    qr_buf = qr_png(badge['qr_payload'], box_size=10, border=1)
    if qr_buf:
        try:
            c.drawImage(ImageReader(qr_buf), (qx + 0.5) * mm, Y(qtop + qs) + 0.5 * mm,
                        width=(qs - 1) * mm, height=(qs - 1) * mm, mask='auto')
        except Exception:
            pass
    c.setFillColor(muted)
    c.setFont('Helvetica', 4.4)
    c.drawCentredString((qx + qs / 2) * mm, Y(qtop + qs + 2.3), 'Scanner pour')
    c.drawCentredString((qx + qs / 2) * mm, Y(qtop + qs + 4.5), 'vérifier la carte')

    # ── Pied ──
    fy = h - g['footer_h']
    c.setFillColor(primary)
    c.rect(0, y0, w * mm, g['footer_h'] * mm, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont('Helvetica', 5.0)
    c.drawString(g['pad'] * mm, Y(g['footer_text_top']),
                 'Cette carte est personnelle et doit être présentée à l’entrée.')
    if school.get('stamp_path'):
        try:
            c.drawImage(ImageReader(school['stamp_path']),
                        (w - g['pad'] - 11) * mm, Y(h - 0.6),
                        width=5.5 * mm, height=4.5 * mm,
                        preserveAspectRatio=True, anchor='c', mask='auto')
        except Exception:
            pass
    c.setFillColor(accent)
    c.setFont('Helvetica-Bold', 5.0)
    c.drawRightString((w - g['pad']) * mm, Y(g['footer_text_top']),
                      'Cachet de la direction')


def draw_card_pdf(c, student, enrollment, school, y0=0, design_key='official'):
    """Compatibilité : construit le badge élève puis délègue au rendu unifié."""
    draw_badge_pdf(c, build_badge_context(student, 'eleve', school, enrollment, design_key), y0)


def render_badge_pdf(badge):
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
        return img.resize((max(1, new_w), max(1, new_h)), Image.Resampling.LANCZOS)
    except Exception:
        return None


def render_badge_png(badge):
    from PIL import Image, ImageDraw

    g = _geometry()
    d = badge['design']
    school = badge['school']
    primary = _hex_rgb(d['primary'])
    accent = _hex_rgb(d['accent'])
    ink = _hex_rgb(d['ink'])
    muted = _hex_rgb(d['muted'])
    photo_bg = _hex_rgb(d.get('photo_bg', '#e7eee9'))

    card = Image.new('RGB', (W_PX, H_PX), _hex_rgb(d['bg']))
    dr = ImageDraw.Draw(card)

    # En-tête
    dr.rectangle([0, 0, W_PX, _px(g['header_h'])], fill=primary)
    from PIL import Image as PILImage
    lx, ld, lt = g['pad'], g['logo_d'], g['logo_top']
    dpx = _px(ld)
    logo = _fit_image(school.get('logo_path'), dpx, dpx, contain=True)
    if logo:
        # Découpage circulaire sur fond blanc, cerclé d'or (comme la maquette).
        disc = PILImage.new('RGBA', (dpx, dpx), (255, 255, 255, 255))
        disc.alpha_composite(logo)
        mask = PILImage.new('L', (dpx, dpx), 0)
        PILImageDraw = __import__('PIL.ImageDraw', fromlist=['Draw']).Draw
        PILImageDraw(mask).ellipse((0, 0, dpx, dpx), fill=255)
        card.paste(disc, (_px(lx), _px(lt)), mask)
    dr.ellipse([_px(lx), _px(lt), _px(lx + ld), _px(lt + ld)],
               outline=accent, width=max(2, _px(0.45)))
    f_logo = _font(15, True)
    if not logo:
        tw = dr.textlength('LOGO', font=f_logo)
        dr.text((_px(lx + ld / 2) - tw / 2, _px(lt + ld / 2) - 9),
                'LOGO', fill=accent, font=f_logo)

    tx = _px(lx + ld + 1.9)
    name = _trim(school['name'].upper(), 30)
    f_name = _font(34, True)
    dr.text((tx, _px(2.9)), name, fill=(255, 255, 255), font=f_name)
    f_place = _font(17)
    dr.text((tx, _px(7.3)), _trim(f"[{school.get('place') or ''}]", 34),
            fill=(229, 231, 235), font=f_place)

    right = W_PX - _px(g['pad'])
    f_title = _font(29, True)
    title = _trim(badge['title'], 22)
    tw = dr.textlength(title, font=f_title)
    dr.text((right - tw, _px(2.6)), title, fill=accent, font=f_title)
    year_txt = _trim(f"Année scolaire {badge['year_label']}", 28)
    f_year = _font(16)
    tw = dr.textlength(year_txt, font=f_year)
    dr.text((right - tw, _px(7.3)), year_txt, fill=(229, 231, 235), font=f_year)

    # Photo
    px, ptop, pw, ph = g['photo_x'], g['photo_top'], g['photo_w'], g['photo_h']
    box = [_px(px), _px(ptop), _px(px + pw), _px(ptop + ph)]
    dr.rounded_rectangle(box, radius=_px(2), fill=photo_bg,
                         outline=_hex_rgb('#d8e2da'), width=2)
    photo = _fit_image(badge.get('photo_path'), box[2] - box[0] - 8, box[3] - box[1] - 8)
    if photo:
        card.paste(photo, (box[0] + 4, box[1] + 4))
    else:
        cx = (box[0] + box[2]) / 2
        cy = (box[1] + box[3]) / 2 - 18
        stroke = _hex_rgb('#6b8a78')
        dr.ellipse([cx - 26, cy - 26, cx + 26, cy + 26], outline=stroke, width=4)
        dr.arc([cx - 42, cy + 12, cx + 42, cy + 60], 180, 360, fill=stroke, width=4)
        f_ph = _font(15, True)
        tw = dr.textlength('PHOTO', font=f_ph)
        dr.text((cx - tw / 2, cy + 46), 'PHOTO', fill=stroke, font=f_ph)

    # Nom + champs
    nx = _px(g['name_x'])
    f_main = _font(38, True)
    dr.text((nx, _px(14.6)),
            _trim(f"{badge['first_name']} {badge['last_name']}", 28), fill=ink, font=f_main)
    f_lab = _font(15, True)
    f_val = _font(25, True)
    ftop = g['fields_top']
    for label, value in badge['main_fields']:
        dr.text((nx, _px(ftop)), _trim(label.upper(), 18), fill=accent, font=f_lab)
        dr.text((nx, _px(ftop + 3.4)), _trim(value, 26), fill=ink, font=f_val)
        ftop += g['fields_step']

    # QR
    qx, qtop, qs = g['qr_x'], g['qr_top'], g['qr_size']
    qr_box = [_px(qx), _px(qtop), _px(qx + qs), _px(qtop + qs)]
    dr.rounded_rectangle(qr_box, radius=10, fill=(255, 255, 255),
                         outline=_hex_rgb('#d1d5db'), width=2)
    qr_buf = qr_png(badge['qr_payload'], box_size=10, border=1)
    if qr_buf:
        from PIL import Image as PILImage
        qr_img = PILImage.open(qr_buf).convert('RGB')
        qr_img = qr_img.resize((qr_box[2] - qr_box[0] - 12, qr_box[3] - qr_box[1] - 12),
                               PILImage.Resampling.NEAREST)
        card.paste(qr_img, (qr_box[0] + 6, qr_box[1] + 6))
    f_cap = _font(13)
    cx = (qr_box[0] + qr_box[2]) / 2
    for i, line in enumerate(('Scanner pour', 'vérifier la carte')):
        tw = dr.textlength(line, font=f_cap)
        dr.text((cx - tw / 2, _px(qtop + qs + 1.6 + i * 2.2)), line, fill=muted, font=f_cap)

    # Pied
    fy = H_PX - _px(g['footer_h'])
    dr.rectangle([0, fy, W_PX, H_PX], fill=primary)
    f_foot = _font(15)
    dr.text((_px(g['pad']), _px(g['footer_text_top'])),
            'Cette carte est personnelle et doit être présentée à l’entrée.',
            fill=(255, 255, 255), font=f_foot)
    f_stamp = _font(15, True)
    txt = 'Cachet de la direction'
    tw = int(round(dr.textlength(txt, font=f_stamp)))
    right_x = W_PX - _px(g['pad'])
    stamp = _fit_image(school.get('stamp_path'), _px(6), _px(6), contain=True)
    if stamp:
        sx = int(right_x - tw - _px(1.6) - stamp.width)
        sy = int(H_PX - _px(g['footer_h']) + (_px(g['footer_h']) - stamp.height) // 2)
        card.paste(stamp, (sx, sy), stamp)
    dr.text((right_x - tw, _px(g['footer_text_top'])), txt, fill=accent, font=f_stamp)

    out = BytesIO()
    card.save(out, format='PNG', optimize=True)
    out.seek(0)
    return out


def render_card_png(student, enrollment, school, design_key='official'):
    return render_badge_png(build_badge_context(student, 'eleve', school, enrollment, design_key))
