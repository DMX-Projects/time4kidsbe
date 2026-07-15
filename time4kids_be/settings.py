import datetime
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables - prioritize .env.local, then .env
ENV_FILE = BASE_DIR / ".env.local"
if not ENV_FILE.exists():
    ENV_FILE = BASE_DIR / ".env"
# override=True so values in .env win over empty shell vars
load_dotenv(ENV_FILE, override=True)

# Environment detection
ENVIRONMENT = os.getenv("DJANGO_ENVIRONMENT", "development").lower()

# Security Settings
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "change-me-in-prod")
DEBUG = os.getenv("DJANGO_DEBUG", "True" if ENVIRONMENT == "development" else "False").lower() == "true"

# Shared secret for /leads/ report pages (query ?key= or X-Landing-Leads-Key header)
LANDING_LEADS_REPORT_KEY = os.getenv("LANDING_LEADS_REPORT_KEY", "").strip()
# TiKES / PLP push enrollment (POST /api/plp/create-enrollment/ with header X-API-Key)
PLP_API_KEY = os.getenv("PLP_API_KEY", "").strip()
if not PLP_API_KEY:
    try:
        from plp_api.plp_api_config import PLP_API_KEY as _PLP_API_KEY_DEFAULT

        PLP_API_KEY = _PLP_API_KEY_DEFAULT
    except ImportError:
        PLP_API_KEY = ""
ALLOWED_HOSTS = [host.strip() for host in os.getenv("DJANGO_ALLOWED_HOSTS", "*").split(",") if host.strip()]

# CORS Configuration
CORS_ALLOW_ALL_ORIGINS = os.getenv("CORS_ALLOW_ALL_ORIGINS", "True" if DEBUG else "False").lower() == "true"
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
    'x-landing-leads-key',
]
CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]
# Let the franchise dashboard read Content-Disposition for download filenames.
CORS_EXPOSE_HEADERS = ["Content-Disposition"]

if not CORS_ALLOW_ALL_ORIGINS:
    CORS_ALLOWED_ORIGINS = [
        origin.strip() for origin in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",") if origin.strip()
    ]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework.authtoken",
    "rest_framework_simplejwt",
    "corsheaders",
    "accounts",
    "users",
    "franchises",
    "events",
    "careers",
    "enquiries",
    "common",
    "updates",
    "gallery",
    "students",
    "documents",
    "plp_api",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "time4kids_be.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "time4kids_be.wsgi.application"

# Database Configuration (PostgreSQL)
# Set DB_HOST, DB_NAME, DB_USER, DB_PASSWORD, DB_PORT in `.env` (or `.env.local`).
# Example live: DB_HOST=103.65.21.176  DB_NAME=time4kids  DB_PASSWORD=...
# Optional: DB_ENGINE=sqlite3 uses a local file DB instead.
DB_ENGINE = os.getenv("DB_ENGINE", "postgresql").lower()

if DB_ENGINE == "postgresql":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("DB_NAME", "time4kids"),
            "USER": os.getenv("DB_USER", "postgres"),
            "PASSWORD": os.getenv("DB_PASSWORD", ""),
            "HOST": os.getenv("DB_HOST", "localhost"),
            "PORT": os.getenv("DB_PORT", "5432"),
            "OPTIONS": {
                "connect_timeout": int(os.getenv("DB_CONNECT_TIMEOUT", "10")),
            },
        }
    }
else:
    # Opt-in SQLite (set DB_ENGINE=sqlite3), e.g. when PostgreSQL is not installed.
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / os.getenv("DB_NAME", "db.sqlite3"),
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Static Files Configuration
STATIC_URL = os.getenv("STATIC_URL", "/static/")
STATIC_ROOT = Path(os.getenv("STATIC_ROOT", str(BASE_DIR / "staticfiles")))

# Static files finders - ensures Django can find static files in installed apps
STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
]

# Additional static files directories (if any)
STATICFILES_DIRS = [
    Path(dir_path) for dir_path in os.getenv("STATICFILES_DIRS", "").split(",") if dir_path.strip()
]

# Media Files Configuration (Local Storage)
MEDIA_URL = os.getenv("MEDIA_URL", "/media/")
MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT", str(BASE_DIR / "media")))

# Legacy centre resource files (old server: /uploads/pc/...).
# Default: <repo-root>/pc/ — copy your Desktop `pc` folder there (see pc/README.md).
_pc_env = os.getenv("PC_DOCUMENTS_ROOT", "").strip()
_default_pc_root = (BASE_DIR.parent / "pc").resolve()
PC_DOCUMENTS_ROOT = Path(_pc_env).expanduser().resolve() if _pc_env else _default_pc_root

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"

# --- Password hashers: plaintext only (`plain$...` or bare literal in DB). See users/hashers.py. ---
PASSWORD_HASHERS = [
    "users.hashers.PlaintextPasswordHasher",
]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "accounts.authentication.LenientJWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_RENDERER_CLASSES": (
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ),
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": datetime.timedelta(minutes=int(os.getenv("JWT_ACCESS_MINUTES", "60"))),
    "REFRESH_TOKEN_LIFETIME": datetime.timedelta(days=int(os.getenv("JWT_REFRESH_DAYS", "30"))),
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# SendGrid — one API key for landing pages, admission/register forms, enquiries, careers, etc.
SENDGRID_API_KEY = (os.getenv("SENDGRID_API_KEY", "") or "").strip()
MAIL_FROM_ADDRESS = (
    os.getenv("MAIL_FROM_ADDRESS", "").strip()
    or os.getenv("SENDGRID_FROM_EMAIL", "").strip()
    or "info@timekidspreschools.com"
)
# Team alerts: admission, landing, register thank-you CC
MAIL_TO_ADDRESS = os.getenv("MAIL_TO_ADDRESS", "info@timekidspreschools.com")
MAIL_LANDING_CC = os.getenv("MAIL_LANDING_CC", "info@timekidspreschools.com")
# Franchise opportunity form — internal alerts only
MAIL_FRANCHISE_TO_ADDRESS = os.getenv("MAIL_FRANCHISE_TO_ADDRESS", "franchise@timekidspreschools.com")
# CRM Direct Contact Email button — From address (must be allowed in SendGrid)
CRM_DIRECT_FROM_EMAIL = (
    os.getenv("CRM_DIRECT_FROM_EMAIL", "").strip()
    or "franchise@timekidspreschools.com"
)

_default_email_backend = (
    "django.core.mail.backends.smtp.EmailBackend"
    if SENDGRID_API_KEY
    else "django.core.mail.backends.console.EmailBackend"
)
EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", _default_email_backend)
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.sendgrid.net")
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "apikey")
EMAIL_HOST_PASSWORD = (os.getenv("EMAIL_HOST_PASSWORD", "") or SENDGRID_API_KEY).strip()
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True").lower() == "true"
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "") or MAIL_FROM_ADDRESS

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "time4kids-default-cache",
    }
}

# Public URL of the Next.js site (for links in parent announcement emails)
PUBLIC_SITE_URL = os.getenv("PUBLIC_SITE_URL", "http://localhost:3000").rstrip("/")

# CSRF Configuration - must include scheme (http:// or https://)
# Next dev may use 3001 if 3000 is busy — include both ports for localhost / 127.0.0.1.
csrf_origins = os.getenv(
    "CSRF_TRUSTED_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001",
)
CSRF_TRUSTED_ORIGINS = [
    origin.strip() 
    for origin in csrf_origins.split(",") 
    if origin.strip() and (origin.strip().startswith("http://") or origin.strip().startswith("https://"))
]

# CSRF Cookie Settings
CSRF_COOKIE_HTTPONLY = False
CSRF_USE_SESSIONS = False
CSRF_COOKIE_SAMESITE = 'Lax'

# Security Settings for Production
if not DEBUG:
    SECURE_SSL_REDIRECT = os.getenv("SECURE_SSL_REDIRECT", "True").lower() == "true"
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "True").lower() == "true"
    CSRF_COOKIE_SECURE = os.getenv("CSRF_COOKIE_SECURE", "True").lower() == "true"
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"

# Logging Configuration
ENABLE_FILE_LOGGING = os.getenv("ENABLE_FILE_LOGGING", "False").lower() == "true"
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": os.getenv("LOG_LEVEL", "INFO"),
    },
}

# Parent app fee payment — UPI QR (scan & pay, then parent taps confirm in app)
PARENT_FEE_UPI_VPA = os.getenv("PARENT_FEE_UPI_VPA", "").strip()
PARENT_FEE_UPI_PAYEE_NAME = os.getenv("PARENT_FEE_UPI_PAYEE_NAME", "T.I.M.E. Kids").strip()
# Optional static QR image URL (e.g. https://yoursite.com/fees/payment-qr.png). If set, shown instead of generated QR.
PARENT_FEE_QR_IMAGE_URL = os.getenv("PARENT_FEE_QR_IMAGE_URL", "").strip()
# When using a static QR image, set the exact amount encoded in that QR (e.g. 1 for ₹1 test payments).
PARENT_FEE_QR_FIXED_AMOUNT = os.getenv("PARENT_FEE_QR_FIXED_AMOUNT", "").strip()

# Add file handler if enabled
if ENABLE_FILE_LOGGING:
    (BASE_DIR / "logs").mkdir(exist_ok=True)
    LOGGING["handlers"]["file"] = {
        "class": "logging.FileHandler",
        "filename": BASE_DIR / "logs" / "django.log",
        "formatter": "verbose",
    }
    LOGGING["root"]["handlers"].append("file")
