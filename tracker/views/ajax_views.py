# tracker/views/ajax_views.py
import json
import logging

from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, Http404
from django.contrib.contenttypes.models import ContentType
from django.views.decorators.http import require_http_methods

# Modelleri import et
from ..models import Favorite, Anime, Manga, Webtoon, Novel # get_object_or_404 için modellere ihtiyaç var

logger = logging.getLogger(__name__)


# ==============================================================================
# AJAX VIEW'LARI - Orijinal views.py'den taşındı
# ==============================================================================

# Favori Ekle/Çıkar (AJAX - Optimize Edildi)
@login_required
@require_http_methods(["POST"]) # Sadece POST isteklerini kabul et
def toggle_favorite(request):
    """Bir öğeyi favorilere ekler veya çıkarır (AJAX)."""
    try:
        # İstek gövdesinden JSON verisini oku
        data = json.loads(request.body)
        item_type_str = data.get('item_type') # örn: "anime"
        item_id = data.get('item_id') # örn: 123

        # Gerekli parametreler var mı kontrol et
        if not item_type_str or not item_id:
            logger.warning("Toggle Favorite: Eksik parametre (item_type veya item_id).")
            return JsonResponse({'status': 'error', 'message': 'Eksik parametre.'}, status=400)

        # item_type_str'dan ContentType'ı al
        try:
            content_type = ContentType.objects.get(model=item_type_str.lower())
            # ContentType'dan model sınıfını al (get_object_or_404 için gerekli)
            model_class = content_type.model_class()
            if model_class is None: # Eğer model app cache'de yoksa (nadir durum)
                raise ContentType.DoesNotExist
        except ContentType.DoesNotExist:
            logger.warning(f"Toggle Favorite: Geçersiz öğe türü '{item_type_str}'.")
            return JsonResponse({'status': 'error', 'message': 'Geçersiz öğe türü.'}, status=400)

        # İlgili öğe veritabanında var mı kontrol et (model_class gerekli)
        target_item = get_object_or_404(model_class, pk=item_id)
        # Not: get_object_or_404 burada 404 döndürürse, aşağıdaki kod çalışmaz.

        # Favoriyi bul veya oluştur (get_or_create atomik ve verimlidir)
        favorite, created = Favorite.objects.get_or_create(
            user=request.user,
            content_type=content_type,
            object_id=item_id
        )

        if not created:
            # Eğer zaten varsa (created=False), sil
            favorite.delete()
            is_favorite_now = False
            logger.debug(f"Favori kaldırıldı: User {request.user.id}, Type {item_type_str}, ID {item_id}")
        else:
            # Eğer yeni oluşturulduysa (created=True), işlem tamam
            is_favorite_now = True
            logger.debug(f"Favori eklendi: User {request.user.id}, Type {item_type_str}, ID {item_id}")

        # Başarılı yanıtı döndür
        return JsonResponse({'status': 'ok', 'is_favorite': is_favorite_now})

    except json.JSONDecodeError:
        logger.warning("Toggle Favorite: Geçersiz JSON formatı.")
        return JsonResponse({'status': 'error', 'message': 'Geçersiz JSON formatı.'}, status=400)
    except Http404: # get_object_or_404'ten gelen hata
        logger.warning(f"Toggle Favorite: Öğe bulunamadı - Type: {item_type_str}, ID: {item_id}")
        return JsonResponse({'status': 'error', 'message': 'Öğe bulunamadı.'}, status=404)
    except Exception as e:
        # Beklenmedik hataları logla
        logger.error(f"Toggle Favorite Hatası: {e}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': 'Sunucu hatası.'}, status=500)