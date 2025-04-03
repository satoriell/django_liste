# liste_sitesi/settings.py

import os # Ortam değişkenleri için
from pathlib import Path
# Geliştirme ortamında .env dosyasını okumak için (opsiyonel, pip install python-dotenv gerekebilir)
# from dotenv import load_dotenv
# load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
# Ortam değişkeninden oku veya geliştirme için varsayılan bir değer ata
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-c1s(2#i+l)=)e(=#^$7zva_eq%t$-bp8wpy$n8*iw4u#qojpzx", # Sadece Geliştirme için!
)

# SECURITY WARNING: don't run with debug turned on in production!
# Ortam değişkeninden oku (varsayılan False), 'True' string'ini boolean True'ya çevir
DEBUG = os.environ.get("DJANGO_DEBUG", "False").lower() == "true"


# Projeye hangi host isimlerinden veya IP adreslerinden erişilebileceği.
# DEBUG = False olduğunda bu listeyi doldurmak zorunludur.
# Örnek: ALLOWED_HOSTS = ['www.example.com', '192.168.1.100']
ALLOWED_HOSTS = []
# DEBUG=True ise veya test çalıştırılıyorsa localhost'a izin ver
if DEBUG or os.environ.get('DJANGO_TESTING') == 'True':
    ALLOWED_HOSTS.extend(['localhost', '127.0.0.1'])


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "tracker",  # Bizim app'imiz
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
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

WSGI_APPLICATION = "liste_sitesi.wsgi.application"


# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}


# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

# GÜNCELLENDİ:
LANGUAGE_CODE = "tr-tr"

# GÜNCELLENDİ:
TIME_ZONE = "Europe/Istanbul"

USE_I18N = True  # Uluslararasılaştırmayı etkinleştirir (True kalmalı)

USE_TZ = True  # Saat dilimi farkındalığını etkinleştirir (True kalmalı)
# USE_L10N = True # Yerel formatları etkinleştirir (Varsayılanı True'dur, açıkça yazmaya gerek yok)


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_URL = "static/"
# `collectstatic` komutunun statik dosyaları toplayacağı dizin
# Üretim ortamında web sunucunuzun (örn. Nginx) bu dizini sunması gerekir.
STATIC_ROOT = BASE_DIR / "staticfiles"


# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Session ayarları (Favoriler session'da tutulduğu için)
# Tarayıcı kapatıldığında session'ın süresinin dolması (varsayılan)
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
# Veya belirli bir süre sonra (örneğin 2 hafta)
# SESSION_COOKIE_AGE = 1209600 # Saniye cinsinden