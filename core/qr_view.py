# -*- coding: utf-8 -*-
"""Sert les QR codes localement (aucun appel à un service externe)."""
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse

from .qr import qr_png


@login_required
def qr_image(request):
    payload = (request.GET.get('data') or '').strip()[:120]
    if not payload:
        return HttpResponse(status=400)
    box_size = 14 if request.GET.get('size') == '14' else 8
    buf = qr_png(payload, box_size=box_size)
    if not buf:
        return HttpResponse(status=503)  # qrcode non installé
    return HttpResponse(buf.read(), content_type='image/png')
