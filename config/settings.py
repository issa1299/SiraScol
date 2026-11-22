"""
Django settings — SiraScol
Développement par défaut. Production via variables d'environnement.
"""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

# Charge .env s'il existe (sans dépendance externe)
_env_file = BASE_DIR / '.env'
if _env_file.exists():
    for _line in _env_file.read_text(encoding='utf-8', errors='ignore').splitlines():
        _line = _line.strip()
        if not _line or _line.startswith('#') or '=' not in _line:
            continue
        _k, _, _v = _line.partition('=')
        _k, _v = _k.strip(), _v.strip().strip('"').strip("'")
        if _k and _k not in os.environ:
            os.environ[_k] = _v


# ── Sécurité de base ─────────────────────────────────────────────────────────
# DEBUG=0 ou DEBUG=false en production. Le défaut est SÉCURISÉ (False) :
# le développement doit explicitement définir SIRASCOL_DEBUG=1.
DEBUG = os.environ.get('SIRASCOL_DEBUG', '0').strip().lower() in ('1', 'true', 'yes', 'on')

# En production, une clé secrète explicite est OBLIGATOIRE (anti-falsification
# des sessions et cookies). En développement seulement, une clé locale est
# générée et conservée dans un fichier ignoré par Git.
SECRET_KEY = os.environ.get('SIRASCOL_SECRET_KEY', '').strip()
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured(
            'SIRASCOL_SECRET_KEY doit être défini dans l’environnement en production.'
        )
    from pathlib import Path as _Path
    import secrets as _secrets
    _dev_key_file = BASE_DIR / '.dev_secret_key'
    if _dev_key_file.exists():
        SECRET_KEY = _dev_key_file.read_text(encoding='utf-8').strip()
    if not SECRET_KEY:
        SECRET_KEY = 'django-insecure-' + _secrets.token_urlsafe(50)
        _dev_key_file.write_text(SECRET_KEY, encoding='utf-8')

# Ex: SIRASCOL_ALLOWED_HOSTS=ecole.example.com,www.ecole.example.com
_hosts = os.environ.get('SIRASCOL_ALLOWED_HOSTS', '').strip()
if DEBUG:
    ALLOWED_HOSTS = ['*']
elif _hosts:
    ALLOWED_HOSTS = [h.strip() for h in _hosts.split(',') if h.strip()]
    # Toujours autoriser le local pour tests
    for h in ('localhost', '127.0.0.1'):
        if h not in ALLOWED_HOSTS:
            ALLOWED_HOSTS.append(h)
else:
    ALLOWED_HOSTS = ['localhost', '127.0.0.1']

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'accounts',
    'students',
    'teachers',
    'academics',
    'timetable',
    'grades',
    'attendance',
    'finance',
    'communication',
    'eleve',
    'prof.apps.ProfConfig',
    'parent.apps.ParentConfig',
    'secretariat',
    'comptabilite',
    'classe',
    'surveillant.apps.SurveillantConfig',
    'core.apps.CoreConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'core.middleware.ForcePasswordChangeMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'core.middleware.MaintenanceModeMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.year_context.academic_year_context',
                'core.year_context.permissions_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = os.environ.get('SIRASCOL_TIMEZONE', 'Africa/Bamako')
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'core:dashboard'
LOGOUT_REDIRECT_URL = 'accounts:login'

EMAIL_BACKEND = os.environ.get(
    'SIRASCOL_EMAIL_BACKEND',
    'django.core.mail.backends.console.EmailBackend',
)
DEFAULT_FROM_EMAIL = os.environ.get('SIRASCOL_FROM_EMAIL', 'noreply@sirascol.local')

WEBAUTHN_RP_NAME = 'SiraScol'

# ── Durcissement production (activé si DEBUG=False) ──────────────────────────
if not DEBUG:
    # Production : HTTPS et cookies sécurisés par défaut.
    # SIRASCOL_SSL_REDIRECT=0 / SIRASCOL_SECURE_COOKIES=0 permettent de désactiver
    # explicitement ces réglages derrière un proxy qui termine le TLS.
    def _env_flag(name, default):
        return os.environ.get(name, default).strip().lower() in ('1', 'true', 'yes', 'on')

    SECURE_SSL_REDIRECT = _env_flag('SIRASCOL_SSL_REDIRECT', '1')
    SESSION_COOKIE_SECURE = _env_flag('SIRASCOL_SECURE_COOKIES', '1')
    CSRF_COOKIE_SECURE = _env_flag('SIRASCOL_SECURE_COOKIES', '1')
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    SECURE_REFERRER_POLICY = 'same-origin'
    SECURE_HSTS_SECONDS = int(os.environ.get('SIRASCOL_HSTS_SECONDS', '31536000'))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    if os.environ.get('SIRASCOL_BEHIND_PROXY', '0') in ('1', 'true', 'True'):
        SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# CSRF : origines locales acceptées
CSRF_TRUSTED_ORIGINS = [
    'http://localhost:7000',
    'http://127.0.0.1:7000',
    'http://localhost:8000',
    'http://127.0.0.1:8000',
    'http://localhost:1000',
    'http://127.0.0.1:1000',
]
_extra_csrf = os.environ.get('SIRASCOL_CSRF_ORIGINS', '').strip()
if _extra_csrf:
    CSRF_TRUSTED_ORIGINS += [o.strip() for o in _extra_csrf.split(',') if o.strip()]
# Origines HTTPS PythonAnywhere
for _h in ALLOWED_HOSTS:
    if _h and _h != '*' and 'pythonanywhere.com' in _h:
        _origin = f'https://{_h}'
        if _origin not in CSRF_TRUSTED_ORIGINS:
            CSRF_TRUSTED_ORIGINS.append(_origin)

# Sessions
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False  # Cookie CSRF lisible pour formulaires AJAX
SESSION_COOKIE_AGE = int(os.environ.get('SIRASCOL_SESSION_AGE', str(60 * 60 * 12)))  # 12 h
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

# Dossier de sauvegardes
BACKUP_DIR = BASE_DIR / 'backups'
