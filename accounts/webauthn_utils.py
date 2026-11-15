# -*- coding: utf-8 -*-
"""Helpers WebAuthn / Passkeys pour SiraScol."""
from __future__ import annotations

import base64
import json
from typing import Optional

from django.conf import settings


def b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('ascii')


def b64url_decode(data: str) -> bytes:
    pad = '=' * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


def get_rp_id(request) -> str:
    """Identifiant du site (domaine sans port). localhost autorisé en dev."""
    host = request.get_host().split(':')[0]
    if host in ('127.0.0.1', '0.0.0.0'):
        return 'localhost'
    return host


def get_origin(request) -> str:
    scheme = 'https' if request.is_secure() else 'http'
    host = request.get_host()
    # Forcer localhost si IP locale pour compat WebAuthn navigateur
    h = host.split(':')[0]
    if h in ('127.0.0.1', '0.0.0.0'):
        port = host.split(':')[1] if ':' in host else None
        host = f'localhost:{port}' if port else 'localhost'
    return f'{scheme}://{host}'


def get_rp_name() -> str:
    return getattr(settings, 'WEBAUTHN_RP_NAME', 'SiraScol')
