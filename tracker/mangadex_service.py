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
        'User-Agent': 'DjangoListeApp/0.1 (Contact: YourEmail@example.com)', # İletişim e-postanı buraya ekleyebilirsin
        'Accept-Language': 'tr, en;q=0.9'
    }
    try:
        # time.sleep(0.25) # Rate limit için gerekirse

        if params:
            # Parametreleri URL'e güvenli bir şekilde ekle (includes[] gibi listeleri destekler)
            query_string = urlencode(params, doseq=True, safe='[]')
            full_url = f"{url}?{query_string}"
        else:
            full_url = url

        # print(f"MangaDex İsteği: {full_url}") # DEBUG

        response = requests.get(full_url, headers=headers, timeout=15)
        response.raise_for_status() # HTTP hata kodları için exception fırlat
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
    # Eğer ikisi de yoksa, ilk bulduğu geçerli değeri döndür
    for lang_code, value in data_dict.items():
        if value: return value
    return None

def search_manga(title: str, limit: int = 15):
    """Verilen başlığa göre MangaDex'te manga/manhwa/manhua arar."""
    params = {
        'title': title,
        'limit': limit,
        'includes[]': ['cover_art', 'author', 'artist'],
        'contentRating[]': ['safe', 'suggestive', 'erotica'] # Content rating filtrelemesi (isteğe bağlı)
    }
    data = _make_request("manga", params=params)

    if not data or data.get('result') != 'ok' or not data.get('data'):
        return [] # Hata veya sonuç yoksa boş liste dön

    results = []
    for manga_data in data['data']:
        attributes = manga_data.get('attributes', {})
        relationships = manga_data.get('relationships', [])

        manga_title = get_localized_text(attributes.get('title', {}), default_lang='en', preferred_lang='tr')
        if not manga_title: manga_title = f"ID: {manga_data['id']}" # Başlık yoksa ID göster

        # Kapak resmi URL'ini oluştur
        cover_url = None
        cover_relation = next((rel for rel in relationships if rel.get('type') == 'cover_art'), None)
        if cover_relation and isinstance(cover_relation.get('attributes'), dict):
             filename = cover_relation['attributes'].get('fileName')
             if filename:
                 # .512.jpg formatı daha büyük bir önizleme sağlar
                 cover_url = f"https://uploads.mangadex.org/covers/{manga_data['id']}/{filename}.512.jpg"

        # Yazar ve çizerleri al
        authors = [rel['attributes']['name'] for rel in relationships if rel.get('type') == 'author' and isinstance(rel.get('attributes'), dict) and rel['attributes'].get('name')]
        artists = [rel['attributes']['name'] for rel in relationships if rel.get('type') == 'artist' and isinstance(rel.get('attributes'), dict) and rel['attributes'].get('name')]

        # Açıklama (kısa snippet)
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
        # DİKKAT: 'tag' BURAYA EKLENMİŞTİ ve KALMALI!
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

    # Haritalama fonksiyonunu çağır
    return map_mangadex_data_to_dict(data['data'])

def map_mangadex_data_to_dict(manga_data):
    """MangaDex'ten gelen detaylı veriyi Django formunu
       doldurmak için bir sözlüğe dönüştürür (Türkçe öncelikli, tip tespiti ve ETİKET listesi ile)."""
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

    # Toplam Bölüm/Cilt (API genellikle bu bilgiyi manga endpoint'inde doğrudan vermez,
    # aggregate endpoint'i veya chapters endpoint'i gerekebilir. Şimdilik None bırakıyoruz.)
    total_chapters = None
    total_volumes = None

    # --- Tip Tespiti (Etiketlere Göre) ---
    detected_type = 'MANGA' # Varsayılan
    tags_from_api = attributes.get('tags', []) # API yanıtından etiketleri al (Bu bir liste olmalı)
    tag_names_en = set() # Tekrarları önlemek ve etiket isimlerini tutmak için set

    if isinstance(tags_from_api, list):
        for tag_data in tags_from_api:
             if isinstance(tag_data.get('attributes'), dict):
                 tag_name_dict = tag_data['attributes'].get('name', {})
                 tag_name = tag_name_dict.get('en') # İngilizce ismini alalım (daha güvenilir)
                 if tag_name:
                      tag_names_en.add(tag_name.lower()) # Küçük harfe çevirip sete ekle

        # "Webtoon" veya "Long Strip" etiketleri var mı kontrol et
        if 'webtoon' in tag_names_en or 'long strip' in tag_names_en:
            detected_type = 'WEBTOON'
            # print(f"Webtoon tespit edildi: {manga_data['id']}") # DEBUG
    # --- Tip Tespiti Sonu ---

    # --- YENİ: Etiket İsimlerini Listeye Ekleme ---
    # tag_names_en set'ini views.py'nin kullanması için listeye çevirelim
    tags_list_for_view = list(tag_names_en)
    # ----------------------------------------------

    # Sonuç sözlüğünü oluştur
    mapped_data = {
        'mangadex_id': manga_data['id'],
        'title': title,
        'cover_image_url': cover_url,
        'author': author_str,
        'artist': artist_str,
        'notes': description, # notes alanını description ile dolduralım
        'total_chapters': total_chapters, # API'dan gelmediği için None
        'total_volumes': total_volumes,   # API'dan gelmediği için None
        'detected_type': detected_type, # Tespit edilen tip (MANGA veya WEBTOON)
        'tags_list': tags_list_for_view, # <- ETİKET LİSTESİ EKLENDİ
    }
    return mapped_data

# ----- Örnek Kullanım (Test Amaçlı) -----
# if __name__ == '__main__':
#     # Örnek Manga ID'si (örneğin: Solo Leveling)
#     test_manga_id = "c77c9b3b-e14b-4a7c-a870-797c6d857f81"
#     # Örnek Webtoon ID'si (örneğin: Tower of God)
#     test_webtoon_id = "3f65e893-63ff-4a50-9450-c63860917b33"

#     print(f"\n--- Manga Detayları ({test_manga_id}) ---")
#     details_manga = get_manga_details(test_manga_id)
#     if details_manga:
#         print(json.dumps(details_manga, indent=2, ensure_ascii=False))
#     else:
#         print("Manga detayları alınamadı.")

#     print(f"\n--- Webtoon Detayları ({test_webtoon_id}) ---")
#     details_webtoon = get_manga_details(test_webtoon_id)
#     if details_webtoon:
#         print(json.dumps(details_webtoon, indent=2, ensure_ascii=False))
#     else:
#         print("Webtoon detayları alınamadı.")

#     print("\n--- Arama Testi (Örn: 'Solo Leveling') ---")
#     search_results = search_manga("Solo Leveling")
#     if search_results:
#         print(f"{len(search_results)} sonuç bulundu:")
#         print(json.dumps(search_results[:2], indent=2, ensure_ascii=False)) # İlk 2 sonucu göster
#     elif search_results == []:
#         print("Arama sonucu bulunamadı.")
#     else:
#         print("Arama sırasında hata oluştu.")