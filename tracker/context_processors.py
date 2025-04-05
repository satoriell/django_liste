# tracker/context_processors.py

from .models import Favorite # Favorite modelini import et

def favorites_processor(request):
    """
    Giriş yapmış kullanıcı için toplam favori sayısını hesaplar
    ve template context'ine 'favorite_count' olarak ekler.
    """
    favorite_count = 0
    # Sadece giriş yapmış kullanıcılar için sayıyı hesapla
    if request.user.is_authenticated:
        try:
            # Kullanıcının favori sayısını veritabanından al
            favorite_count = Favorite.objects.filter(user=request.user).count()
        except Exception as e:
            # Olası bir hata durumunda loglama yapılabilir
            # import logging
            # logger = logging.getLogger(__name__)
            # logger.error(f"Favori sayısı alınırken hata oluştu: Kullanıcı={request.user.id}, Hata={e}")
            pass # Hata olsa bile 0 olarak devam et
    # Sözlüğü döndür (her zaman, kullanıcı giriş yapmamışsa count=0 olur)
    return {'favorite_count': favorite_count}