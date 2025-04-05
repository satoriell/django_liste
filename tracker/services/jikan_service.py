# tracker/jikan_service.py
# İyileştirmeler: Logging, Hata Yönetimi (404, 429), time.sleep, Ortak Map Fonksiyonu, SFW filtre, .get() kullanımı iyileştirildi.

import requests
import time
import json
import logging
from django.conf import settings
from urllib.parse import urlencode, quote # quote path parametreleri için

# Logger oluştur
logger = logging.getLogger(__name__)

# Jikan API base URL (settings.py'den)
JIKAN_BASE_URL = settings.JIKAN_API_URL

# Opsiyonel: requests.Session kullanımı
# session = requests.Session()
# session.headers.update({
#     'User-Agent': 'DjangoListeApp/0.1 (Contact: YourEmail@example.com)' # E-postanı güncelle
# })

# Genel Jikan istek fonksiyonu (Logging, Hata Yönetimi, Rate Limit ile güncellendi)
def _make_jikan_request(endpoint, params=None):
    """Jikan API'na güvenli GET isteği yapar. Hata veya bulunamazsa None döner."""
    safe_endpoint = "/".join([quote(part, safe='') for part in endpoint.split('/')])
    url = f"{JIKAN_BASE_URL}/{safe_endpoint}"
    headers = {
        'User-Agent': 'DjangoListeApp/0.1 (Contact: YourEmail@example.com)'
    }
    full_url = url
    response_text_snippet = ""
    try:
        time.sleep(0.6) # Jikan rate limit (saniyede ~1.6 istek)

        if params:
            query_string = urlencode(params, doseq=True, safe='[]/:=')
            full_url = f"{url}?{query_string}"

        logger.debug(f"Jikan API İsteği: {full_url}")

        response = requests.get(full_url, headers=headers, timeout=15)
        response_text_snippet = response.text[:500]

        if response.status_code == 404:
            logger.info(f"Jikan API 404 Not Found: {full_url}")
            return None

        if response.status_code == 429:
            logger.warning(f"Jikan API Rate Limit Aşıldı (429) - URL: {full_url}")
            return None

        response.raise_for_status()

        json_response = response.json()

        is_search_endpoint = ("anime" in endpoint or "manga" in endpoint) and params and 'q' in params
        if 'data' not in json_response:
            if not is_search_endpoint:
                 logger.warning(f"Jikan API yanıtında 'data' anahtarı bulunamadı: {full_url}")
                 return None
            else:
                 logger.info(f"Jikan API araması 'data' anahtarı olmadan döndü (boş sonuç varsayılır): {full_url}")
                 return {'data': []}
        elif not json_response['data'] and not is_search_endpoint:
             logger.warning(f"Jikan API yanıtında 'data' boş geldi (detay için): {full_url}")
             return None

        return json_response

    except requests.exceptions.Timeout:
        logger.error(f"Jikan API isteği zaman aşımına uğradı: {full_url}", exc_info=True)
        return None
    except requests.exceptions.HTTPError as http_err:
        status_code = http_err.response.status_code
        logger.error(
            f"Jikan API HTTP Hatası ({status_code}) - URL: {full_url} - Detay: {response_text_snippet}",
            exc_info=False
        )
        return None
    except requests.exceptions.RequestException as req_err:
        logger.error(f"Jikan API Bağlantı/İstek Hatası - URL: {full_url} - Hata: {req_err}", exc_info=True)
        return None
    except json.JSONDecodeError:
         logger.error(
            f"Jikan API JSON Decode Hatası - URL: {full_url} - Yanıt: {response_text_snippet}",
            exc_info=True
        )
         return None
    except Exception as e:
        logger.error(f"Jikan API Genel Hata - URL: {full_url} - Hata: {e}", exc_info=True)
        return None

# --- Anime Fonksiyonları ---
def search_anime(title: str, limit: int = 10):
    """Verilen başlığa göre Jikan API üzerinde anime arar."""
    params = { 'q': title, 'limit': limit, 'sfw': "true" } # SFW filtrelemesi eklendi
    data = _make_jikan_request("anime", params=params)

    if data is None: return None # API hatası
    if not isinstance(data.get('data'), list):
        logger.warning(f"Jikan anime arama yanıtı beklenmedik formatta: title='{title}', yanıt: {str(data)[:200]}")
        return [] # Hatalı format veya boş sonuç

    results = []
    for anime_data in data['data']:
        mal_id = anime_data.get('mal_id')
        if not mal_id: continue

        # Başlık seçimi (daha güvenli)
        title_display = anime_data.get('title') or anime_data.get('title_english') or f"ID: {mal_id}"

        # Resim URL'si (daha güvenli)
        images = anime_data.get('images', {}) or {}
        jpg_images = images.get('jpg', {}) or {}
        image_url = jpg_images.get('large_image_url') # Yoksa None olacak

        synopsis = anime_data.get('synopsis', '') or ''
        synopsis_snippet = (synopsis[:150] + '...') if len(synopsis) > 150 else synopsis

        results.append({
            'mal_id': mal_id,
            'title': title_display,
            'image_url': image_url,
            'type': anime_data.get('type'), # None olabilir
            'episodes': anime_data.get('episodes'), # None olabilir
            'score': anime_data.get('score'), # None olabilir
            'status': anime_data.get('status'), # None olabilir
            'synopsis_snippet': synopsis_snippet
        })
    return results

def get_anime_details(mal_id: int):
    """Verilen MAL ID'sine sahip animenin detaylarını (/full endpoint'inden) getirir."""
    endpoint = f"anime/{quote(str(mal_id))}/full"
    data = _make_jikan_request(endpoint)

    if data is None or not isinstance(data.get('data'), dict):
         logger.warning(f"Jikan anime detayları alınamadı veya format hatalı: MAL ID {mal_id}")
         return None

    return map_jikan_media_data_to_dict(data['data'], 'anime')

# --- Novel Fonksiyonları ---
def search_novel(title: str, limit: int = 10):
    """Verilen başlığa göre Jikan API üzerinde light novel arar."""
    params = { 'q': title, 'limit': limit, 'type': 'lightnovel', 'sfw': "true" }
    data = _make_jikan_request("manga", params=params) # manga endpoint

    if data is None: return None
    if not isinstance(data.get('data'), list):
        logger.warning(f"Jikan novel arama yanıtı beklenmedik formatta: title='{title}', yanıt: {str(data)[:200]}")
        return []

    results = []
    for manga_data in data['data']: # Gelen veri manga formatında
        mal_id = manga_data.get('mal_id')
        if not mal_id: continue

        title_display = manga_data.get('title') or manga_data.get('title_english') or f"ID: {mal_id}"

        images = manga_data.get('images', {}) or {}
        jpg_images = images.get('jpg', {}) or {}
        image_url = jpg_images.get('large_image_url')

        # Yazar(lar)ı güvenli al
        authors_list = manga_data.get('authors', []) or []
        author_names = [
            a.get('name')
            for a in authors_list
            if isinstance(a, dict) and a.get('name')
        ]
        author_str = ", ".join(filter(None, author_names))

        synopsis = manga_data.get('synopsis', '') or ''
        synopsis_snippet = (synopsis[:150] + '...') if len(synopsis) > 150 else synopsis

        results.append({
            'mal_id': mal_id,
            'title': title_display,
            'image_url': image_url,
            'type': manga_data.get('type'), # 'Light Novel'
            'chapters': manga_data.get('chapters'),
            'volumes': manga_data.get('volumes'),
            'score': manga_data.get('score'),
            'status': manga_data.get('status'),
            'author': author_str, # Güvenli alınmış yazar string'i
            'synopsis_snippet': synopsis_snippet
        })
    return results

def get_novel_details(mal_id: int):
    """Verilen MAL ID'sine sahip novelin detaylarını getirir."""
    endpoint = f"manga/{quote(str(mal_id))}/full" # manga endpoint
    data = _make_jikan_request(endpoint)

    if data is None or not isinstance(data.get('data'), dict):
         logger.warning(f"Jikan novel detayları alınamadı veya format hatalı: MAL ID {mal_id}")
         return None

    api_type = data['data'].get('type')
    if api_type != 'Light Novel':
         logger.warning(f"Jikan'dan alınan MAL ID {mal_id} bir Light Novel değil, tipi: {api_type}")
         # return None # İsteğe bağlı: Sadece LN ise devam et

    return map_jikan_media_data_to_dict(data['data'], 'novel')

# --- Ortak Map Fonksiyonu (Anime & Novel Detayları İçin) ---
def map_jikan_media_data_to_dict(jikan_data, media_type):
    """
    Jikan'dan gelen detaylı veriyi (anime veya novel) Django formunu
    doldurmak için ortak bir sözlüğe dönüştürür.
    """
    if not jikan_data or not isinstance(jikan_data, dict):
        logger.error("map_jikan_media_data_to_dict: Geçersiz veya boş jikan_data.")
        return {}

    mal_id = jikan_data.get('mal_id')
    title_display = jikan_data.get('title') or jikan_data.get('title_english') or f"ID: {mal_id}"

    images = jikan_data.get('images', {}) or {}
    jpg_images = images.get('jpg', {}) or {}
    image_url = jpg_images.get('large_image_url')

    synopsis = jikan_data.get('synopsis', '') or '' # Boş string varsayılan
    status_jikan = jikan_data.get('status')
    rating_jikan = jikan_data.get('score')

    # Durum Haritalama
    status_mapped = "Plan to Watch"
    if status_jikan:
        status_lower = status_jikan.lower()
        if "airing" in status_lower or "publishing" in status_lower: status_mapped = "Watching"
        elif "finished" in status_lower: status_mapped = "Completed"
        elif "on hiatus" in status_lower: status_mapped = "On Hold"
        elif "discontinued" in status_lower: status_mapped = "Dropped"

    # Puan Haritalama
    rating_mapped = None
    if rating_jikan is not None:
        try:
            rating_float = float(rating_jikan)
            if 0 <= rating_float <= 10: rating_mapped = int(round(rating_float))
            else: logger.warning(f"Jikan puanı ({rating_jikan}) 0-10 aralığı dışında. MAL ID: {mal_id}")
        except (ValueError, TypeError):
             logger.warning(f"Jikan puanı ({rating_jikan}) sayıya dönüştürülemedi. MAL ID: {mal_id}")

    # Form için temel haritalanmış veri
    mapped_data = {
        'mal_id': mal_id,
        'title': title_display,
        'cover_image_url': image_url,
        'notes': synopsis,
        'status': status_mapped,
        'rating': rating_mapped,
        'start_date': None,
        'end_date': None,
        'tags': '',
    }

    # Tipe Özel Alanlar (Daha güvenli .get() kullanımı)
    if media_type == 'anime':
        mapped_data['episodes_watched'] = 0
        mapped_data['total_episodes'] = jikan_data.get('episodes') # None olabilir
        studios_list = jikan_data.get('studios', []) or []
        studio_names = [
            s.get('name')
            for s in studios_list
            if isinstance(s, dict) and s.get('name')
        ]
        mapped_data['studio'] = ", ".join(filter(None, studio_names))
    elif media_type == 'novel':
        mapped_data['chapters_read'] = 0
        mapped_data['volumes_read'] = 0
        mapped_data['total_chapters'] = jikan_data.get('chapters') # None olabilir
        mapped_data['total_volumes'] = jikan_data.get('volumes') # None olabilir
        authors_list = jikan_data.get('authors', []) or []
        author_names = [
            a.get('name')
            for a in authors_list
            if isinstance(a, dict) and a.get('name')
        ]
        mapped_data['author'] = ", ".join(filter(None, author_names))

    return mapped_data

# ----- Test Kodları (Opsiyonel, kaldırılabilir) -----
# if __name__ == '__main__':
#     logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
#     logger.info("Jikan Servis Testi Başlatıldı")
#     # ... (test kodları) ...