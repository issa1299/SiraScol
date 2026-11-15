"""
Middleware SiraScol — mode maintenance.
Les staff / superuser / admin / directeur passent toujours.
"""
from django.shortcuts import render


class MaintenanceModeMiddleware:
    """
    Si SchoolSettings.maintenance_mode est actif, toutes les pages
    affichent l'écran de maintenance sauf pour les comptes staff.
    """

    ALLOWED_PREFIXES = (
        '/admin/',
        '/static/',
        '/media/',
        '/accounts/login',
        '/accounts/logout',
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path or '/'
        if any(path.startswith(p) for p in self.ALLOWED_PREFIXES):
            return self.get_response(request)

        user = getattr(request, 'user', None)
        if user is not None and user.is_authenticated:
            if user.is_superuser or user.is_staff:
                return self.get_response(request)
            # Rôles direction
            role = getattr(user, 'role', None) or ''
            if role in ('admin', 'directeur', 'administrator'):
                return self.get_response(request)
            # Profil linked
            try:
                from core.permissions import get_role
                if get_role(user) in ('admin', 'directeur'):
                    return self.get_response(request)
            except Exception:
                pass

        # Vérifier le flag
        try:
            from core.models import SchoolSettings
            school = SchoolSettings.get_solo()
            if school and school.maintenance_mode:
                return render(
                    request,
                    'maintenance.html',
                    {
                        'school': school,
                        'message': getattr(school, 'footer_text', '') or (
                            'SiraScol est temporairement en maintenance. '
                            'Merci de réessayer dans quelques minutes.'
                        ),
                    },
                    status=503,
                )
        except Exception:
            pass

        return self.get_response(request)
