# -*- coding: utf-8 -*-
"""QR codes LOCAUX des badges — plus aucune dépendance à un service externe.

Les charges utiles sont normalisées pour le scanner de présence :
  - élève     -> STU:<matricule>
  - personnel -> TCH:<matricule>
`attendance.views.scan_qr_api` reconnaît déjà ces deux préfixes et impose le
bon type de pointage, quel que soit l'onglet ouvert sur la page de scan.
"""
from io import BytesIO

KIND_STUDENT = 'STU'
KIND_STAFF = 'TCH'


def badge_payload(kind, code):
    """Retourne la charge utile normalisée d'un badge."""
    matricule = str(code or '').strip()
    prefix = KIND_STAFF if kind in ('teacher', 'staff', 'personnel') else KIND_STUDENT
    return f'{prefix}:{matricule}' if matricule else prefix


def qr_png(payload, box_size=8, border=2, dark='#0f172a', light='#ffffff'):
    """Retourne un BytesIO PNG, ou None si qrcode n'est pas installé."""
    try:
        import qrcode
    except ImportError:
        return None
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(str(payload or ''))
    qr.make(fit=True)
    image = qr.make_image(fill_color=dark, back_color=light).convert('RGB')
    buf = BytesIO()
    image.save(buf, format='PNG')
    buf.seek(0)
    return buf
