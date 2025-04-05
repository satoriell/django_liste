# tracker/mangadex_service.py
# İyileştirmeler: Logging detayları, None dönüşü, quote kullanımı, tag/type tespiti, time.sleep aktif edildi, .get() kullanımı iyileştirildi.

import requests
import time
import json
import logging
import uuid # ID çevirme için
from django.conf import settings
from urllib.parse import urlencode, quote # quote path parametreleri için

# Logger oluştur (settings.py'den yapılandırmayı alır)
logger = logging.getLogger(__name__)

# MangaDex API base URL (settings.py'den)
BASE_URL = settings.MANGADEX_API_URL

# Opsiyonel: requests.Session kullanımı (Tek bir session objesi oluşturup tekrar kullanmak için)
# session = requests.Session()
# session.headers.update({
#     'User-Agent': 'DjangoListeApp/0.1 (Contact: YourEmail@example.com)', # E-postanı güncelle
#     'Accept-Language': 'tr, en;q=0.9'
# })

# Genel istek fonksiyonu (Logging ve Hata Yönetimi İyileştirildi)
def _make_request(endpoint, params=None):
    """MangaDex API'na güvenli GET isteği yapar (Logging ile). Hata veya bulunamazsa None döner."""
    # Endpoint'in path parametrelerini güvenli hale getir (örn: manga/{id})
    # quote_via parametresi ile '/' karakterinin encode edilmesini engelle
    safe_endpoint = "/".join([quote(part, safe='') for part in endpoint.split('/')])
    url = f"{BASE_URL}/{safe_endpoint}"

    # Session kullanmıyorsak, her seferinde header oluştur
    headers = {
        'User-Agent': 'DjangoListeApp/0.1 (Contact: YourEmail@example.com)', # E-postanı güncelle
        'Accept-Language': 'tr, en;q=0.9' # Türkçe içeriği tercih et
    }

    full_url = url # Loglama için
    response_text_snippet = "" # Hata durumunda loglamak için
    try:
        # ----- YORUMU KALDIRILDI -----
        time.sleep(0.2) # MangaDex rate limit için küçük bir bekleme (saniyede 5 istek)
        # -------------------------

        if params:
            # Query parametrelerini URL'e güvenli bir şekilde ekle
            # safe='[]/:=' -> köşeli parantezleri (includes[] için) ve diğer bazı özel karakterleri koru
            query_string = urlencode(params, doseq=True, safe='[]/:=')
            full_url = f"{url}?{query_string}"
        # else: full_url = url # Zaten yukarıda tanımlı

        logger.debug(f"MangaDex API İsteği: {full_url}")

        # Session kullanıyorsak:
        # response = session.get(full_url, timeout=15)
        # Session kullanmıyorsak:
        response = requests.get(full_url, headers=headers, timeout=15)
        response_text_snippet = response.text[:500] # Hata logu için yanıtın başını al

        # 404 Not Found özel durumu (ID bulunamayınca)
        if response.status_code == 404:
             logger.warning(f"MangaDex API 404 Not Found: {full_url}")
             return None # Bulunamadıysa None dön

        response.raise_for_status() # Diğer HTTP hata kodları için exception fırlat (4xx, 5xx)

        # Yanıtı JSON olarak parse et
        return response.json()

    except requests.exceptions.Timeout:
        logger.error(f"MangaDex API isteği zaman aşımına uğradı: {full_url}", exc_info=True) # Traceback ekle
        return None
    except requests.exceptions.HTTPError as http_err:
        # 4xx (404 hariç) veya 5xx hataları
        status_code = http_err.response.status_code
        logger.error(
            f"MangaDex API HTTP Hatası ({status_code}) - URL: {full_url} - Detay: {response_text_snippet}",
            exc_info=False # Traceback genelde gereksiz, yanıt önemli
        )
        return None
    except requests.exceptions.RequestException as req_err:
        # Bağlantı hatası vb. diğer request hataları
        logger.error(f"MangaDex API Bağlantı/İstek Hatası - URL: {full_url} - Hata: {req_err}", exc_info=True)
        return None
    except json.JSONDecodeError:
         # Yanıt JSON değilse
         logger.error(
             f"MangaDex API JSON Decode Hatası - URL: {full_url} - Yanıt: {response_text_snippet}",
             exc_info=True # JSON hatası traceback'i faydalı olabilir
         )
         return None
    except Exception as e:
        # Beklenmedik diğer hatalar
        logger.error(f"MangaDex API Genel Hata - URL: {full_url} - Hata: {e}", exc_info=True)
        return None

def get_localized_text(data_dict, default_lang='en', preferred_lang='tr'):
    """
    Verilen sözlükten önce tercih edilen dili (tr), sonra varsayılanı (en),
    sonra da ilk bulduğu geçerli (None olmayan) değeri döndürür.
    """
    if not isinstance(data_dict, dict):
        return None # Veya boş string "" ? None daha iyi olabilir.
    # Önce TR, sonra EN, sonra listedeki ilk geçerli değer
    return data_dict.get(preferred_lang) or data_dict.get(default_lang) or next((v for v in data_dict.values() if v), None)

def search_manga(title: str, limit: int = 15):
    """Verilen başlığa göre MangaDex'te manga/manhwa/manhua arar."""
    params = {
        'title': title,
        'limit': limit,
        'includes[]': ['cover_art', 'author', 'artist'],
        'contentRating[]': ['safe', 'suggestive'],
        'order[relevance]': 'desc'
    }
    data = _make_request("manga", params=params)

    if data is None: return None
    if not data or data.get('result') != 'ok' or not isinstance(data.get('data'), list): # data'nın list olduğunu kontrol et
        logger.info(f"MangaDex araması '{title}' için sonuç döndürmedi veya hatalı formatta.")
        return []

    results = []
    for manga_data in data['data']:
        # .get() kullanımı daha güvenli hale getirildi (varsayılan değerlerle)
        attributes = manga_data.get('attributes', {}) or {} # attributes yoksa boş dict
        relationships = manga_data.get('relationships', []) or [] # relationships yoksa boş liste
        manga_id = manga_data.get('id')
        if not manga_id: continue

        manga_title = get_localized_text(attributes.get('title', {}), preferred_lang='tr') or f"ID: {manga_id}"

        cover_filename = None
        cover_url = None
        # cover_relation için .get() kullanmak daha güvenli
        cover_relation = next((rel for rel in relationships if rel.get('type') == 'cover_art'), None)
        # cover_relation['attributes'] yerine .get('attributes') kullan
        cover_attributes = cover_relation.get('attributes', {}) if cover_relation else {}
        if isinstance(cover_attributes, dict):
            cover_filename = cover_attributes.get('fileName')
            if cover_filename:
                 cover_url = f"https://uploads.mangadex.org/covers/{quote(manga_id)}/{quote(cover_filename)}.512.jpg"

        # Yazar/Çizer alırken daha dikkatli ol
        authors = [
            rel.get('attributes', {}).get('name')
            for rel in relationships
            if rel.get('type') == 'author' and rel.get('attributes', {}).get('name') # Hem attributes hem name var mı?
        ]
        artists = [
            rel.get('attributes', {}).get('name')
            for rel in relationships
            if rel.get('type') == 'artist' and rel.get('attributes', {}).get('name')
        ]

        description_dict = attributes.get('description', {})
        description = get_localized_text(description_dict, preferred_lang='tr') if isinstance(description_dict, dict) else ""
        description_snippet = (description[:200] + '...' if description and len(description) > 200 else description) if description else ""

        results.append({
            'id': manga_id,
            'title': manga_title,
            'description_snippet': description_snippet,
            'year': attributes.get('year'),
            'status': attributes.get('status'),
            'cover_url': cover_url,
            'authors': ", ".join(filter(None, authors)), # None değerleri filtrele
            'artists': ", ".join(filter(None, artists)), # None değerleri filtrele
        })
    return results

def get_manga_details(mangadex_id: str):
    """Verilen MangaDex UUID'sine sahip öğenin detaylarını getirir."""
    try:
        uuid_obj = uuid.UUID(str(mangadex_id))
    except ValueError:
        logger.error(f"Geçersiz MangaDex ID formatı: {mangadex_id}")
        return None

    params = {
        'includes[]': ['cover_art', 'author', 'artist', 'tag']
    }
    endpoint = f"manga/{quote(str(uuid_obj))}"
    data = _make_request(endpoint, params=params)

    if data is None:
        logger.warning(f"MangaDex detayları alınamadı veya bulunamadı: ID={mangadex_id}")
        return None
    if not data or data.get('result') != 'ok' or not data.get('data'):
        logger.warning(f"MangaDex detayları alınamadı (hatalı format): ID={mangadex_id}")
        return None

    return map_mangadex_data_to_dict(data['data'])

def map_mangadex_data_to_dict(manga_data):
    """MangaDex'ten gelen detaylı veriyi Django formunu doldurmak için bir sözlüğe dönüştürür."""
    if not manga_data or not isinstance(manga_data, dict):
        logger.error("map_mangadex_data_to_dict: Geçersiz veya boş manga_data.")
        return {}

    attributes = manga_data.get('attributes', {}) or {}
    relationships = manga_data.get('relationships', []) or []
    manga_id = manga_data.get('id')
    if not manga_id:
        logger.error("map_mangadex_data_to_dict: Manga ID bulunamadı.")
        return {}

    title = get_localized_text(attributes.get('title', {}), preferred_lang='tr') or f"ID: {manga_id}"

    cover_filename = None
    cover_url = None
    cover_relation = next((rel for rel in relationships if rel.get('type') == 'cover_art'), None)
    cover_attributes = cover_relation.get('attributes', {}) if cover_relation else {}
    if isinstance(cover_attributes, dict):
        cover_filename = cover_attributes.get('fileName')
        if cover_filename:
            cover_url = f"https://uploads.mangadex.org/covers/{quote(manga_id)}/{quote(cover_filename)}.512.jpg"

    authors = [
        rel.get('attributes', {}).get('name')
        for rel in relationships
        if rel.get('type') == 'author' and rel.get('attributes', {}).get('name')
    ]
    artists = [
        rel.get('attributes', {}).get('name')
        for rel in relationships
        if rel.get('type') == 'artist' and rel.get('attributes', {}).get('name')
    ]
    author_str = ", ".join(filter(None, authors))
    artist_str = ", ".join(filter(None, artists))

    description_dict = attributes.get('description', {})
    description = get_localized_text(description_dict, preferred_lang='tr') if isinstance(description_dict, dict) else ""

    detected_type = 'MANGA'
    tags_from_api = attributes.get('tags', []) or [] # tags yoksa boş liste
    tag_names_en = set()
    if isinstance(tags_from_api, list):
        for tag_data in tags_from_api:
             tag_attributes = tag_data.get('attributes', {}) if isinstance(tag_data, dict) else {}
             tag_name_dict = tag_attributes.get('name', {}) if isinstance(tag_attributes, dict) else {}
             if isinstance(tag_name_dict, dict):
                 tag_name = tag_name_dict.get('en')
                 if tag_name and isinstance(tag_name, str): # tag_name string mi?
                     tag_names_en.add(tag_name.lower())

        if 'webtoon' in tag_names_en or 'long strip' in tag_names_en:
            detected_type = 'WEBTOON'
            logger.debug(f"Webtoon tipi tespit edildi (etiketlerden): ID={manga_id}")
        elif 'manhwa' in tag_names_en:
             detected_type = 'WEBTOON'
             logger.debug(f"Webtoon tipi tespit edildi (manhwa etiketinden): ID={manga_id}")

    tags_list_for_view = sorted(list(tag_names_en))

    mapped_data = {
        'mangadex_id': manga_id,
        'title': title,
        'cover_image_url': cover_url,
        'author': author_str,
        'artist': artist_str,
        'notes': description,
        'total_chapters': None,
        'chapters_read': 0,
        'total_volumes': None,
        'volumes_read': 0,
        'platform': '',
        'status': 'Plan to Watch',
        'rating': None,
        'start_date': None,
        'end_date': None,
        'detected_type': detected_type,
        'tags_list': tags_list_for_view,
        'tags': ", ".join(tags_list_for_view),
    }
    return mapped_data

# ----- Test Kodları (Opsiyonel, kaldırılabilir) -----
# if __name__ == '__main__':
#     logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
#     logger.info("MangaDex Servis Testi Başlatıldı")
#     # ... (test kodları) ...