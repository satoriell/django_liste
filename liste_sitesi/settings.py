# liste_sitesi/settings.py

import os # Ortam değişkenleri için
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/ # Django sürümü güncellendi (opsiyonel)

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    # Geliştirme için geçici anahtar, üretimde değiştirilmeli!
    "django-insecure-c1s(2#i+l)=)e(=#^$7zva_eq%t$-bp8wpy$n8*iw4u#qojpzx",
)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get("DJANGO_DEBUG", "True").lower() == "true" # Geliştirme için varsayılan True yapıldı

# ALLOWED_HOSTS boş ise DEBUG=True iken çalışır. DEBUG=False yapınca doldurmak gerekir.
ALLOWED_HOSTS = []


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions", # Session hala mesajlar vb. için kullanılabilir
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "tracker",  # Bizim app'imiz
    'taggit'
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware", # Session hala gerekli
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware", # Kullanıcı kimlik doğrulaması için
    "django.contrib.messages.middleware.MessageMiddleware", # Mesajlar için
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "liste_sitesi.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        # YENİ: Proje genelindeki templates klasörünün yolu
        # BASE_DIR, manage.py'nin olduğu klasördür.
        # /home/admin/App/django_liste/templates yolu BASE_DIR / 'templates' ile aynı olmalı.
        "DIRS": [BASE_DIR / 'templates'],
        "APP_DIRS": True, # Uygulama içindeki (örn: tracker/templates) klasörleri de ara
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth", # user değişkenini şablonlara ekler
                "django.contrib.messages.context_processors.messages", # messages değişkenini şablonlara ekler
                # --- GÜNCELLENDİ ---
                "tracker.context_processors.favorites_processor", # Favori sayısını global olarak ekler
                # --- GÜNCELLEME SONU ---
            ],
        },
    },
]

WSGI_APPLICATION = "liste_sitesi.wsgi.application"


# Database (Aynı kalır)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}


# Password validation (Aynı kalır)
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    { "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", },
    { "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator", },
    { "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator", },
]


# Internationalization (Aynı kalır)
LANGUAGE_CODE = "tr-tr"
TIME_ZONE = "Europe/Istanbul"
USE_I18N = True
USE_TZ = True


# Static files (Aynı kalır)
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles" # collectstatic için


# Default primary key field type (Aynı kalır)
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# YENİ: Kimlik Doğrulama Ayarları
LOGIN_URL = 'login' # @login_required'ın yönlendireceği URL adı
LOGIN_REDIRECT_URL = 'tracker:dashboard' # Başarılı giriş sonrası gidilecek URL adı
LOGOUT_REDIRECT_URL = 'login' # Başarılı çıkış sonrası gidilecek URL adı

# Session Ayarları (Artık favoriler için kullanılmıyor ama mesajlar vb. için kalabilir)
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
# SESSION_COOKIE_AGE = 1209600 # 2 hafta

# --- YENİ: MangaDex API Ayarı ---
MANGADEX_API_URL = "https://api.mangadex.org"
# ---------------------------------