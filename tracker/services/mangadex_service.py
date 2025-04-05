# tracker/mangadex_service.py
# İyileştirmeler: Logging detayları, None dönüşü, quote kullanımı, tag/type tespiti.

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
        # MangaDex rate limit'i daha esnek, şimdilik bekleme yok. Gerekirse aktif et:
        # time.sleep(0.2) # Örnek: saniyede 5 istek

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
        # İlişkili verileri dahil et (tek istekte daha fazla bilgi)
        'includes[]': ['cover_art', 'author', 'artist'],
        # İçerik derecelendirmesi (isteğe bağlı olarak 'pornographic', 'erotica' eklenebilir)
        'contentRating[]': ['safe', 'suggestive'],
        # Sipariş (en alakalı olanlar önce gelsin - opsiyonel)
        'order[relevance]': 'desc'
    }
    # API isteğini yap
    data = _make_request("manga", params=params)

    # Hata kontrolü
    if data is None: # API hatası oluştu
        return None # Hata olduğunu belirtmek için None dön
    if not data or data.get('result') != 'ok' or not data.get('data'):
        logger.info(f"MangaDex araması '{title}' için sonuç döndürmedi veya hatalı formatta.")
        return [] # Sonuç yoksa veya format hatalıysa boş liste

    # Sonuçları işle
    results = []
    for manga_data in data['data']:
        attributes = manga_data.get('attributes', {})
        relationships = manga_data.get('relationships', [])
        manga_id = manga_data.get('id')
        if not manga_id: continue # ID yoksa atla

        # Lokalize başlığı al (TR > EN > İlk Bulunan)
        manga_title = get_localized_text(attributes.get('title', {}), preferred_lang='tr')
        if not manga_title: manga_title = f"ID: {manga_id}" # Başlık yoksa ID göster

        # Kapak resmini bul ve URL'ini oluştur
        cover_filename = None
        cover_url = None
        # 'cover_art' tipindeki ilişkiyi bul
        cover_relation = next((rel for rel in relationships if rel.get('type') == 'cover_art'), None)
        if cover_relation and isinstance(cover_relation.get('attributes'), dict):
             cover_filename = cover_relation['attributes'].get('fileName')
             if cover_filename:
                 # Güvenli URL oluşturma (ID ve dosya adını quote et)
                 # .512.jpg gibi uzantılarla belirli boyutları almak mümkün
                 cover_url = f"https://uploads.mangadex.org/covers/{quote(manga_id)}/{quote(cover_filename)}.512.jpg"

        # Yazar ve çizer isimlerini al
        authors = [rel['attributes']['name'] for rel in relationships if rel.get('type') == 'author' and isinstance(rel.get('attributes'), dict) and rel['attributes'].get('name')]
        artists = [rel['attributes']['name'] for rel in relationships if rel.get('type') == 'artist' and isinstance(rel.get('attributes'), dict) and rel['attributes'].get('name')]

        # Açıklama (kısa versiyon)
        description = get_localized_text(attributes.get('description', {}), preferred_lang='tr')
        description_snippet = (description[:200] + '...' if description and len(description) > 200 else description) if description else ""

        results.append({
            'id': manga_id,
            'title': manga_title,
            'description_snippet': description_snippet,
            'year': attributes.get('year'), # Yayın yılı
            'status': attributes.get('status'), # Yayın durumu (ongoing, completed vb.)
            'cover_url': cover_url,
            'authors': ", ".join(authors), # Virgülle ayrılmış string
            'artists': ", ".join(artists), # Virgülle ayrılmış string
        })
    return results

def get_manga_details(mangadex_id: str):
    """Verilen MangaDex UUID'sine sahip öğenin detaylarını getirir."""
    # UUID format kontrolü (opsiyonel ama iyi pratik)
    try:
        uuid_obj = uuid.UUID(mangadex_id)
    except ValueError:
        logger.error(f"Geçersiz MangaDex ID formatı: {mangadex_id}")
        return None

    params = {
        'includes[]': ['cover_art', 'author', 'artist', 'tag'] # Etiketleri de dahil et
    }
    # ID'yi URL'e güvenli bir şekilde ekle (quote ile)
    endpoint = f"manga/{quote(str(uuid_obj))}"
    data = _make_request(endpoint, params=params)

    if data is None: # API hatası veya bulunamadı (404)
        logger.warning(f"MangaDex detayları alınamadı veya bulunamadı: ID={mangadex_id}")
        return None
    if not data or data.get('result') != 'ok' or not data.get('data'):
        logger.warning(f"MangaDex detayları alınamadı (hatalı format): ID={mangadex_id}")
        return None

    # Başarılı yanıttan veriyi haritala
    return map_mangadex_data_to_dict(data['data'])

def map_mangadex_data_to_dict(manga_data):
    """MangaDex'ten gelen detaylı veriyi Django formunu doldurmak için bir sözlüğe dönüştürür."""
    if not manga_data or not isinstance(manga_data, dict):
        logger.error("map_mangadex_data_to_dict: Geçersiz veya boş manga_data.")
        return {}

    attributes = manga_data.get('attributes', {})
    relationships = manga_data.get('relationships', [])
    manga_id = manga_data.get('id')
    if not manga_id:
        logger.error("map_mangadex_data_to_dict: Manga ID bulunamadı.")
        return {} # ID yoksa boş dön

    # Başlık
    title = get_localized_text(attributes.get('title', {}), preferred_lang='tr') or f"ID: {manga_id}"

    # Kapak
    cover_filename = None
    cover_url = None
    cover_relation = next((rel for rel in relationships if rel.get('type') == 'cover_art'), None)
    if cover_relation and isinstance(cover_relation.get('attributes'), dict):
        cover_filename = cover_relation['attributes'].get('fileName')
        if cover_filename:
             cover_url = f"https://uploads.mangadex.org/covers/{quote(manga_id)}/{quote(cover_filename)}.512.jpg"

    # Yazar/Çizer
    authors = [rel['attributes']['name'] for rel in relationships if rel.get('type') == 'author' and isinstance(rel.get('attributes'), dict) and rel['attributes'].get('name')]
    artists = [rel['attributes']['name'] for rel in relationships if rel.get('type') == 'artist' and isinstance(rel.get('attributes'), dict) and rel['attributes'].get('name')]
    author_str = ", ".join(authors)
    artist_str = ", ".join(artists)

    # Açıklama/Notlar
    description = get_localized_text(attributes.get('description', {}), preferred_lang='tr') or ""

    # Tip Tespiti ve Etiketler
    detected_type = 'MANGA' # Varsayılan
    tags_from_api = attributes.get('tags', [])
    tag_names_en = set() # Tutarlılık için İngilizce isimleri topla
    if isinstance(tags_from_api, list):
        for tag_data in tags_from_api:
             # Gelen verinin beklenen yapıda olduğunu kontrol et
             if isinstance(tag_data, dict) and isinstance(tag_data.get('attributes'), dict):
                 tag_name_dict = tag_data['attributes'].get('name', {})
                 if isinstance(tag_name_dict, dict):
                     tag_name = tag_name_dict.get('en') # İngilizce isim
                     if tag_name:
                         tag_names_en.add(tag_name.lower()) # Küçük harfe çevir

        # Webtoon tespiti (etiketlere göre)
        if 'webtoon' in tag_names_en or 'long strip' in tag_names_en:
            detected_type = 'WEBTOON'
            logger.debug(f"Webtoon tipi tespit edildi (etiketlerden): ID={manga_id}")
        elif 'manhwa' in tag_names_en: # Opsiyonel: Manhwa'yı da Webtoon sayabiliriz
             detected_type = 'WEBTOON'
             logger.debug(f"Webtoon tipi tespit edildi (manhwa etiketinden): ID={manga_id}")


    # Formda ve view'da kullanılacak etiket listesi (alfabetik sıralı)
    tags_list_for_view = sorted(list(tag_names_en))

    # Formu doldurmak için haritalanmış veri
    mapped_data = {
        'mangadex_id': manga_id,
        'title': title,
        'cover_image_url': cover_url,
        'author': author_str,
        'artist': artist_str,
        'notes': description, # Notlar alanını API açıklaması ile doldur
        # API genellikle bu bilgileri direkt vermez, kullanıcı doldurmalı
        'total_chapters': None,
        'chapters_read': 0, # Varsayılan
        'total_volumes': None,
        'volumes_read': 0, # Varsayılan
        'platform': '', # Webtoon ise kullanıcı girebilir
        'status': 'Plan to Watch', # Varsayılan durum
        'rating': None, # Kullanıcı girecek
        'start_date': None,
        'end_date': None,
        # Tespit edilen tip ve etiketler view tarafından kullanılacak
        'detected_type': detected_type,
        'tags_list': tags_list_for_view, # View'da tags.add() için kullanılacak
        'tags': ", ".join(tags_list_for_view), # Formdaki tags alanı için string
    }
    return mapped_data

# ----- Test Kodları (Opsiyonel, kaldırılabilir) -----
# if __name__ == '__main__':
#     # Basit logging ayarı
#     logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
#     logger.info("MangaDex Servis Testi Başlatıldı")
#     test_manga_id = "a96676e5-8ae2-425e-b549-7f15dd34a6d8" # One Piece
#     test_webtoon_id = "3f65e893-63ff-4a50-9450-c63860917b33" # Tower of God (ToG)
#     test_invalid_id = "invalid-uuid-format"
#     test_notfound_id = "00000000-0000-0000-0000-000000000000"

#     # logger.info(f"--- Arama Testi ('solo leveling') ---")
#     # search_results = search_manga("solo leveling", limit=5)
#     # if search_results:
#     #     logger.info(f"{len(search_results)} sonuç bulundu.")
#     #     # print(json.dumps(search_results, indent=2, ensure_ascii=False))
#     # elif search_results == []:
#     #     logger.warning("Arama sonucu bulunamadı.")
#     # else:
#     #     logger.error("Arama sırasında API hatası oluştu.")

#     logger.info(f"--- Manga Detayları ({test_manga_id}) ---")
#     details_manga = get_manga_details(test_manga_id)
#     if details_manga: print(json.dumps(details_manga, indent=2, ensure_ascii=False))

#     logger.info(f"--- Webtoon Detayları ({test_webtoon_id}) ---")
#     details_webtoon = get_manga_details(test_webtoon_id)
#     if details_webtoon: print(json.dumps(details_webtoon, indent=2, ensure_ascii=False))

#     logger.info(f"--- Geçersiz ID Testi ({test_invalid_id}) ---")
#     details_invalid = get_manga_details(test_invalid_id)
#     if details_invalid is None: logger.info("Geçersiz ID testi başarılı (None döndü).")

#     logger.info(f"--- Bulunamayan ID Testi ({test_notfound_id}) ---")
#     details_notfound = get_manga_details(test_notfound_id)
#     if details_notfound is None: logger.info("Bulunamayan ID testi başarılı (None döndü).")