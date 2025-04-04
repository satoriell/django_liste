"""
URL configuration for liste_sitesi project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/ # Django sürümü güncellendi (opsiyonel)
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
# liste_sitesi/urls.py
from django.contrib import admin
from django.urls import path, include # include import edilmiş olmalı

urlpatterns = [
    path('admin/', admin.site.urls),

    # Ana uygulama (tracker) URL'lerini include et (Bu zaten vardı)
    # Projenin kök dizinine gelen istekleri tracker.urls'e yönlendirir
    path('', include('tracker.urls')),

    # YENİ: Django'nun yerleşik kimlik doğrulama view'larını ekle
    # Bu, /accounts/login/, /accounts/logout/ gibi URL'leri otomatik olarak sağlar
    path('accounts/', include('django.contrib.auth.urls')),

    # Not: Kayıt (signup) URL'si tracker.urls içine eklendiği için burada tekrar eklemiyoruz.
]