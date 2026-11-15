# -*- coding: utf-8 -*-
"""API WebAuthn : enregistrement & connexion par empreinte / Face ID / Passkey."""
from __future__ import annotations

import json
from datetime import datetime

from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import ensure_csrf_cookie

from .models import WebAuthnCredential
from .webauthn_utils import b64url_encode, b64url_decode, get_rp_id, get_origin, get_rp_name

User = get_user_model()


def _json_body(request):
    try:
        return json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        return {}


def _webauthn_available():
    try:
        import webauthn  # noqa: F401
        return True
    except ImportError:
        return False


# ─── Enregistrement (utilisateur connecté) ───────────────────────────────────

@login_required
@require_POST
def register_begin(request):
    if not _webauthn_available():
        return JsonResponse({'ok': False, 'error': 'Bibliothèque webauthn manquante. Installez: pip install webauthn'}, status=500)

    from webauthn import generate_registration_options, options_to_json
    from webauthn.helpers.structs import (
        AuthenticatorSelectionCriteria,
        ResidentKeyRequirement,
        UserVerificationRequirement,
        AuthenticatorAttachment,
        PublicKeyCredentialDescriptor,
    )

    user = request.user
    existing = list(
        WebAuthnCredential.objects.filter(user=user).values_list('credential_id', flat=True)
    )
    exclude = []
    for cid in existing:
        try:
            exclude.append(PublicKeyCredentialDescriptor(id=b64url_decode(cid)))
        except Exception:
            pass

    opts = generate_registration_options(
        rp_id=get_rp_id(request),
        rp_name=get_rp_name(),
        user_id=str(user.pk).encode('utf-8'),
        user_name=user.username,
        user_display_name=user.get_full_name() or user.username,
        exclude_credentials=exclude or None,
        authenticator_selection=AuthenticatorSelectionCriteria(
            # Capteur du téléphone / PC uniquement → doigt ou visage
            authenticator_attachment=AuthenticatorAttachment.PLATFORM,
            resident_key=ResidentKeyRequirement.REQUIRED,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
        timeout=120000,  # 2 min pour placer le doigt
    )
    request.session['webauthn_reg_challenge'] = b64url_encode(opts.challenge)
    return JsonResponse(json.loads(options_to_json(opts)))


@login_required
@require_POST
def register_complete(request):
    if not _webauthn_available():
        return JsonResponse({'ok': False, 'error': 'webauthn non installé'}, status=500)

    from webauthn import verify_registration_response
    from webauthn.helpers.exceptions import InvalidRegistrationResponse

    body = _json_body(request)
    challenge = request.session.pop('webauthn_reg_challenge', None)
    if not challenge:
        return JsonResponse({'ok': False, 'error': 'Session expirée. Réessayez.'}, status=400)

    try:
        verification = verify_registration_response(
            credential=body,
            expected_challenge=b64url_decode(challenge),
            expected_rp_id=get_rp_id(request),
            expected_origin=get_origin(request),
        )
    except InvalidRegistrationResponse as e:
        return JsonResponse({'ok': False, 'error': f'Vérification échouée: {e}'}, status=400)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)

    cred_id = b64url_encode(verification.credential_id)
    pub_key = b64url_encode(verification.credential_public_key)
    name = (body.get('device_name') or '').strip() or 'Empreinte digitale'

    WebAuthnCredential.objects.update_or_create(
        credential_id=cred_id,
        defaults={
            'user': request.user,
            'public_key': pub_key,
            'sign_count': verification.sign_count,
            'device_name': name[:120],
        },
    )
    return JsonResponse({'ok': True, 'message': 'Empreinte / Passkey enregistrée.'})


# ─── Connexion ───────────────────────────────────────────────────────────────

@require_POST
@ensure_csrf_cookie
def login_begin(request):
    if not _webauthn_available():
        return JsonResponse({'ok': False, 'error': 'webauthn non installé. pip install webauthn'}, status=500)

    from webauthn import generate_authentication_options, options_to_json
    from webauthn.helpers.structs import (
        UserVerificationRequirement,
        PublicKeyCredentialDescriptor,
    )

    body = _json_body(request)
    username = (body.get('username') or '').strip()

    allow = []
    if username:
        try:
            user = User.objects.get(username=username)
            for c in WebAuthnCredential.objects.filter(user=user):
                try:
                    allow.append(PublicKeyCredentialDescriptor(id=b64url_decode(c.credential_id)))
                except Exception:
                    pass
            if not allow:
                return JsonResponse({
                    'ok': False,
                    'error': 'Aucune empreinte enregistrée pour ce compte. Connectez-vous d\'abord avec mot de passe, puis activez l\'empreinte.',
                }, status=400)
        except User.DoesNotExist:
            return JsonResponse({'ok': False, 'error': 'Utilisateur introuvable.'}, status=400)

    opts = generate_authentication_options(
        rp_id=get_rp_id(request),
        allow_credentials=allow or None,  # None = discoverable (passkey sans username)
        user_verification=UserVerificationRequirement.REQUIRED,
    )
    request.session['webauthn_auth_challenge'] = b64url_encode(opts.challenge)
    return JsonResponse(json.loads(options_to_json(opts)))


@require_POST
def login_complete(request):
    if not _webauthn_available():
        return JsonResponse({'ok': False, 'error': 'webauthn non installé'}, status=500)

    from webauthn import verify_authentication_response
    from webauthn.helpers.exceptions import InvalidAuthenticationResponse

    body = _json_body(request)
    challenge = request.session.pop('webauthn_auth_challenge', None)
    if not challenge:
        return JsonResponse({'ok': False, 'error': 'Session expirée. Réessayez.'}, status=400)

    # Récupérer credential_id de la réponse
    raw_id = body.get('id') or body.get('rawId')
    if not raw_id:
        return JsonResponse({'ok': False, 'error': 'Réponse invalide.'}, status=400)

    # id est déjà en base64url
    cred = WebAuthnCredential.objects.filter(credential_id=raw_id).select_related('user').first()
    if not cred:
        # parfois rawId est b64url différent
        try:
            alt = b64url_encode(b64url_decode(raw_id))
            cred = WebAuthnCredential.objects.filter(credential_id=alt).select_related('user').first()
        except Exception:
            pass
    if not cred:
        return JsonResponse({'ok': False, 'error': 'Empreinte non reconnue. Enregistrez-la d\'abord depuis votre compte.'}, status=400)

    try:
        verification = verify_authentication_response(
            credential=body,
            expected_challenge=b64url_decode(challenge),
            expected_rp_id=get_rp_id(request),
            expected_origin=get_origin(request),
            credential_public_key=b64url_decode(cred.public_key),
            credential_current_sign_count=cred.sign_count,
        )
    except InvalidAuthenticationResponse as e:
        return JsonResponse({'ok': False, 'error': f'Échec authentification: {e}'}, status=400)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)

    cred.sign_count = verification.new_sign_count
    cred.last_used_at = timezone.now()
    cred.save(update_fields=['sign_count', 'last_used_at'])

    user = cred.user
    if not user.is_active:
        return JsonResponse({'ok': False, 'error': 'Compte désactivé.'}, status=403)

    login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    return JsonResponse({'ok': True, 'redirect': '/'})


# ─── Gestion ─────────────────────────────────────────────────────────────────

@login_required
@require_GET
def security_page(request):
    creds = WebAuthnCredential.objects.filter(user=request.user)
    return render(request, 'accounts/security.html', {
        'credentials': creds,
        'webauthn_ok': _webauthn_available(),
    })


@login_required
@require_POST
def delete_credential(request, pk):
    WebAuthnCredential.objects.filter(pk=pk, user=request.user).delete()
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'ok': True})
    return redirect('accounts:security')
