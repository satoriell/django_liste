# tracker/views/api_views.py
import logging
import uuid

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse, NoReverseMatch

# Modelleri ve Formları import et
from ..models import Anime, Manga, Novel, Webtoon
from ..forms import AnimeForm, MangaForm, NovelForm, WebtoonForm

# Servisleri import et
from ..services import mangadex as mangadex_service
from ..services import jikan as jikan_service

# Yardımcı fonksiyonları import et
from .helpers import _get_existing_mal_ids, _get_existing_mangadex_ids

logger = logging.getLogger(__name__)


# ==============================================================================
# 5. API VE EXPORT VIEW'LARI (API kısmı) - Orijinal views.py'den taşındı
# ==============================================================================

# --- API Arama View'ları (Optimize Edildi) ---
@login_required
def manga_api_search_view(request):
    """MangaDex API ile Manga/Webtoon arar ve sonuçları gösterir."""
    context = {
        'search_results': None, # Arama sonuçları
        'query': request.GET.get('query', None), # Önceki arama sorgusu (varsa)
        'add_item_url_name': 'tracker:md_add_item', # Ekleme linki için URL adı
        'search_title': 'MangaDex API ile Manga/Webtoon Ara',
        'item_type_name': 'Manga/Webtoon',
        'existing_ids_in_db': set() # Listede zaten var olan MangaDex ID'leri (string)
    }
    # POST'tan veya GET'ten gelen sorguyu al
    query = request.POST.get('query', context['query'] or '').strip()

    if request.method == 'POST' and not query:
        messages.warning(request, "Lütfen aramak için bir başlık girin.")
        # Boş arama formuyla template'i tekrar göster
        # === GÜNCELLEME: Template yolu değişti (Kullanıcının belirttiği yol) ===
        return render(request, 'tracker/anime_manga_weptoon_novel_api/manga_api_search.html', context)

    if query: # Eğer bir arama sorgusu varsa
        context['query'] = query # Context'i güncelle
        results = mangadex_service.search_manga(query) # API'dan arama yap

        # API yanıtını işle
        if results is None: # API hatası
            messages.error(request, "MangaDex API'ına bağlanırken bir hata oluştu.")
            context['search_results'] = None
        elif not results: # Sonuç bulunamadı (boş liste)
            context['search_results'] = []
            if request.method == 'POST': # Sadece form gönderildiğinde mesaj göster
                messages.warning(request, f"'{query}' için MangaDex üzerinde sonuç bulunamadı.")
        else: # Sonuç bulundu
            context['search_results'] = results
            if request.method == 'POST':
                messages.success(request, f"'{query}' için {len(results)} sonuç bulundu.")
            # Kullanıcının listesinde zaten var olan ID'leri bul (Optimize Edildi)
            context['existing_ids_in_db'] = _get_existing_mangadex_ids(request, results)

    # Template'i render et
    # === GÜNCELLEME: Template yolu değişti (Kullanıcının belirttiği yol) ===
    return render(request, 'tracker/anime_manga_weptoon_novel_api/manga_api_search.html', context)

@login_required
def anime_api_search_view(request):
    """Jikan API ile Anime arar ve sonuçları gösterir."""
    context = {
        'search_results': None,
        'query': request.GET.get('query', None),
        'add_item_url_name': 'tracker:jikan_add_anime',
        'search_title': 'Jikan API ile Anime Ara',
        'item_type_name': 'Anime',
        'existing_ids_in_db': set() # Listede zaten var olan MAL ID'leri (integer)
    }
    query = request.POST.get('query', context['query'] or '').strip()

    if request.method == 'POST' and not query:
        messages.warning(request, "Lütfen aramak için bir anime başlığı girin.")
        # === GÜNCELLEME: Template yolu değişti (Kullanıcının belirttiği yol) ===
        return render(request, 'tracker/anime_manga_weptoon_novel_api/anime_api_search.html', context)

    if query:
        context['query'] = query
        results = jikan_service.search_anime(query) # Servis fonksiyonunu çağır

        if results is None: # API hatası
            messages.error(request, "Jikan API hatası oluştu veya bağlantı kurulamadı.")
            context['search_results'] = None
        elif not results: # Sonuç yok
            context['search_results'] = []
            if request.method == 'POST':
                 messages.warning(request, f"'{query}' için Jikan (MAL) üzerinde sonuç bulunamadı.")
        else: # Sonuç var
             context['search_results'] = results
             if request.method == 'POST':
                 messages.success(request, f"'{query}' için {len(results)} sonuç bulundu.")
             # Listede var olan MAL ID'lerini bul (Optimize Edildi)
             context['existing_ids_in_db'] = _get_existing_mal_ids(request, results, Anime)

    # === GÜNCELLEME: Template yolu değişti (Kullanıcının belirttiği yol) ===
    return render(request, 'tracker/anime_manga_weptoon_novel_api/anime_api_search.html', context)

@login_required
def novel_api_search_view(request):
    """Jikan API ile Novel arar ve sonuçları gösterir."""
    context = {
        'search_results': None,
        'query': request.GET.get('query', None),
        'add_item_url_name': 'tracker:jikan_add_novel',
        'search_title': 'Jikan API ile Novel Ara',
        'item_type_name': 'Novel',
        'existing_ids_in_db': set() # Listede zaten var olan MAL ID'leri (integer)
    }
    query = request.POST.get('query', context['query'] or '').strip()

    if request.method == 'POST' and not query:
        messages.warning(request, "Lütfen aramak için bir novel başlığı girin.")
        # === GÜNCELLEME: Template yolu değişti (Kullanıcının belirttiği yol) ===
        return render(request, 'tracker/anime_manga_weptoon_novel_api/novel_api_search.html', context)

    if query:
        context['query'] = query
        results = jikan_service.search_novel(query) # Novel arama servisi

        if results is None: # API hatası
            messages.error(request, "Jikan API Novel arama hatası oluştu veya bağlantı kurulamadı.")
            context['search_results'] = None
        elif not results: # Sonuç yok
             context['search_results'] = []
             if request.method == 'POST':
                 messages.warning(request, f"'{query}' için Jikan (MAL) üzerinde Light Novel sonucu bulunamadı.")
        else: # Sonuç var
             context['search_results'] = results
             if request.method == 'POST':
                 messages.success(request, f"'{query}' için {len(results)} novel sonucu bulundu.")
             # Listede var olan MAL ID'lerini bul (Optimize Edildi)
             context['existing_ids_in_db'] = _get_existing_mal_ids(request, results, Novel)

    # === GÜNCELLEME: Template yolu değişti (Kullanıcının belirttiği yol) ===
    return render(request, 'tracker/anime_manga_weptoon_novel_api/novel_api_search.html', context)


# --- API Ekleme View'ları (Optimize Edilmiş Kontroller) ---
@login_required
def md_add_item_view(request, mangadex_id):
    """MangaDex'ten gelen veriyi kullanarak Manga veya Webtoon ekler."""
    try:
        md_id_uuid = uuid.UUID(str(mangadex_id)) # Gelen ID'yi UUID'ye çevir
    except ValueError:
        logger.warning(f"Geçersiz MangaDex ID formatı: {mangadex_id}")
        messages.error(request, "Geçersiz MangaDex ID formatı.")
        return redirect('tracker:manga_api_search') # Arama sayfasına dön

    # 1. API'dan detayları al
    initial_data = mangadex_service.get_manga_details(str(md_id_uuid))
    if initial_data is None:
        messages.error(request, f"MangaDex ID '{md_id_uuid}' için detaylar alınamadı veya bulunamadı.")
        return redirect('tracker:manga_api_search')

    # 2. Tipi belirle (Manga mı Webtoon mu?) ve ilgili Form/Model'i seç
    detected_type = initial_data.get('detected_type', 'MANGA') # Servisten gelen tip
    if detected_type == 'WEBTOON':
        ModelClass, FormClass = Webtoon, WebtoonForm
        name = "Webtoon"
        list_url_name = 'tracker:webtoon_list_view'
        detail_url_name = 'tracker:webtoon_detail'
        # === GÜNCELLEME: Template yolu değişti (Kullanıcının belirttiği yol) ===
        template = 'tracker/anime_manga_weptoon_novel_api/md_form_api.html'
    else: # Varsayılan Manga
        ModelClass, FormClass = Manga, MangaForm
        name = "Manga"
        list_url_name = 'tracker:manga_list_view'
        detail_url_name = 'tracker:manga_detail'
        # === GÜNCELLEME: Template yolu değişti (Kullanıcının belirttiği yol) ===
        template = 'tracker/anime_manga_weptoon_novel_api/md_form_api.html'

    # 3. Bu öğe kullanıcının listesinde zaten var mı kontrol et
    existing_item = ModelClass.objects.filter(mangadex_id=md_id_uuid, user=request.user).first()
    if existing_item:
        messages.info(request, f"'{existing_item.title}' ({name}) zaten listenizde.")
        # Zaten varsa detay sayfasına yönlendir
        try:
            return redirect(reverse(detail_url_name, kwargs={'pk': existing_item.pk}))
        except NoReverseMatch:
             logger.warning(f"MD Add - Var olan öğe için detay URL'i bulunamadı: {detail_url_name}")
             return redirect(list_url_name) # Liste sayfasına dön

    # 4. Formu işle (POST veya GET)
    if request.method == 'POST':
        form = FormClass(request.POST)
        if form.is_valid():
            try:
                instance = form.save(commit=False)
                instance.user = request.user
                instance.mangadex_id = md_id_uuid # MangaDex ID'yi ata
                instance.save()
                # API'dan gelen etiketleri ekle (tags_list servis tarafından sağlanmalı)
                api_tags = initial_data.get('tags_list', [])
                if api_tags:
                    instance.tags.add(*api_tags) # Toplu ekleme
                else:
                     form.save_m2m() # Eğer tags_list yoksa normal save_m2m çağır (formdan gelenler için)

                messages.success(request, f"{name} '{instance.title}' başarıyla eklendi.")
                detail_url = reverse(detail_url_name, kwargs={'pk': instance.pk})
                return redirect(detail_url)
            except NoReverseMatch:
                 logger.error(f"MD Add Item yönlendirme hatası: Detay URL'i '{detail_url_name}' bulunamadı.")
                 messages.warning(request, f"{name} '{instance.title}' eklendi ancak detay sayfasına yönlendirilemedi.")
                 return redirect(list_url_name) # Liste sayfasına dön
            except Exception as e:
                 logger.error(f"MD Add Item kaydetme hatası: {e}", exc_info=True)
                 messages.error(request, "Öğe kaydedilirken bir hata oluştu.")
                 # Hata durumunda formu tekrar göster (hatalarla birlikte)
        else:
            messages.error(request, "Formda hatalar var.")
            # Geçersiz formu template'e gönder
    else: # GET isteği
        # Formu API'dan gelen verilerle doldur
        # Servis içindeki map fonksiyonu initial_data'yı form alanlarına uygun hale getirmeli
        # Etiketleri virgülle ayrılmış string olarak 'tags' anahtarına ekle (form widget'ı için)
        if 'tags_list' in initial_data:
             initial_data['tags'] = ", ".join(initial_data['tags_list'])
        form = FormClass(initial=initial_data)

    # 5. Context'i hazırla ve template'i render et
    context = {
        'form': form,
        'mangadex_data': initial_data, # API verisini teyit için göster
        'model_verbose_name': name # Template başlığı vb. için
    }
    return render(request, template, context)

@login_required
def jikan_add_anime_view(request, mal_id):
    """Jikan'dan gelen veriyi kullanarak Anime ekler."""
    # 1. API'dan detayları al
    initial_data = jikan_service.get_anime_details(mal_id)
    if initial_data is None:
        messages.error(request, f"Anime (MAL ID: {mal_id}) için detaylar alınamadı veya bulunamadı.")
        return redirect('tracker:anime_api_search')

    # Sabitler (Anime için)
    ModelClass, FormClass = Anime, AnimeForm
    name = "Anime"
    list_url_name = 'tracker:anime_list_view'
    detail_url_name = 'tracker:anime_detail'
    # === GÜNCELLEME: Template yolu değişti (Kullanıcının belirttiği yol) ===
    template = 'tracker/anime_manga_weptoon_novel_api/jikan_form_api.html'

    # 2. Bu öğe kullanıcının listesinde zaten var mı kontrol et
    existing_item = ModelClass.objects.filter(mal_id=mal_id, user=request.user).first()
    if existing_item:
        messages.info(request, f"'{existing_item.title}' ({name}) zaten listenizde.")
        try:
            return redirect(reverse(detail_url_name, kwargs={'pk': existing_item.pk}))
        except NoReverseMatch:
            logger.warning(f"Jikan Anime Add - Var olan öğe için detay URL'i bulunamadı: {detail_url_name}")
            return redirect(list_url_name)

    # 3. Formu işle (POST veya GET)
    if request.method == 'POST':
        form = FormClass(request.POST)
        if form.is_valid():
            try:
                instance = form.save(commit=False)
                instance.user = request.user
                instance.mal_id = mal_id # MAL ID'yi ata
                instance.save()
                form.save_m2m() # Etiketleri kaydet
                messages.success(request, f"{name} '{instance.title}' başarıyla eklendi.")
                detail_url = reverse(detail_url_name, kwargs={'pk': instance.pk})
                return redirect(detail_url)
            except NoReverseMatch:
                 logger.error(f"Jikan Anime Add yönlendirme hatası: Detay URL'i '{detail_url_name}' bulunamadı.")
                 messages.warning(request, f"{name} '{instance.title}' eklendi ancak detay sayfasına yönlendirilemedi.")
                 return redirect(list_url_name)
            except Exception as e:
                 logger.error(f"Jikan Anime Add kaydetme hatası: {e}", exc_info=True)
                 messages.error(request, "Öğe kaydedilirken bir hata oluştu.")
        else:
            messages.error(request, "Formda hatalar var.")
    else: # GET
        # Formu API'dan gelen ve maplenmiş verilerle doldur
        form = FormClass(initial=initial_data)

    # 4. Context'i hazırla ve template'i render et
    context = {
        'form': form,
        'api_data': initial_data, # API verisini teyit için göster
        'model_verbose_name': name
    }
    return render(request, template, context)

@login_required
def jikan_add_novel_view(request, mal_id):
    """Jikan'dan gelen veriyi kullanarak Novel ekler."""
    # 1. API'dan detayları al
    initial_data = jikan_service.get_novel_details(mal_id)
    if initial_data is None:
        messages.error(request, f"Novel (MAL ID: {mal_id}) için detaylar alınamadı veya bulunamadı.")
        return redirect('tracker:novel_api_search')

    # Sabitler (Novel için)
    ModelClass, FormClass = Novel, NovelForm
    name = "Novel"
    list_url_name = 'tracker:novel_list_view'
    detail_url_name = 'tracker:novel_detail'
    # === GÜNCELLEME: Template yolu değişti (Kullanıcının belirttiği yol) ===
    template = 'tracker/anime_manga_weptoon_novel_api/jikan_novel_form_api.html'

    # 2. Bu öğe kullanıcının listesinde zaten var mı kontrol et
    existing_item = ModelClass.objects.filter(mal_id=mal_id, user=request.user).first()
    if existing_item:
        messages.info(request, f"'{existing_item.title}' ({name}) zaten listenizde.")
        try:
            return redirect(reverse(detail_url_name, kwargs={'pk': existing_item.pk}))
        except NoReverseMatch:
             logger.warning(f"Jikan Novel Add - Var olan öğe için detay URL'i bulunamadı: {detail_url_name}")
             return redirect(list_url_name)

    # 3. Formu işle (POST veya GET)
    if request.method == 'POST':
        form = FormClass(request.POST)
        if form.is_valid():
            try:
                instance = form.save(commit=False)
                instance.user = request.user
                instance.mal_id = mal_id # MAL ID'yi ata
                instance.save()
                form.save_m2m() # Etiketleri kaydet
                messages.success(request, f"{name} '{instance.title}' başarıyla eklendi.")
                detail_url = reverse(detail_url_name, kwargs={'pk': instance.pk})
                return redirect(detail_url)
            except NoReverseMatch:
                 logger.error(f"Jikan Novel Add yönlendirme hatası: Detay URL'i '{detail_url_name}' bulunamadı.")
                 messages.warning(request, f"{name} '{instance.title}' eklendi ancak detay sayfasına yönlendirilemedi.")
                 return redirect(list_url_name)
            except Exception as e:
                 logger.error(f"Jikan Novel Add kaydetme hatası: {e}", exc_info=True)
                 messages.error(request, "Öğe kaydedilirken bir hata oluştu.")
        else:
            messages.error(request, "Formda hatalar var.")
    else: # GET
        # Formu API'dan gelen ve maplenmiş verilerle doldur
        form = FormClass(initial=initial_data)

    # 4. Context'i hazırla ve template'i render et
    context = {
        'form': form,
        'api_data': initial_data, # API verisini teyit için göster
        'model_verbose_name': name
    }
    return render(request, template, context)