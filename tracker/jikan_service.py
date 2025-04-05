# tracker/jikan_service.py
# YENİ: search_novel, get_novel_details eklendi. map fonksiyonu genelleştirildi.

import requests
import time
import json # Debug için
from django.conf import settings
from urllib.parse import urlencode

# Jikan API base URL (v4)
JIKAN_BASE_URL = "https://api.jikan.moe/v4"

# Genel Jikan istek fonksiyonu (Aynı kalır)
def _make_jikan_request(endpoint, params=None):
    """Jikan API'na güvenli GET isteği yapar."""
    url = f"{JIKAN_BASE_URL}/{endpoint}"
    headers = { 'User-Agent': 'DjangoListeApp/0.1 (Contact: YourEmail@example.com)' }
    try:
        time.sleep(0.6) # Rate limit için bekleme
        full_url = f"{url}?{urlencode(params, doseq=True, safe='[]')}" if params else url
        # print(f"Jikan İsteği: {full_url}") # DEBUG
        response = requests.get(full_url, headers=headers, timeout=15)
        if response.status_code == 404: return None
        response.raise_for_status()
        json_response = response.json()
        if 'data' not in json_response or not json_response['data']:
            # Arama için boş data dönebilir, detay için None mantıklı
            is_search = '?' in endpoint # Basit kontrol
            return {'data': []} if is_search else None
        return json_response
    except requests.exceptions.Timeout: print(f"Jikan timeout: {full_url}"); return None
    except requests.exceptions.RequestException as e: print(f"Jikan request error: {full_url} - {e}"); return None
    except json.JSONDecodeError: print(f"Jikan JSON error: {full_url}"); return None
    except Exception as e: print(f"Jikan general error: {full_url} - {e}"); return None

# --- Anime Fonksiyonları ---
def search_anime(title: str, limit: int = 10):
    """Verilen başlığa göre Jikan API üzerinde anime arar."""
    params = { 'q': title, 'limit': limit, 'sfw': "true" }
    data = _make_jikan_request("anime", params=params)
    if not data or 'data' not in data or not isinstance(data['data'], list): return []

    results = []
    for anime_data in data['data']:
        mal_id = anime_data.get('mal_id')
        title_display = anime_data.get('title') or anime_data.get('title_english')
        image_url = anime_data.get('images', {}).get('jpg', {}).get('large_image_url')
        if not mal_id or not title_display: continue
        results.append({
            'mal_id': mal_id,
            'title': title_display,
            'image_url': image_url,
            'type': anime_data.get('type'),
            'episodes': anime_data.get('episodes'),
            'score': anime_data.get('score'),
            'status': anime_data.get('status'),
            'synopsis_snippet': (anime_data.get('synopsis', '') or '')[:150] + ('...' if len(anime_data.get('synopsis', '') or '') > 150 else '')
        })
    return results

def get_anime_details(mal_id: int):
    """Verilen MAL ID'sine sahip animenin detaylarını getirir."""
    data = _make_jikan_request(f"anime/{mal_id}/full")
    if not data or 'data' not in data or not isinstance(data['data'], dict):
        print(f"Jikan anime detayları alınamadı: MAL ID {mal_id}")
        return None
    # Ortak map fonksiyonunu kullan
    return map_jikan_media_data_to_dict(data['data'], 'anime')

# --- YENİ: Novel Fonksiyonları ---
def search_novel(title: str, limit: int = 10):
    """Verilen başlığa göre Jikan API üzerinde light novel arar."""
    params = {
        'q': title,
        'limit': limit,
        'type': 'lightnovel', # Sadece light novel ara (veya 'novel,lightnovel'?)
        'sfw': "true"
    }
    # Dikkat: Anime için /anime, Novel için /manga endpoint'i kullanılır
    data = _make_jikan_request("manga", params=params)
    if not data or 'data' not in data or not isinstance(data['data'], list): return []

    results = []
    for manga_data in data['data']: # Jikan bunları 'manga' olarak döndürür
        mal_id = manga_data.get('mal_id')
        title_display = manga_data.get('title') or manga_data.get('title_english')
        image_url = manga_data.get('images', {}).get('jpg', {}).get('large_image_url')
        authors = manga_data.get('authors', []) # Yazar listesi
        author_str = ", ".join([a.get('name') for a in authors if a.get('name')]) if authors else ""

        if not mal_id or not title_display: continue
        results.append({
            'mal_id': mal_id,
            'title': title_display,
            'image_url': image_url,
            'type': manga_data.get('type'), # 'Light Novel' olmalı
            'chapters': manga_data.get('chapters'), # None olabilir
            'volumes': manga_data.get('volumes'), # None olabilir
            'score': manga_data.get('score'),
            'status': manga_data.get('status'), # Publishing, Finished, etc.
            'author': author_str, # Yazar(lar)
            'synopsis_snippet': (manga_data.get('synopsis', '') or '')[:150] + ('...' if len(manga_data.get('synopsis', '') or '') > 150 else '')
        })
    return results

def get_novel_details(mal_id: int):
    """Verilen MAL ID'sine sahip novelin detaylarını getirir."""
    # Dikkat: Anime için /anime, Novel için /manga endpoint'i kullanılır
    data = _make_jikan_request(f"manga/{mal_id}/full")
    if not data or 'data' not in data or not isinstance(data['data'], dict):
        print(f"Jikan novel detayları alınamadı: MAL ID {mal_id}")
        return None
    # Ortak map fonksiyonunu kullan
    return map_jikan_media_data_to_dict(data['data'], 'novel')

# --- Ortak Map Fonksiyonu ---
def map_jikan_media_data_to_dict(jikan_data, media_type):
    """Jikan'dan gelen detaylı veriyi (anime veya novel) Django formunu
       doldurmak için ortak bir sözlüğe dönüştürür."""
    if not jikan_data: return {}

    mal_id = jikan_data.get('mal_id')
    title_display = jikan_data.get('title') or jikan_data.get('title_english')
    image_url = jikan_data.get('images', {}).get('jpg', {}).get('large_image_url')
    synopsis = jikan_data.get('synopsis', '')
    status_jikan = jikan_data.get('status')
    rating_jikan = jikan_data.get('score')

    # --- Ortak Alanlar ---
    status_mapped = "Plan to Watch"
    if status_jikan:
        status_lower = status_jikan.lower()
        # Anime durumları
        if "currently airing" in status_lower: status_mapped = "Watching"
        elif "finished airing" in status_lower: status_mapped = "Completed"
        # Manga/Novel durumları
        elif "publishing" in status_lower: status_mapped = "Watching" # Okuyorum varsayalım
        elif "finished" in status_lower: status_mapped = "Completed"
        elif "on hiatus" in status_lower: status_mapped = "On Hold"
        elif "discontinued" in status_lower: status_mapped = "Dropped" # Bıraktım?
        elif "not yet published" in status_lower: status_mapped = "Plan to Watch" # Okuyacağım

    rating_mapped = None
    if rating_jikan is not None:
        try:
            if 0 <= float(rating_jikan) <= 10: rating_mapped = int(round(float(rating_jikan)))
        except (ValueError, TypeError): pass # Hata varsa None kalır

    mapped_data = {
        'mal_id': mal_id,
        'title': title_display,
        'cover_image_url': image_url,
        'notes': synopsis or "",
        'status': status_mapped,
        'rating': rating_mapped,
    }

    # --- Tipe Özel Alanlar ---
    if media_type == 'anime':
        mapped_data['total_episodes'] = jikan_data.get('episodes')
        studios = jikan_data.get('studios', [])
        mapped_data['studio'] = ", ".join([s.get('name') for s in studios if s.get('name')]) if studios else ""
    elif media_type == 'novel':
        authors = jikan_data.get('authors', [])
        mapped_data['author'] = ", ".join([a.get('name') for a in authors if a.get('name')]) if authors else ""
        mapped_data['total_chapters'] = jikan_data.get('chapters') # None olabilir
        mapped_data['total_volumes'] = jikan_data.get('volumes') # None olabilir

    return mapped_data

# ----- Örnek Kullanım (Test Amaçlı) -----
# if __name__ == '__main__':
#     test_anime_id = 5114
#     test_novel_id = 11757 # Mushoku Tensei Light Novel MAL ID
#
#     print(f"\n--- Anime Detayları (MAL ID: {test_anime_id}) ---")
#     details_anime = get_anime_details(test_anime_id)
#     if details_anime: print(json.dumps(details_anime, indent=2, ensure_ascii=False))
#
#     print(f"\n--- Novel Detayları (MAL ID: {test_novel_id}) ---")
#     details_novel = get_novel_details(test_novel_id)
#     if details_novel: print(json.dumps(details_novel, indent=2, ensure_ascii=False))
#
#     print("\n--- Anime Arama ('Cowboy Bebop') ---")
#     search_results_anime = search_anime("Cowboy Bebop")
#     if search_results_anime: print(f"{len(search_results_anime)} sonuç: {search_results_anime[0]['title']}")
#
#     print("\n--- Novel Arama ('Mushoku Tensei') ---")
#     search_results_novel = search_novel("Mushoku Tensei")
#     if search_results_novel: print(f"{len(search_results_novel)} sonuç: {search_results_novel[0]['title']}")