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
# django_liste/liste_sitesi/urls.py
"""
URL configuration for liste_sitesi project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings # settings'i import et
import logging # Loglama için logging modülünü ekle

# Logger'ı yapılandır
logger = logging.getLogger(__name__)

urlpatterns = [
    path('admin/', admin.site.urls),
    # Ana URL'ler tracker uygulamasından gelecek
    # '' path'i tracker.urls'e yönlendiriyor (örn: /anime/, /manga/ vb.)
    path('', include('tracker.urls')),

    # Django'nun kimlik doğrulama URL'lerini dahil et
    # (login, logout, password_reset, password_change vb. için)
    # Bu URL'ler /accounts/login/, /accounts/logout/ gibi olacak
    path('accounts/', include('django.contrib.auth.urls')),

    # Not: Kayıt (signup) URL'i tracker.urls içinde tanımlı ('/' altında)
    # Eğer /accounts/signup/ olarak istenirse, tracker/urls.py'den kaldırılıp buraya eklenebilir:
    # from tracker import views as tracker_views
    # path('accounts/signup/', tracker_views.signup_view, name='signup'),
]

# --- YENİ: Debug Toolbar URL'leri (Sadece DEBUG modunda ekle) ---
if settings.DEBUG:
    try:
        import debug_toolbar
        # Debug toolbar URL'lerini ana urlpatterns listesinin başına ekle
        urlpatterns = [
            path('__debug__/', include(debug_toolbar.urls)),
        ] + urlpatterns
        logger.info("Django Debug Toolbar URL'leri başarıyla eklendi.") # Loglama eklenebilir
    except ImportError:
         # debug_toolbar kurulu değilse veya import edilemiyorsa sessizce geç
         # İsteğe bağlı olarak burada bir uyarı loglanabilir
         # logger.warning("Django Debug Toolbar kurulu değil, URL'ler eklenemedi.")
         pass
    except Exception as e:
        # Beklenmedik bir hata olursa logla
        # logger.error(f"Debug Toolbar URL'leri eklenirken hata oluştu: {e}", exc_info=True)
        pass
# ------------------------------------------------------------