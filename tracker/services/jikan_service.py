# tracker/jikan_service.py
# İyileştirmeler: Logging, Hata Yönetimi (404, 429), time.sleep, Ortak Map Fonksiyonu, SFW filtre.

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
    # Endpoint'in path parametrelerini güvenli hale getir (örn: anime/{id})
    safe_endpoint = "/".join([quote(part, safe='') for part in endpoint.split('/')])
    url = f"{JIKAN_BASE_URL}/{safe_endpoint}"

    # Session kullanmıyorsak, her seferinde header oluştur
    headers = {
        'User-Agent': 'DjangoListeApp/0.1 (Contact: YourEmail@example.com)' # E-postanı güncelle
    }

    full_url = url # Loglama için
    response_text_snippet = "" # Hata loglama için
    try:
        # Jikan rate limit (resmi dokümantasyona göre ayarlanabilir - örn: saniyede ~1.6 istek)
        # Her istekten ÖNCE bekleme eklemek daha güvenli olabilir.
        time.sleep(0.6) # Saniyede ~1.6 istek limiti için

        if params:
            # Query parametrelerini URL'e güvenli bir şekilde ekle
            query_string = urlencode(params, doseq=True, safe='[]/:=')
            full_url = f"{url}?{query_string}"
        # else: full_url = url

        logger.debug(f"Jikan API İsteği: {full_url}")

        # Session kullanıyorsak:
        # response = session.get(full_url, timeout=15)
        # Session kullanmıyorsak:
        response = requests.get(full_url, headers=headers, timeout=15)
        response_text_snippet = response.text[:500] # Hata logu için yanıtın başını al

        # 404 Not Found özel durumu (Jikan ID bulunamayınca 404 döner)
        if response.status_code == 404:
            logger.info(f"Jikan API 404 Not Found: {full_url}")
            return None # ID bulunamadıysa None dönmek mantıklı

        # 429 Too Many Requests özel durumu (Rate Limit)
        if response.status_code == 429:
            logger.warning(f"Jikan API Rate Limit Aşıldı (429) - URL: {full_url} - Biraz bekleyip tekrar deneyin.")
            # İsteğe bağlı: Burada tekrar deneme mekanizması eklenebilir (exponential backoff ile)
            # Şimdilik None dönelim.
            return None

        response.raise_for_status() # Diğer HTTP hata kodları için exception fırlat (4xx, 5xx)

        json_response = response.json()

        # Yanıtta 'data' anahtarı olmayabilir veya boş olabilir
        # Arama endpoint'leri ('/anime', '/manga') için 'data': [] normaldir.
        # Detay endpoint'leri ('/anime/{id}', '/manga/{id}') için 'data' olmalı.
        is_search_endpoint = ("anime" in endpoint or "manga" in endpoint) and params and 'q' in params
        if 'data' not in json_response:
            if not is_search_endpoint: # Detay isteği ise hata
                 logger.warning(f"Jikan API yanıtında 'data' anahtarı bulunamadı: {full_url}")
                 return None
            else: # Arama isteği ise boş sonuç olarak kabul et
                 logger.info(f"Jikan API araması 'data' anahtarı olmadan döndü (boş sonuç varsayılır): {full_url}")
                 return {'data': []} # Boş liste içeren dict dön (search fonksiyonları bunu bekliyor)
        elif not json_response['data'] and not is_search_endpoint:
             # Detay isteğinde data boşsa (örn: /full endpoint'i olmayan ID için)
             logger.warning(f"Jikan API yanıtında 'data' boş geldi (detay için): {full_url}")
             return None # Hata veya eksik bilgi olarak kabul et


        return json_response # Başarılı yanıt

    except requests.exceptions.Timeout:
        logger.error(f"Jikan API isteği zaman aşımına uğradı: {full_url}", exc_info=True)
        return None
    except requests.exceptions.HTTPError as http_err:
        # 4xx (404, 429 hariç) veya 5xx hataları
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
    # data['data'] var mı ve liste mi diye kontrol et
    if not isinstance(data.get('data'), list):
        logger.warning(f"Jikan anime arama yanıtı beklenmedik formatta: title='{title}', yanıt: {str(data)[:200]}")
        return [] # Hatalı format veya boş sonuç

    # Sonuçları işle
    results = []
    for anime_data in data['data']:
        mal_id = anime_data.get('mal_id')
        # Ana başlık veya İngilizce başlığı kullan, yoksa ID göster
        title_display = anime_data.get('title') or anime_data.get('title_english') or f"ID: {mal_id}"
        image_url = anime_data.get('images', {}).get('jpg', {}).get('large_image_url')
        if not mal_id: continue # MAL ID yoksa atla

        # Kısa özet
        synopsis = anime_data.get('synopsis', '') or ''
        synopsis_snippet = (synopsis[:150] + '...') if len(synopsis) > 150 else synopsis

        results.append({
            'mal_id': mal_id,
            'title': title_display,
            'image_url': image_url,
            'type': anime_data.get('type'),
            'episodes': anime_data.get('episodes'),
            'score': anime_data.get('score'),
            'status': anime_data.get('status'), # API'dan gelen ham durum
            'synopsis_snippet': synopsis_snippet
        })
    return results

def get_anime_details(mal_id: int):
    """Verilen MAL ID'sine sahip animenin detaylarını (/full endpoint'inden) getirir."""
    # ID'yi URL'e güvenli bir şekilde ekle
    endpoint = f"anime/{quote(str(mal_id))}/full"
    data = _make_jikan_request(endpoint)

    if data is None or not isinstance(data.get('data'), dict):
         logger.warning(f"Jikan anime detayları alınamadı veya format hatalı: MAL ID {mal_id}")
         return None # API hatası, 404 veya format hatası

    # Başarılı yanıttan veriyi ortak map fonksiyonu ile haritala
    return map_jikan_media_data_to_dict(data['data'], 'anime')

# --- Novel Fonksiyonları ---
def search_novel(title: str, limit: int = 10):
    """Verilen başlığa göre Jikan API üzerinde light novel arar."""
    # Novel için manga endpoint'i ve type=lightnovel kullanılır
    params = { 'q': title, 'limit': limit, 'type': 'lightnovel', 'sfw': "true" }
    data = _make_jikan_request("manga", params=params)

    if data is None: return None # API hatası
    if not isinstance(data.get('data'), list):
        logger.warning(f"Jikan novel arama yanıtı beklenmedik formatta: title='{title}', yanıt: {str(data)[:200]}")
        return []

    results = []
    for manga_data in data['data']: # Gelen veri manga formatında
        mal_id = manga_data.get('mal_id')
        title_display = manga_data.get('title') or manga_data.get('title_english') or f"ID: {mal_id}"
        image_url = manga_data.get('images', {}).get('jpg', {}).get('large_image_url')
        if not mal_id: continue

        # Yazar(lar)ı al
        authors = manga_data.get('authors', [])
        author_str = ", ".join([a.get('name') for a in authors if isinstance(a, dict) and a.get('name')])

        synopsis = manga_data.get('synopsis', '') or ''
        synopsis_snippet = (synopsis[:150] + '...') if len(synopsis) > 150 else synopsis

        results.append({
            'mal_id': mal_id,
            'title': title_display,
            'image_url': image_url,
            'type': manga_data.get('type'), # 'Light Novel' olmalı
            'chapters': manga_data.get('chapters'),
            'volumes': manga_data.get('volumes'),
            'score': manga_data.get('score'),
            'status': manga_data.get('status'),
            'author': author_str, # Yazarı ekle
            'synopsis_snippet': synopsis_snippet
        })
    return results

def get_novel_details(mal_id: int):
    """Verilen MAL ID'sine sahip novelin detaylarını getirir."""
    # Novel detayları da manga endpoint'inden alınır
    endpoint = f"manga/{quote(str(mal_id))}/full"
    data = _make_jikan_request(endpoint)

    if data is None or not isinstance(data.get('data'), dict):
         logger.warning(f"Jikan novel detayları alınamadı veya format hatalı: MAL ID {mal_id}")
         return None

     # Gelen verinin tipinin Light Novel olduğunu teyit et (opsiyonel)
    api_type = data['data'].get('type')
    if api_type != 'Light Novel':
         logger.warning(f"Jikan'dan alınan MAL ID {mal_id} bir Light Novel değil, tipi: {api_type}")
         # İsteğe bağlı olarak None dönebilir veya devam edebiliriz. Şimdilik devam edelim.
         # return None

    # Ortak map fonksiyonunu kullan
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
    image_url = jikan_data.get('images', {}).get('jpg', {}).get('large_image_url')
    synopsis = jikan_data.get('synopsis', '')
    status_jikan = jikan_data.get('status') # Örn: "Finished Airing", "Publishing"
    rating_jikan = jikan_data.get('score') # Örn: 8.75

    # Durum Haritalama (Jikan Status -> Bizim Status Choices)
    status_mapped = "Plan to Watch" # Varsayılan
    if status_jikan:
        status_lower = status_jikan.lower()
        if "airing" in status_lower or "publishing" in status_lower:
             status_mapped = "Watching" # İzliyorum/Okuyorum
        elif "finished" in status_lower:
             status_mapped = "Completed" # Tamamladım
        elif "on hiatus" in status_lower:
             status_mapped = "On Hold" # Beklemede
        elif "discontinued" in status_lower: # Jikan'da bu durum var mı emin değilim ama ekleyelim
             status_mapped = "Dropped" # Bıraktım
        # "Not yet aired/published" durumu "Plan to Watch" (varsayılan) olarak kalır.

    # Puan Haritalama (Jikan Float -> Bizim Integer 0-10)
    rating_mapped = None
    if rating_jikan is not None:
        try:
            # Önce float'a çevir, sonra yuvarla, sonra int'e çevir
            rating_float = float(rating_jikan)
            # Sadece 0-10 arasındaki geçerli puanları al
            if 0 <= rating_float <= 10:
                 rating_mapped = int(round(rating_float))
            else:
                 logger.warning(f"Jikan puanı ({rating_jikan}) 0-10 aralığı dışında, None olarak ayarlandı. MAL ID: {mal_id}")
        except (ValueError, TypeError):
            logger.warning(f"Jikan puanı ({rating_jikan}) sayıya dönüştürülemedi. MAL ID: {mal_id}")

    # Form için temel haritalanmış veri
    mapped_data = {
        'mal_id': mal_id,
        'title': title_display,
        'cover_image_url': image_url,
        'notes': synopsis or "", # Synopsis'i notlar alanına koy
        'status': status_mapped, # Haritalanmış durumu kullan
        'rating': rating_mapped, # Haritalanmış puanı kullan
        # Kullanıcının doldurması gerekenler için varsayılanlar
        'start_date': None,
        'end_date': None,
        'tags': '', # Kullanıcı girecek
    }

    # Tipe Özel Alanlar (Anime veya Novel)
    if media_type == 'anime':
        mapped_data['episodes_watched'] = 0 # Varsayılan
        mapped_data['total_episodes'] = jikan_data.get('episodes') # Toplam bölüm sayısı
        # Stüdyo(lar)ı al
        studios = jikan_data.get('studios', [])
        mapped_data['studio'] = ", ".join([s.get('name') for s in studios if isinstance(s, dict) and s.get('name')])
    elif media_type == 'novel':
        mapped_data['chapters_read'] = 0 # Varsayılan
        mapped_data['volumes_read'] = 0 # Varsayılan
        mapped_data['total_chapters'] = jikan_data.get('chapters') # Toplam bölüm (varsa)
        mapped_data['total_volumes'] = jikan_data.get('volumes') # Toplam cilt (varsa)
        # Yazar(lar)ı al
        authors = jikan_data.get('authors', [])
        mapped_data['author'] = ", ".join([a.get('name') for a in authors if isinstance(a, dict) and a.get('name')])

    return mapped_data

# ----- Test Kodları (Opsiyonel, kaldırılabilir) -----
# if __name__ == '__main__':
#     logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
#     logger.info("Jikan Servis Testi Başlatıldı")
#     test_anime_id = 5114 # FMA: Brotherhood
#     test_novel_id = 11757 # Mushoku Tensei LN
#     test_notfound_id = 9999999

#     logger.info("--- Anime Arama ('steins gate') ---")
#     search_results_anime = search_anime("steins gate", limit=3)
#     if search_results_anime: logger.info(f"{len(search_results_anime)} anime sonucu bulundu.")
#     # print(json.dumps(search_results_anime, indent=2))

#     logger.info(f"--- Anime Detayları (MAL ID: {test_anime_id}) ---")
#     details_anime = get_anime_details(test_anime_id)
#     if details_anime: print(json.dumps(details_anime, indent=2, ensure_ascii=False))

#     logger.info("--- Novel Arama ('overlord ln') ---")
#     search_results_novel = search_novel("overlord ln", limit=3)
#     if search_results_novel: logger.info(f"{len(search_results_novel)} novel sonucu bulundu.")
#     # print(json.dumps(search_results_novel, indent=2))

#     logger.info(f"--- Novel Detayları (MAL ID: {test_novel_id}) ---")
#     details_novel = get_novel_details(test_novel_id)
#     if details_novel: print(json.dumps(details_novel, indent=2, ensure_ascii=False))

#     logger.info(f"--- Bulunamayan ID Testi (Anime - MAL ID: {test_notfound_id}) ---")
#     details_notfound_anime = get_anime_details(test_notfound_id)
#     if details_notfound_anime is None: logger.info("Bulunamayan anime ID testi başarılı (None döndü).")

#     logger.info(f"--- Bulunamayan ID Testi (Novel - MAL ID: {test_notfound_id}) ---")
#     details_notfound_novel = get_novel_details(test_notfound_id)
#     if details_notfound_novel is None: logger.info("Bulunamayan novel ID testi başarılı (None döndü).")