import os
from dotenv import load_dotenv

load_dotenv()


from pathlib import Path
from datetime import timedelta

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/6.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = str(os.getenv("SECRET_KEY"))
#'django-insecure-%x&y+3a-nl5)%(=!iti0(a)3_tm8^4f-xkbmona_a6ny-g*cm$'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party
    "rest_framework",
    "corsheaders",
    "rest_framework_simplejwt.token_blacklist",

    # custom app
    "core",
    "accounts",
    "blog",
    "comments",
    "engagements",
    "notifications",
    "analytics.apps.AnalyticsConfig",
    "django_celery_beat",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Database
# https://docs.djangoproject.com/en/6.1/ref/settings/#databases

# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.sqlite3',
#         'NAME': BASE_DIR / 'db.sqlite3',
#     }
# }

# postgress
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": str(os.getenv("DATABASE_NAME")),
        "USER": str(os.getenv("DATABASE_USER")),
        "PASSWORD": str(os.getenv("DATABASE_PASSWORD")),
        "HOST": str(os.getenv("DATABASE_HOST")),
        "PORT": str(os.getenv("DATABASE_PORT")),
    }
}


# Password validation
# https://docs.djangoproject.com/en/6.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/6.1/topics/i18n/

# LANGUAGE_CODE = 'en-us'

# TIME_ZONE = 'UTC'

# USE_I18N = True

# USE_TZ = True

LANGUAGE_CODE = "en-us"

TIME_ZONE = "Africa/Lagos"

USE_I18N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.1/howto/static-files/

STATIC_URL = "static/"

STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"

MEDIA_ROOT = BASE_DIR / "media"



# =============================
# EMAIL CONFIGURATION
# =============================
BACKBLOG_REPORT_RECIPIENT = os.getenv(
    "BACKBLOG_REPORT_RECIPIENT",
    "",
).strip()
# Standard Django SMTP Configuration

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_USE_SSL = False
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")

EMAIL_TIMEOUT = 10


DEFAULT_FROM_EMAIL = os.getenv(
    "DEFAULT_FROM_EMAIL",
    "noreply@backblog.local",
)

MAILERS = {
    "default": {
        "BACKEND": "django.core.mail.backends.smtp.EmailBackend",
        "OPTIONS": {
            "host": "smtp.gmail.com",
            "port": 587,
            "use_tls": True,
            "username": os.getenv("EMAIL_HOST_USER"),
            "password": os.getenv("EMAIL_HOST_PASSWORD"),
            "timeout": 10,
        },
    },
}

AUTH_USER_MODEL = "accounts.User"

# ======================
# FRAMEWORKS
# ======================
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.AllowAny",
    ),

    # versioning
    "DEFAULT_VERSIONING_CLASS": "rest_framework.versioning.URLPathVersioning",

    "DEFAULT_VERSION": "v1",

    "ALLOWED_VERSIONS": [
        "v1",
    ],

    # EXCEPTION HANDLING
    "EXCEPTION_HANDLER": "core.exceptions.custom_exception_handler",
}

# ========
# JWT
# ========
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),

    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,

    "AUTH_HEADER_TYPES": ("Bearer",),
}

# ============================================
# REDIS CACHING CONFIGURATION
# ============================================
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379/2",
        "TIMEOUT": 300,
        "KEY_PREFIX": "backblog",
    }
}

# ============================================================
# CELERY & BEAT SCHEDULER CONFIGURATION
# ============================================================

CELERY_BROKER_URL = "redis://127.0.0.1:6379/0"
CELERY_RESULT_BACKEND = "redis://127.0.0.1:6379/1"

CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_ENABLE_UTC = True
# BEAT
CELERY_BEAT_SCHEDULER = "config.celery_scheduler:BackBlogDatabaseScheduler"

# ============================================================
# LOGGING CONFIGURATION
# ============================================================

LOG_DIR = BASE_DIR / "logs"

LOG_DIR.mkdir(exist_ok=True)


LOGGING = {
    "version": 1,

    "disable_existing_loggers": False,

    "formatters": {

        "verbose": {
            "format": (
                "{levelname} "
                "{asctime} "
                "{name} "
                "{message}"
            ),
            "style": "{",
        },

        "simple": {
            "format": (
                "{levelname} "
                "{message}"
            ),
            "style": "{",
        },
    },

    "handlers": {

        # ----------------------------------------------------
        # GENERAL APPLICATION LOG
        # ----------------------------------------------------

        "django_file": {
            "class": "logging.FileHandler",
            "filename": LOG_DIR / "django.log",
            "formatter": "verbose",
        },

        # ----------------------------------------------------
        # ERROR LOG
        # ----------------------------------------------------

        "error_file": {
            "class": "logging.FileHandler",
            "filename": LOG_DIR / "errors.log",
            "formatter": "verbose",
            "level": "ERROR",
        },

        # ----------------------------------------------------
        # CONSOLE
        # ----------------------------------------------------

        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
    },

    "loggers": {

        # ----------------------------------------------------
        # DJANGO
        # ----------------------------------------------------

        "django": {
            "handlers": [
                "console",
                "django_file",
            ],
            "level": "INFO",
            "propagate": False,
        },

        # ----------------------------------------------------
        # BACKBLOG APPLICATION
        # ----------------------------------------------------

        "backblog": {
            "handlers": [
                "console",
                "django_file",
                "error_file",
            ],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# ===============
# CORS
# ===============
CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]
# ===============
# FRONTEND URL
# ===============
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")