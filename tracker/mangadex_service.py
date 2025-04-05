# tracker/mangadex_service.py

import requests
import time
import json # Debug print için
from django.conf import settings
from urllib.parse import urlencode

# MangaDex API base URL
BASE_URL = settings.MANGADEX_API_URL

# Genel istek fonksiyonu
def _make_request(endpoint, params=None):
    """MangaDex API'na güvenli GET isteği yapar."""
    url = f"{BASE_URL}/{endpoint}"
    headers = {
        'User-Agent': 'DjangoListeApp/0.1 (Contact: YourEmail@example.com)',
        'Accept-Language': 'tr, en;q=0.9'
    }
    try:
        # time.sleep(0.25) # Rate limit için gerekirse

        if params:
            query_string = urlencode(params, doseq=True, safe='[]')
            full_url = f"{url}?{query_string}"
        else:
            full_url = url

        # print(f"MangaDex İsteği: {full_url}") # DEBUG

        response = requests.get(full_url, headers=headers, timeout=15)
        response.raise_for_status()
        return response.json()

    except requests.exceptions.Timeout:
        print(f"MangaDex API isteği zaman aşımına uğradı ({full_url})")
        return None
    except requests.exceptions.RequestException as e:
        print(f"MangaDex API isteği hatası ({full_url}): {e}")
        if e.response is not None:
             print(f"Yanıt İçeriği: {e.response.text}")
        return None
    except Exception as e:
        print(f"MangaDex yanıtını işlerken genel hata ({full_url}): {e}")
        return None

def get_localized_text(data_dict, default_lang='en', preferred_lang='tr'):
    """Verilen sözlükten önce tercih edilen dili, sonra varsayılanı,
       sonra da ilk bulduğunu döndürür."""
    if not isinstance(data_dict, dict):
        return None
    text = data_dict.get(preferred_lang)
    if text: return text
    text = data_dict.get(default_lang)
    if text: return text
    for lang_code, value in data_dict.items():
        if value: return value
    return None

def search_manga(title: str, limit: int = 15):
    """Verilen başlığa göre MangaDex'te manga/manhwa/manhua arar."""
    params = {
        'title': title,
        'limit': limit,
        'includes[]': ['cover_art', 'author', 'artist'],
        'contentRating[]': ['safe', 'suggestive', 'erotica']
    }
    data = _make_request("manga", params=params)

    if not data or data.get('result') != 'ok' or not data.get('data'):
        return []

    results = []
    for manga_data in data['data']:
        attributes = manga_data.get('attributes', {})
        relationships = manga_data.get('relationships', [])

        manga_title = get_localized_text(attributes.get('title', {}), default_lang='en', preferred_lang='tr')
        if not manga_title: manga_title = f"ID: {manga_data['id']}"

        cover_url = None
        cover_relation = next((rel for rel in relationships if rel.get('type') == 'cover_art'), None)
        if cover_relation and isinstance(cover_relation.get('attributes'), dict):
             filename = cover_relation['attributes'].get('fileName')
             if filename:
                 cover_url = f"https://uploads.mangadex.org/covers/{manga_data['id']}/{filename}.512.jpg"

        authors = [rel['attributes']['name'] for rel in relationships if rel.get('type') == 'author' and isinstance(rel.get('attributes'), dict) and rel['attributes'].get('name')]
        artists = [rel['attributes']['name'] for rel in relationships if rel.get('type') == 'artist' and isinstance(rel.get('attributes'), dict) and rel['attributes'].get('name')]

        description = get_localized_text(attributes.get('description', {}), default_lang='en', preferred_lang='tr')
        description_snippet = (description[:200] + '...' if description and len(description) > 200 else description) if description else ""

        results.append({
            'id': manga_data['id'],
            'title': manga_title,
            'description_snippet': description_snippet,
            'year': attributes.get('year'),
            'status': attributes.get('status'),
            'cover_url': cover_url,
            'authors': ", ".join(authors),
            'artists': ", ".join(artists),
        })
    return results

def get_manga_details(mangadex_id: str):
    """Verilen MangaDex UUID'sine sahip öğenin detaylarını getirir."""
    params = {
        # DİKKAT: 'tag' BURAYA EKLENDİ!
        'includes[]': ['cover_art', 'author', 'artist', 'tag']
    }
    data = _make_request(f"manga/{mangadex_id}", params=params)

    # --- DEBUG İÇİN PRINT (İsteğe Bağlı) ---
    # print("----- MangaDex API Ham Yanıtı (Detay) -----")
    # print(json.dumps(data, indent=2, ensure_ascii=False))
    # print("-----------------------------------------")
    # --- DEBUG SONU ---

    if not data or data.get('result') != 'ok' or not data.get('data'):
        print(f"MangaDex detayları alınamadı veya bulunamadı: {mangadex_id}")
        return None

    return map_mangadex_data_to_dict(data['data'])

def map_mangadex_data_to_dict(manga_data):
    """MangaDex'ten gelen detaylı veriyi Django formunu
       doldurmak için bir sözlüğe dönüştürür (Türkçe öncelikli ve tip tespiti ile)."""
    if not manga_data:
        return {}

    attributes = manga_data.get('attributes', {})
    relationships = manga_data.get('relationships', [])

    # Başlık
    title = get_localized_text(attributes.get('title', {}), default_lang='en', preferred_lang='tr')
    if not title: title = f"ID: {manga_data['id']}"

    # Kapak
    cover_url = None
    cover_relation = next((rel for rel in relationships if rel.get('type') == 'cover_art'), None)
    if cover_relation and isinstance(cover_relation.get('attributes'), dict):
        filename = cover_relation['attributes'].get('fileName')
        if filename:
             cover_url = f"https://uploads.mangadex.org/covers/{manga_data['id']}/{filename}.512.jpg"

    # Yazar/Çizer
    authors = [rel['attributes']['name'] for rel in relationships if rel.get('type') == 'author' and isinstance(rel.get('attributes'), dict) and rel['attributes'].get('name')]
    artists = [rel['attributes']['name'] for rel in relationships if rel.get('type') == 'artist' and isinstance(rel.get('attributes'), dict) and rel['attributes'].get('name')]
    author_str = ", ".join(authors) if authors else ""
    artist_str = ", ".join(artists) if artists else ""

    # Açıklama
    description = get_localized_text(attributes.get('description', {}), default_lang='en', preferred_lang='tr') or ""

    # Toplam Bölüm/Cilt
    total_chapters = None
    total_volumes = None

    # --- DİKKAT: Tip Tespiti (Etiketlere Göre) BURADA ---
    detected_type = 'MANGA' # Varsayılan
    tags = attributes.get('tags', []) # API yanıtından etiketleri al
    if isinstance(tags, list):
        # Etiket isimlerini al (İngilizce isimlerine bakmak daha güvenilir)
        tag_names_en = set() # Tekrarları önlemek için set kullanalım
        for tag in tags:
             if isinstance(tag.get('attributes'), dict):
                 tag_name = tag['attributes'].get('name', {}).get('en')
                 if tag_name:
                      tag_names_en.add(tag_name.lower()) # Küçük harfe çevir

        # "Webtoon" veya "Long Strip" etiketleri var mı kontrol et
        if 'webtoon' in tag_names_en or 'long strip' in tag_names_en:
            detected_type = 'WEBTOON'
            # print(f"Webtoon tespit edildi: {manga_data['id']}") # DEBUG
        # Alternatif: Format etiket grubu kontrolü (daha az güvenilir olabilir)
        # elif any(t.get('attributes',{}).get('group') == 'format' and t.get('attributes',{}).get('name',{}).get('en','').lower() in ['webtoon', 'long strip'] for t in tags):
        #     detected_type = 'WEBTOON'
    # ----------------------------------------------------

    mapped_data = {
        'mangadex_id': manga_data['id'],
        'title': title,
        'cover_image_url': cover_url,
        'author': author_str,
        'artist': artist_str,
        'notes': description,
        'total_chapters': total_chapters,
        'total_volumes': total_volumes,
        'detected_type': detected_type, # <- TESPİT EDİLEN TİP EKLENDİ
    }
    return mapped_data

# ----- Örnek Kullanım (Test Amaçlı) -----
# if __name__ == '__main__':
#     # ... (test kodları aynı kalabilir) ...