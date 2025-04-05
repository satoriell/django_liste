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
    # Türkçe ve İngilizce dil tercihini başlıkta belirtelim
    headers = {
        'User-Agent': 'DjangoListeApp/0.1 (Contact: YourEmail@example.com)', # Kendi iletişim bilginizi ekleyin
        'Accept-Language': 'tr, en;q=0.9' # Önce Türkçe, sonra İngilizce tercih et
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
    # 1. Tercih edilen dil (örn: 'tr')
    text = data_dict.get(preferred_lang)
    if text: return text
    # 2. Varsayılan dil (örn: 'en')
    text = data_dict.get(default_lang)
    if text: return text
    # 3. Diğer diller (örn: 'ja-ro' gibi Romaji)
    #    Basitlik adına ilk bulduğu değeri döndürebilir veya belirli bir sıra izleyebilir.
    for lang_code, value in data_dict.items():
        # Belki Romaji ('ja-ro') gibi alternatifleri İngilizce'den sonra arayabiliriz
        # if 'ja-ro' in lang_code: return value
        if value: # İlk bulunan değeri al
             return value
    return None # Hiçbir şey bulunamadıysa

def search_manga(title: str, limit: int = 15): # Limiti biraz artırdık
    """Verilen başlığa göre MangaDex'te manga/manhwa/manhua arar.
       Türkçe detayları almaya öncelik verir.
    """
    params = {
        'title': title,
        'limit': limit,
        'includes[]': ['cover_art', 'author', 'artist'],
        'contentRating[]': ['safe', 'suggestive', 'erotica'] # Erotica'yı da ekleyelim mi? (Opsiyonel)
        # 'availableTranslatedLanguage[]': ['tr'] # Bu sadece bölüm çevirisi olanları filtreler, metadata için gereksiz.
    }
    data = _make_request("manga", params=params)

    if not data or data.get('result') != 'ok' or not data.get('data'):
        return []

    results = []
    for manga_data in data['data']:
        attributes = manga_data.get('attributes', {})
        relationships = manga_data.get('relationships', [])

        # Başlık (Türkçe > İngilizce > İlk dil)
        manga_title = get_localized_text(attributes.get('title', {}), default_lang='en', preferred_lang='tr')
        if not manga_title:
             manga_title = f"ID: {manga_data['id']}" # Başlık hiç yoksa

        # Kapak Resmi URL'si (Daha Güvenli Kontrol)
        cover_url = None
        cover_relation = next((rel for rel in relationships if rel.get('type') == 'cover_art'), None)
        if cover_relation and isinstance(cover_relation.get('attributes'), dict):
             filename = cover_relation['attributes'].get('fileName')
             if filename:
                 cover_url = f"https://uploads.mangadex.org/covers/{manga_data['id']}/{filename}.512.jpg"

        # Yazar/Çizer isimleri
        authors = [rel['attributes']['name'] for rel in relationships if rel.get('type') == 'author' and isinstance(rel.get('attributes'), dict) and rel['attributes'].get('name')]
        artists = [rel['attributes']['name'] for rel in relationships if rel.get('type') == 'artist' and isinstance(rel.get('attributes'), dict) and rel['attributes'].get('name')]

        # Açıklama (Türkçe > İngilizce > İlk dil) - Kısa Snippet
        description = get_localized_text(attributes.get('description', {}), default_lang='en', preferred_lang='tr')
        description_snippet = (description[:200] + '...' if description and len(description) > 200 else description) if description else ""


        results.append({
            'id': manga_data['id'], # UUID
            'title': manga_title,
            'description_snippet': description_snippet,
            'year': attributes.get('year'),
            'status': attributes.get('status'),
            'cover_url': cover_url, # None olabilir
            'authors': ", ".join(authors),
            'artists': ", ".join(artists),
        })
    return results

def get_manga_details(mangadex_id: str):
    """Verilen MangaDex UUID'sine sahip öğenin detaylarını getirir."""
    params = {
        'includes[]': ['cover_art', 'author', 'artist'] # Gerekirse başka ilişkiler de eklenebilir ('manga_relation', 'tag' vb.)
    }
    data = _make_request(f"manga/{mangadex_id}", params=params)

    # --- DEBUG İÇİN PRINT (İsteğe Bağlı) ---
    # print("----- MangaDex API Ham Yanıtı (Detay) -----")
    # print(json.dumps(data, indent=2, ensure_ascii=False)) # Türkçe karakterler için ensure_ascii=False
    # print("-----------------------------------------")
    # --- DEBUG SONU ---

    if not data or data.get('result') != 'ok' or not data.get('data'):
        print(f"MangaDex detayları alınamadı veya bulunamadı: {mangadex_id}")
        return None

    return map_mangadex_data_to_dict(data['data'])

def map_mangadex_data_to_dict(manga_data):
    """MangaDex'ten gelen detaylı veriyi Django formunu
       doldurmak için bir sözlüğe dönüştürür (Türkçe öncelikli)."""
    if not manga_data:
        return {}

    attributes = manga_data.get('attributes', {})
    relationships = manga_data.get('relationships', [])

    # Başlık (Türkçe > İngilizce > İlk dil)
    title = get_localized_text(attributes.get('title', {}), default_lang='en', preferred_lang='tr')
    if not title: title = f"ID: {manga_data['id']}"

    # Kapak (Daha Güvenli Kontrol)
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
    # Yazar ve çizer aynıysa ve çizer boş değilse, yine de gösterelim. Boşaltma mantığını kaldırdık.
    # Kullanıcı formda kendisi düzenleyebilir.

    # Açıklama (Türkçe > İngilizce > İlk dil)
    description = get_localized_text(attributes.get('description', {}), default_lang='en', preferred_lang='tr') or ""

    # Diğer potansiyel alanlar (şimdilik eklenmedi, isteğe göre eklenebilir)
    # status = attributes.get('status')
    # year = attributes.get('year')
    # tags = [get_localized_text(t.get('attributes',{}).get('name',{}),'en','tr') for t in attributes.get('tags',[])]

    # Toplam Bölüm/Cilt - API'dan güvenilir şekilde alınamıyor.
    total_chapters = None
    total_volumes = None

    mapped_data = {
        'mangadex_id': manga_data['id'],
        'title': title,
        'cover_image_url': cover_url, # None olabilir
        'author': author_str,
        'artist': artist_str,       # Artık yazarla aynı olsa bile boşaltılmıyor
        'notes': description,      # Açıklamayı notlara ekliyoruz
        'total_chapters': total_chapters, # None
        'total_volumes': total_volumes,   # None
        # Eklenebilecek diğer alanlar...
        # 'status': map_md_status(status), # Durum eşleştirme fonksiyonu yazılırsa
    }

    return mapped_data

# ----- Örnek Kullanım (Test Amaçlı) -----
# (Aynı kalabilir)