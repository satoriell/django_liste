# django_liste/liste_sitesi/settings.py
# liste_sitesi/settings.py

import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-c1s(2#i+l)=)e(=#^$7zva_eq%t$-bp8wpy$n8*iw4u#qojpzx",
)

# DEBUG True olmalı ki Debug Toolbar çalışsın
DEBUG = os.environ.get("DJANGO_DEBUG", "True").lower() == "true"

ALLOWED_HOSTS = []


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # --- Bizim Uygulamalarımız ---
    "tracker",
    # --- Üçüncü Parti Uygulamalar ---
    'taggit',        # Etiketleme için
    'debug_toolbar', # Debugging için
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    # --- YENİ: Debug Toolbar Middleware (CommonMiddleware'den HEMEN SONRA!) ---
    # Sıralama önemli, CommonMiddleware'den sonra, diğerlerinden önce gelmeli.
    "debug_toolbar.middleware.DebugToolbarMiddleware",
    # --------------------------------------------------------------------------
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "liste_sitesi.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        # Ana templates klasörünü DIRS'e ekle (registration şablonları için)
        "DIRS": [BASE_DIR / 'templates'],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                # Favori sayısı context processor'ı
                "tracker.context_processors.favorites_processor",
            ],
        },
    },
]

WSGI_APPLICATION = "liste_sitesi.wsgi.application"


# Database
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}


# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",},
]


# Internationalization
LANGUAGE_CODE = "tr-tr"
TIME_ZONE = "Europe/Istanbul"
USE_I18N = True
USE_TZ = True


# Static files
STATIC_URL = "static/"
# Geliştirme sırasında app'lerin içindeki static dosyaları bulmak için
# STATICFILES_DIRS = [BASE_DIR / "static"] # Genelde APP_DIRS=True yeterli olur
STATIC_ROOT = BASE_DIR / "staticfiles" # Toplanan statik dosyalar (collectstatic)


# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Kimlik Doğrulama Ayarları
LOGIN_URL = 'login' # Default Django login view'ının adı
LOGIN_REDIRECT_URL = 'tracker:dashboard' # Başarılı giriş sonrası yönlendirme
LOGOUT_REDIRECT_URL = 'login' # Başarılı çıkış sonrası yönlendirme

# Session Ayarları (İsteğe bağlı)
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# --- API Ayarları ---
MANGADEX_API_URL = "https://api.mangadex.org"
JIKAN_API_URL = "https://api.jikan.moe/v4"

# --- YENİ: Debug Toolbar Ayarları ---
# DEBUG True ise ve bu IP'lerden birinden istek gelirse Toolbar görünür.
INTERNAL_IPS = [
    "127.0.0.1",
]
# Docker kullanıyorsan veya farklı bir IP'den erişiyorsan burayı ayarlaman gerekebilir.
# Örn: `DEBUG_TOOLBAR_CONFIG = { 'SHOW_TOOLBAR_CALLBACK': lambda request: True }`
# Ama bu güvenlik riski oluşturabilir, dikkatli kullan!
# ----------------------------------

# --- YENİ: Logging Ayarları (Basit Konsol Loglaması) ---
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {asctime} {module}: {message}',
            'style': '{',
             'datefmt': '%Y-%m-%d %H:%M:%S',
        },
    },
    'handlers': {
        'console': {
            'level': 'DEBUG' if DEBUG else 'INFO', # DEBUG modunda daha detaylı log
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        # Opsiyonel: Dosyaya loglama
        # 'file': {
        #     'level': 'INFO',
        #     'class': 'logging.FileHandler',
        #     'filename': BASE_DIR / 'logs/django.log', # logs klasörünün var olduğundan emin ol
        #     'formatter': 'verbose',
        # },
    },
    'loggers': {
        'django': {
            'handlers': ['console'], # DEBUG false ise sadece INFO ve üstü
            'level': 'INFO',
            'propagate': True,
        },
        'tracker': { # Kendi app'imiz için logger
            'handlers': ['console'],
            'level': 'DEBUG' if DEBUG else 'INFO', # DEBUG modunda tüm logları göster
            'propagate': False, # Django logger'ına tekrar gitmesin
        },
         # Diğer kütüphanelerin log seviyelerini ayarlayabilirsiniz
         'requests': {
             'handlers': ['console'],
             'level': 'WARNING', # requests kütüphanesinden sadece uyarı ve hataları göster
             'propagate': False,
         },
         'urllib3': {
             'handlers': ['console'],
             'level': 'WARNING',
             'propagate': False,
         }
    },
}