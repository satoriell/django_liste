# tracker/views.py
# Konum: /home/admin/App/django_liste/tracker/views.py
# Kapsamlı Refactoring: Yardımcı fonksiyonlar, query optimizasyonu, logging, hata yönetimi.
# GÜNCELLEME: API şablon yolları kullanıcı tarafından belirtilen
# 'tracker/anime_manga_weptoon_novel_api/' altına göre güncellendi.

import csv
import datetime
import json
import logging
import uuid # MangaDex ID için

from django.apps import apps # Model class'ı dinamik almak için (opsiyonel)
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm # signup_view için
from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Count, F, Q # F() sıralama için, Q() karmaşık sorgular için (şu an kullanılmıyor)
from django.http import HttpResponse, JsonResponse, Http404
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse, NoReverseMatch
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from taggit.models import Tag # Etiketler için

# Formları import et
from .forms import AnimeForm, MangaForm, NovelForm, WebtoonForm

# Modelleri import et
from .models import Anime, Manga, Novel, Webtoon, Favorite

# --- Servisleri import et ---
from . import mangadex_service
from . import jikan_service
# ---------------------------

# Logging yapılandırması (settings.py'den alır)
logger = logging.getLogger(__name__)


# ==============================================================================
# 1. YARDIMCI FONKSİYONLAR (HELPERS)
# ==============================================================================

# --- Sıralama ---
def apply_sorting(queryset, sort_by_param, default_sort="-added_date"):
    """Verilen queryset'i belirtilen parametreye göre sıralar."""
    valid_sort_options = {
        "title_asc": "title", "title_desc": "-title",
        "rating_asc": "rating", "rating_desc": "-rating", # F() ile null kontrolü aşağıda
        "date_asc": "added_date", "date_desc": "-added_date",
    }
    order_field = valid_sort_options.get(sort_by_param, default_sort)

    # Rating'e göre sıralarken null değerleri sona at (F objesi ile)
    if order_field == "rating_desc":
        # Önce rating'e göre azalan (null'lar sonda), sonra eklenme tarihine göre azalan
        return queryset.order_by(F("rating").desc(nulls_last=True), "-added_date")
    elif order_field == "rating_asc":
        # Önce rating'e göre artan (null'lar sonda), sonra eklenme tarihine göre azalan
        return queryset.order_by(F("rating").asc(nulls_last=True), "-added_date")
    else:
        # Diğer alanlar için normal sıralama
        return queryset.order_by(order_field)

# --- Filtreleme/Arama (İlişkili Verilerle - Optimize Edildi) ---
def _get_filtered_queryset(request, model):
    """
    İstek parametrelerine göre queryset'i filtreler, arama yapar ve
    ilişkili verileri (user, tags) verimli bir şekilde önceden yükler.
    """
    status_filter = request.GET.get("status", "")
    search_query = request.GET.get("q", "").strip()
    tag_filter = request.GET.get("tag", "") # Etiket slug'ı

    # Temel queryset: Sadece mevcut kullanıcıya ait olanlar
    # select_related('user'): Her öğe için user sorgusunu önler.
    # prefetch_related('tags'): Her öğe için tags sorgusunu önler.
    queryset = model.objects.select_related('user').prefetch_related('tags').filter(user=request.user)

    # Filtreleri uygula
    if status_filter:
        queryset = queryset.filter(status=status_filter)
    if tag_filter:
        # Etikete göre filtreleme (taggit slug alanını kullanır)
        queryset = queryset.filter(tags__slug=tag_filter)
    if search_query:
        # Başlıkta büyük/küçük harf duyarsız arama
        queryset = queryset.filter(title__icontains=search_query)

    return queryset, status_filter, search_query, tag_filter

# --- Sayfalama ---
def _paginate_queryset(request, queryset, paginate_by):
    """Queryset'i sayfalar."""
    paginator = Paginator(queryset, paginate_by)
    page_number = request.GET.get("page")
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        # Sayfa numarası integer değilse ilk sayfayı göster
        page_obj = paginator.page(1)
    except EmptyPage:
        # Sayfa numarası aralık dışındaysa son sayfayı göster
        page_obj = paginator.page(paginator.num_pages)
    return page_obj, paginator

# --- Form İşleme (Create - Optimize Edildi) ---
def _handle_create_form(request, form_class, model, redirect_url_name):
    """POST isteğinde yeni öğe oluşturma formunu işler."""
    if request.method == "POST":
        form = form_class(request.POST)
        if form.is_valid():
            try:
                instance = form.save(commit=False)
                instance.user = request.user # Kullanıcıyı ata
                instance.save() # Ana objeyi kaydet
                form.save_m2m() # ManyToMany alanlarını (tags gibi) kaydet
                messages.success(request, f'{model._meta.verbose_name.capitalize()} "{instance.title}" başarıyla eklendi.')
                return redirect(redirect_url_name), None # Başarılı, yönlendir
            except Exception as e:
                 # Kaydetme sırasında bir hata oluşursa logla ve kullanıcıya bildir
                 logger.error(f"'{model._meta.verbose_name}' oluşturulurken hata: {e}", exc_info=True)
                 messages.error(request, "Öğe kaydedilirken beklenmedik bir hata oluştu. Lütfen tekrar deneyin.")
                 return None, form # Başarısız, formu hatalarla geri döndür
        else:
            # Form geçerli değilse kullanıcıya bildir
            messages.error(request, "Formda hatalar var. Lütfen işaretli alanları kontrol edin.")
            return None, form # Başarısız, formu hatalarla geri döndür
    # GET isteği ise veya form geçersizse boş form döndür
    return None, form_class()

# --- Context Oluşturma (Listeleme - Optimize Edildi) ---
def _build_list_context(request, page_obj, paginator, form, model, filters, sort_by, item_type_lower):
    """Liste görünümü için context sözlüğünü oluşturur."""
    status_filter, search_query, tag_filter = filters
    # Sayfalama linkleri için mevcut GET parametrelerini koru (page hariç)
    existing_params = request.GET.copy()
    existing_params.pop("page", None)
    params_encoded = existing_params.urlencode()

    # Mevcut sayfadaki öğelerin favori durumunu tek sorguyla al
    favorited_pks = _get_favorited_pks(request, model, page_obj.object_list if page_obj else [])

    # Kullanıcının bu model türü için kullandığı tüm etiketleri al (filtreleme için)
    all_tags = _get_all_user_tags(request.user, model)

    # Varsa API arama URL'ini al
    api_search_url = _get_api_search_url(item_type_lower)

    context = {
        "page_obj": page_obj, # Sayfalanmış öğeler
        "paginator": paginator, # Sayfalama bilgisi
        "form": form, # Yeni öğe ekleme formu
        "status_choices": model.STATUS_CHOICES, # Durum filtreleme seçenekleri
        "current_status_filter": status_filter, # Seçili durum filtresi
        "search_query": search_query, # Arama sorgusu
        "current_tag_filter": tag_filter, # Seçili etiket filtresi
        "all_tags": all_tags, # Tüm etiketler (filtreleme için)
        "current_sort": sort_by, # Mevcut sıralama
        "params_encoded": params_encoded, # Sayfalama için GET parametreleri
        "model_name_plural": model._meta.verbose_name_plural.capitalize(), # Modelin çoğul adı (örn: Animeler)
        "favorited_pks": favorited_pks, # Template'de favori butonunu işaretlemek için
        "item_type_str": item_type_lower, # Model adının küçük harfli hali (örn: anime)
        "list_url_name": f'tracker:{item_type_lower}_list_view', # Liste view'ının URL adı
        "export_url_name": f"tracker:export_{item_type_lower}_csv", # CSV export URL adı
        "api_search_url": api_search_url, # API arama view'ının URL'i (varsa)
    }
    return context

# --- Yardımcı: Favori PK'ları Alma (Optimize Edildi) ---
def _get_favorited_pks(request, model, items_list):
    """Verilen öğe listesi için kullanıcının favori PK'larını tek sorguyla döndürür."""
    favorited_pks = set()
    if request.user.is_authenticated and items_list:
        item_ids = [item.pk for item in items_list]
        if not item_ids: # Eğer liste boşsa sorgu yapma
            return favorited_pks
        try:
            content_type = ContentType.objects.get_for_model(model)
            # Tek bir sorguyla mevcut sayfadaki favori ID'lerini al
            favorited_pks = set(
                Favorite.objects.filter(
                    user=request.user,
                    content_type=content_type,
                    object_id__in=item_ids # Sadece bu ID'ler içinde ara
                ).values_list('object_id', flat=True) # Sadece ID'leri al
            )
        except ContentType.DoesNotExist:
            logger.warning(f"Favori PK'ları alınamadı: Model '{model.__name__}' için ContentType bulunamadı.")
        except Exception as e:
            logger.error(f"Favori PK'ları alınırken hata: {e}", exc_info=True)
    return favorited_pks

# --- Yardımcı: Kullanıcı Etiketleri Alma (Optimize Edildi) ---
def _get_all_user_tags(user, model):
    """Belirli bir model türü için kullanıcının tüm etiketlerini (Tag nesneleri) döndürür."""
    try:
        # Kullanıcının ilgili modeldeki tüm öğelerinin etiket ID'lerini al
        tag_pks = model.objects.filter(user=user, tags__isnull=False).values_list('tags', flat=True).distinct()
        # Bu ID'lere sahip Tag nesnelerini tek sorguyla getir
        return Tag.objects.filter(pk__in=tag_pks).order_by('name')
    except Exception as e:
        logger.error(f"Kullanıcı etiketleri alınırken hata (Model: {model.__name__}): {e}", exc_info=True)
        return Tag.objects.none() # Hata durumunda boş QuerySet dön

# --- Yardımcı: API Arama URL'ini Alma ---
def _get_api_search_url(item_type_lower):
    """Verilen öğe türü için ilgili API arama view'ının URL'ini döndürür."""
    try:
        # Manga ve Webtoon için ortak MangaDex arama view'ı kullanılır
        if item_type_lower in ['manga', 'webtoon']:
            search_view_name = 'tracker:manga_api_search'
        # Anime ve Novel için kendi Jikan arama view'ları
        elif item_type_lower in ['anime', 'novel']:
            search_view_name = f'tracker:{item_type_lower}_api_search'
        else:
            return None # Diğer tipler için API araması yok

        return reverse(search_view_name)
    except NoReverseMatch:
        logger.warning(f"API arama URL'i bulunamadı: '{search_view_name}'")
        return None
    except Exception as e:
        logger.error(f"API Arama URL hatası ({item_type_lower}): {e}", exc_info=True)
        return None

# --- Yardımcı: Öğeyi Güvenli Alma (Optimize Edildi) ---
def _get_item_or_404(model, pk, user=None, prefetch_fields=None, select_fields=None):
    """
    Öğeyi alır veya 404 döndürür. İsteğe bağlı olarak kullanıcıya göre filtreler
    ve ilişkili alanları verimli bir şekilde yükler (prefetch/select).
    """
    queryset = model.objects
    if select_fields: # ForeignKey alanları için
        queryset = queryset.select_related(*select_fields)
    if prefetch_fields: # ManyToMany veya GenericForeignKey alanları için
        queryset = queryset.prefetch_related(*prefetch_fields)

    filter_kwargs = {'pk': pk}
    if user: # Eğer kullanıcı belirtilmişse, sadece o kullanıcıya ait olanı getir
        filter_kwargs['user'] = user

    try:
        # get() ile tek bir nesne almayı dene
        return queryset.get(**filter_kwargs)
    except model.DoesNotExist:
        # Nesne bulunamazsa veya kullanıcıya ait değilse 404 hatası fırlat
        logger.warning(f"{model._meta.verbose_name} bulunamadı veya erişim yetkisi yok: PK={pk}, User={user.username if user else 'Yok'}")
        raise Http404(f"{model._meta.verbose_name} bulunamadı.")
    except Exception as e:
        # Beklenmedik bir hata olursa logla ve 404 fırlat
        logger.error(f"Öğe alınırken hata: Model={model.__name__}, PK={pk}, User={user.username if user else 'Yok'} - {e}", exc_info=True)
        raise Http404("Öğe alınırken sunucu hatası oluştu.")

# --- Yardımcı: Formu Kaydetme (Edit - Optimize Edildi) ---
def _handle_edit_form(request, instance, form_class, model):
    """POST isteğinde düzenleme formunu işler."""
    form = form_class(request.POST, instance=instance)
    if form.is_valid():
        try:
            saved_instance = form.save() # save_m2m otomatik çağrılır (tags için)
            messages.success(request, f'{model._meta.verbose_name.capitalize()} "{saved_instance.title}" başarıyla güncellendi.')
            # Başarılı güncelleme sonrası detay sayfasına yönlendir
            detail_url_name = f'tracker:{model.__name__.lower()}_detail'
            detail_url = reverse(detail_url_name, kwargs={'pk': saved_instance.pk})
            return redirect(detail_url), None
        except NoReverseMatch:
             # Eğer detay URL'i bulunamazsa (bir hata olmuşsa), liste sayfasına yönlendir
             logger.warning(f"Detay URL'i bulunamadı: '{detail_url_name}'. Liste sayfasına yönlendiriliyor.")
             list_url_name = f'tracker:{model.__name__.lower()}_list_view'
             try:
                 return redirect(reverse(list_url_name)), None
             except NoReverseMatch: # Liste URL'i de bulunamazsa dashboard'a
                 logger.error(f"Liste URL'i de bulunamadı: '{list_url_name}'. Dashboard'a yönlendiriliyor.")
                 return redirect('tracker:dashboard'), None
        except Exception as e:
             # Güncelleme sırasında hata olursa logla ve kullanıcıya bildir
             logger.error(f"'{model._meta.verbose_name}' güncellenirken hata (ID: {instance.pk}): {e}", exc_info=True)
             messages.error(request, "Öğe güncellenirken beklenmedik bir hata oluştu.")
             return None, form # Hatalı formu geri döndür
    else:
        # Form geçerli değilse kullanıcıya bildir
        messages.error(request, "Formda hatalar var. Lütfen işaretli alanları kontrol edin.")
        return None, form # Hatalı formu geri döndür

# --- Yardımcı: Favori Durumunu Al (Optimize Edildi) ---
def _get_favorite_status(request, item):
    """Verilen öğenin mevcut kullanıcı için favori olup olmadığını kontrol eder."""
    is_favorite = False
    if request.user.is_authenticated and item: # item None değilse
        try:
            content_type = ContentType.objects.get_for_model(item.__class__)
            # exists() kullanmak, sadece var olup olmadığını kontrol etmek için daha verimlidir
            is_favorite = Favorite.objects.filter(
                user=request.user,
                content_type=content_type,
                object_id=item.pk
            ).exists()
        except ContentType.DoesNotExist:
            logger.warning(f"Favori durumu kontrolü: Model '{item.__class__.__name__}' için ContentType bulunamadı.")
        except Exception as e:
            logger.error(f"Favori durumu kontrol hatası (PK: {item.pk}, Type: {item.__class__.__name__}): {e}", exc_info=True)
    return is_favorite

# --- Yardımcı: CSV Satırı Oluşturma (Optimize Edildi) ---
def _build_csv_row(item, fields_map):
    """
    Verilen öğe ve alan haritası için bir CSV satırı (liste) oluşturur.
    İlişkili alanları ve etiketleri verimli bir şekilde alır (prefetch edildiği varsayılır).
    """
    row = []
    for field_name in fields_map.keys():
        value = "" # Varsayılan değer
        try:
            if field_name == 'get_status_display':
                value = item.get_status_display() # Model metodu
            elif field_name == 'tags':
                # .tags.all() yerine prefetch edilmiş _prefetched_objects_cache kullanılır (varsa)
                # Bu sayede her satır için ek sorgu yapılmaz
                try:
                    # Prefetch edilmiş etiketleri al (performanslı)
                    tags_qs = getattr(item, '_prefetched_objects_cache', {}).get('tags')
                    if tags_qs is not None: # Prefetch edilmişse
                         value = ", ".join(t.name for t in tags_qs)
                    else: # Prefetch edilmemişse (fallback, daha yavaş olabilir)
                        value = ", ".join(t.name for t in item.tags.all())
                except Exception as tag_err:
                    logger.warning(f"CSV: Etiket alınamadı (PK: {item.pk}) - {tag_err}")
                    value = ""
            elif field_name in ['mal_id', 'mangadex_id'] and hasattr(item, field_name):
                # UUID veya None ise string'e çevir
                attr_value = getattr(item, field_name, None)
                value = str(attr_value) if attr_value is not None else ""
            elif '__' in field_name: # İlişkili alan (örn: user__username)
                # select_related ile önceden yüklendiği varsayılır
                related_attrs = field_name.split('__')
                related_obj = item
                for i, attr in enumerate(related_attrs):
                    try:
                        related_obj = getattr(related_obj, attr, None)
                    except Exception as related_err:
                        logger.warning(f"CSV: İlişkili alan hatası (PK: {item.pk}, Field: {field_name}) - {related_err}")
                        related_obj = None
                        break # İç içe objelerde hata olursa devam etme
                    if related_obj is None: # Eğer ilişki boşsa (örn: user=None)
                        break
                value = str(related_obj) if related_obj is not None else ""
            else:
                # Doğrudan model alanı
                value = getattr(item, field_name, "")

            # Formatlama
            if isinstance(value, datetime.datetime):
                # Timezone farkındalığı olan datetime'ı local time'a çevir
                value = timezone.localtime(value).strftime("%Y-%m-%d %H:%M:%S") if value else ""
            elif isinstance(value, datetime.date):
                value = value.strftime("%Y-%m-%d") if value else ""
            elif isinstance(value, uuid.UUID):
                 value = str(value) # UUID'leri string yap
            elif value is None:
                value = "" # None değerleri boş string yap
        except Exception as e:
            logger.error(f"CSV Satır Oluşturma Hatası (PK: {item.pk}, Alan: {field_name}): {e}", exc_info=False) # Genelde traceback gereksiz
            value = "HATA" # Hata durumunda belirt
        row.append(str(value)) # Her değeri string'e çevir
    return row

# --- YENİ Yardımcı: API Sonuçlarından DB'de Olan MAL ID'leri Bulma (Optimize Edildi) ---
def _get_existing_mal_ids(request, results, model_class):
    """Jikan API sonuçlarındaki MAL ID'lerden hangilerinin kullanıcının DB'sinde olduğunu tek sorguyla bulur."""
    existing_ids = set()
    if results and request.user.is_authenticated:
        # API sonuçlarından geçerli (integer) MAL ID'lerini topla
        api_mal_ids = [result.get('mal_id') for result in results if isinstance(result.get('mal_id'), int)]
        if api_mal_ids:
            # Tek bir sorguyla kullanıcının listesindeki bu ID'leri bul
            existing_ids = set(model_class.objects.filter(
                user=request.user,
                mal_id__in=api_mal_ids # __in filtresi ile toplu kontrol
            ).values_list('mal_id', flat=True)) # Sadece ID'leri al
    return existing_ids

# --- YENİ Yardımcı: API Sonuçlarından DB'de Olan MangaDex ID'leri Bulma ---
def _get_existing_mangadex_ids(request, results):
    """MangaDex API sonuçlarındaki UUID'lerden hangilerinin kullanıcının Manga/Webtoon listelerinde olduğunu bulur."""
    existing_ids_str = set()
    if results and request.user.is_authenticated:
        # API sonuçlarından geçerli UUID string'lerini topla
        api_md_ids_str = {str(r.get('id')) for r in results if r.get('id')}
        valid_uuids = set()
        for id_str in api_md_ids_str:
            try:
                valid_uuids.add(uuid.UUID(id_str))
            except ValueError:
                logger.warning(f"Geçersiz MangaDex UUID formatı: {id_str}")
                continue # Geçersiz formatı atla

        if valid_uuids:
            # Tek sorguyla Manga listesindekileri bul
            existing_manga_uuids = set(Manga.objects.filter(
                user=request.user,
                mangadex_id__in=valid_uuids
            ).values_list('mangadex_id', flat=True))

            # Tek sorguyla Webtoon listesindekileri bul
            existing_webtoon_uuids = set(Webtoon.objects.filter(
                user=request.user,
                mangadex_id__in=valid_uuids
            ).values_list('mangadex_id', flat=True))

            # İki kümenin birleşimini al ve string'e çevir
            existing_ids_str = {str(uid) for uid in existing_manga_uuids.union(existing_webtoon_uuids)}

    return existing_ids_str


# ==============================================================================
# 2. GENEL VIEW İŞLEYİCİLERİ (PROCESSORS using Helpers)
# ==============================================================================

@login_required
def _process_list_view(request, model, form_class, template_name, redirect_url_name, paginate_by=15):
    """Listeleme ve oluşturma görünümünü işler (Refactored)."""
    # 1. Filtrelenmiş ve ilişkili verileri yüklenmiş queryset'i al
    queryset, status_filter, search_query, tag_filter = _get_filtered_queryset(request, model)
    filters = (status_filter, search_query, tag_filter) # Context için filtreleri paketle

    # 2. Sıralamayı uygula
    sort_by = request.GET.get("sort", "-added_date") # Varsayılan sıralama
    queryset = apply_sorting(queryset, sort_by)

    # 3. Sayfalamayı yap
    page_obj, paginator = _paginate_queryset(request, queryset, paginate_by)

    # 4. Eğer POST isteği ise, yeni öğe oluşturma formunu işle
    redirect_response, form = _handle_create_form(request, form_class, model, redirect_url_name)
    if redirect_response:
        return redirect_response # Başarılı oluşturma sonrası yönlendirme

    # 5. Template için context'i oluştur
    item_type_lower = model.__name__.lower()
    context = _build_list_context(request, page_obj, paginator, form, model, filters, sort_by, item_type_lower)

    # 6. Template'i render et
    return render(request, template_name, context)

@login_required
def _process_edit_view(request, pk, model, form_class, template_name):
    """Düzenleme görünümünü işler (Refactored)."""
    # 1. Öğeyi getir (veya 404) - Sadece kullanıcıya ait olanı
    # prefetch_fields=['tags'] taggit için ManyToMany ilişkisini optimize eder
    instance = _get_item_or_404(model, pk, user=request.user, prefetch_fields=['tags'])
    name = model._meta.verbose_name.capitalize() # Model adını al (örn: Anime)
    list_url_name = f'tracker:{model.__name__.lower()}_list_view' # Geri dönülecek liste URL'i

    # 2. Eğer POST isteği ise, düzenleme formunu işle
    if request.method == "POST":
        redirect_response, form = _handle_edit_form(request, instance, form_class, model)
        if redirect_response:
            return redirect_response # Başarılı güncelleme sonrası yönlendirme
    else:
        # GET isteği ise, formu mevcut instance ile doldur
        form = form_class(instance=instance)

    # 3. Template için context'i oluştur
    try:
        # "İptal" butonu için liste URL'ini template'e gönder
        list_url_for_template = reverse(list_url_name)
    except NoReverseMatch:
        logger.warning(f"Düzenleme formu için liste URL'i bulunamadı: '{list_url_name}'. Dashboard'a yönlendirilecek.")
        list_url_for_template = reverse('tracker:dashboard')

    context = {
        "form": form,
        "item": instance, # Mevcut öğe (örn: form başlığında kullanmak için)
        "model_name": name, # Model adı (örn: Anime)
        "list_url_name": list_url_for_template # İptal butonu için
    }

    # 4. Template'i render et
    return render(request, template_name, context)

@login_required
def _process_delete_view(request, pk, model, redirect_url_name):
    """Silme görünümünü işler (Refactored - item_type eklendi)."""
    # 1. Öğeyi getir (veya 404) - Sadece kullanıcıya ait olanı
    instance = _get_item_or_404(model, pk, user=request.user)
    name = model._meta.verbose_name.capitalize() # Model adı (örn: Anime)
    item_type = model.__name__.lower() # Model adının küçük harfi (örn: anime) -> **YENİ EKLENDİ**

    # 2. Eğer POST isteği ise (silme onaylandıysa), silme işlemini yap
    if request.method == "POST":
        try:
            title = instance.title # Silme mesajı için başlığı sakla
            instance.delete()
            messages.success(request, f'{name} "{title}" başarıyla silindi.')
            # Başarılı silme sonrası liste sayfasına yönlendir
            list_url = reverse(redirect_url_name)
            return redirect(list_url)
        except NoReverseMatch:
             logger.error(f"Silme yönlendirme hatası: Liste URL'i '{redirect_url_name}' bulunamadı.")
             messages.warning(request, f'{name} "{title}" silindi ancak liste sayfasına yönlendirilemedi.')
             return redirect('tracker:dashboard') # Dashboard'a yönlendir
        except Exception as e:
             logger.error(f"'{name}' silinirken hata (ID: {pk}): {e}", exc_info=True)
             messages.error(request, "Öğe silinirken beklenmedik bir hata oluştu.")
             # Hata sonrası liste sayfasına yönlendirmeyi dene
             try:
                 return redirect(reverse(redirect_url_name))
             except NoReverseMatch:
                 return redirect('tracker:dashboard')

    # 3. GET isteği ise, onay sayfasını göster
    context = {
        "item": instance, # Silinecek öğe (başlığını göstermek için)
        "model_name": name, # Model adı (örn: Anime)
        "item_type": item_type # -> **YENİ EKLENDİ** (Template'in URL oluşturması için)
    }
    # Ortak silme onay template'ini kullan
    return render(request, "tracker/confirm_delete_base.html", context)

@login_required
def _render_detail_view(request, pk, model):
    """Detay görünümünü oluşturur (Refactored)."""
    # 1. Öğeyi getir (veya 404) - Herkese açık olabilir, user=None
    # İlişkili alanları (user, tags) önceden yükle
    instance = _get_item_or_404(model, pk, user=None, prefetch_fields=['tags'], select_fields=['user'])
    name_lower = model.__name__.lower() # Model adının küçük harfi (örn: anime)
    model_name_display = model._meta.verbose_name.capitalize() # Modelin gösterim adı (örn: Anime)

    # 2. Favori durumunu kontrol et
    is_favorite = _get_favorite_status(request, instance)

    # 3. Kullanıcının öğenin sahibi olup olmadığını kontrol et (düzenle/sil butonları için)
    is_owner = request.user.is_authenticated and request.user == instance.user

    # 4. Geri dönülecek liste URL'ini al (breadcrumb ve etiket linkleri için)
    try:
        list_url_base = reverse(f'tracker:{name_lower}_list_view')
    except NoReverseMatch:
        logger.warning(f"Detay sayfası için liste URL'i bulunamadı: 'tracker:{name_lower}_list_view'")
        list_url_base = None # Bulunamadıysa None ata

    # 5. Template için context'i oluştur
    context = {
        "item": instance, # Detayları gösterilecek öğe
        "model_name": model_name_display, # Başlıkta vb. kullanmak için
        "item_type": name_lower, # Favori butonu vb. için
        "is_favorite": is_favorite, # Favori butonunun durumunu belirlemek için
        "is_owner": is_owner, # Düzenle/Sil butonlarını göstermek için
        "list_url_base": list_url_base # Breadcrumb ve etiket linkleri için
    }

    # 6. Ortak detay template'ini render et
    return render(request, "tracker/detail_base.html", context)

# --- Yeniden Düzenlenmiş _export_csv ---
@login_required
def _export_csv(request, model, filename_prefix, fields_map):
    """Verileri CSV olarak dışa aktarır (Refactored & Optimized)."""
    # 1. Filtrelenmiş queryset'i al (_get_filtered_queryset zaten select/prefetch yapıyor)
    queryset, status_filter, search_query, tag_filter = _get_filtered_queryset(request, model)

    # 2. HTTP yanıtını hazırla (CSV formatı ve dosya adı)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    # UTF-8 BOM (Byte Order Mark) ekleyerek Excel uyumluluğunu artır
    response.write("\ufeff".encode("utf8"))
    timestamp = timezone.localtime(timezone.now()).strftime("%Y%m%d_%H%M")
    filename_suffix = ""
    if status_filter: filename_suffix += f"_durum-{status_filter.replace(' ', '_')}"
    if tag_filter: filename_suffix += f"_etiket-{tag_filter}"
    if search_query: filename_suffix += f"_arama-{search_query[:15].replace(' ','_').replace('.','')}" # Max 15 char, boşlukları değiştir
    filename = f"{filename_prefix}_export_{timestamp}{filename_suffix}.csv"
    # Dosya adını güvenli hale getir (tarayıcıların yorumlamasını engellemek için)
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    # 3. CSV yazıcısını oluştur ve başlık satırını yaz
    writer = csv.writer(response, delimiter=";", quotechar='"', quoting=csv.QUOTE_MINIMAL)
    writer.writerow(list(fields_map.values())) # fields_map'in value'ları başlıklar

    # 4. Verileri işle ve satırları yaz
    # CSV için ek prefetch/select (user/tags zaten _get_filtered_queryset'te var)
    # Örn: fields_map'te 'category__name' varsa, 'category' select_related edilmeli
    related_fields_to_select = set()
    related_fields_to_prefetch = set() # Örn: GenericForeignKey veya başka ManyToMany
    for field_name in fields_map.keys():
        if '__' in field_name and field_name != 'user__username' and field_name != 'get_status_display':
            # Şu an sadece user select_related ediliyor, diğerleri gerekirse eklenebilir.
            # base_field = field_name.split('__')[0]
            # if base_field != 'tags': # tags zaten prefetch ediliyor
                 # related_fields_to_select.add(base_field) # Gerekirse aktive et
            pass

    if related_fields_to_select:
        try: queryset = queryset.select_related(*related_fields_to_select)
        except Exception as e: logger.warning(f"CSV Export ek select_related hatası ({model.__name__}): {e}")
    if related_fields_to_prefetch:
         try: queryset = queryset.prefetch_related(*related_fields_to_prefetch)
         except Exception as e: logger.warning(f"CSV Export ek prefetch_related hatası ({model.__name__}): {e}")

    # Veritabanından tüm sonuçları tek seferde çekmek yerine
    # .iterator() kullanarak belleği daha verimli kullan (çok büyük listeler için)
    # Ancak prefetch_related ile iterator kullanımı uyumsuz olabilir, dikkat!
    # Şimdilik normal queryset üzerinde döngüye girelim.
    # Belirli bir sıra önemliyse burada order_by eklenebilir.
    queryset = queryset.order_by("-added_date", "title") # Tutarlı bir sıra olsun

    for item in queryset:
        row = _build_csv_row(item, fields_map) # Yardımcı fonksiyonu kullan
        writer.writerow(row)

    # 5. Yanıtı döndür
    return response


# ==============================================================================
# 3. ANA VIEW FONKSİYONLARI (Dashboard, Signup, Favorites, Toggle)
# ==============================================================================

@login_required
def dashboard_view(request):
    """Dashboard görünümünü oluşturur (Optimize Edilmiş Sorgular)."""
    user = request.user
    # Toplam sayıları al (count() genellikle verimlidir)
    anime_count = Anime.objects.filter(user=user).count()
    webtoon_count = Webtoon.objects.filter(user=user).count()
    manga_count = Manga.objects.filter(user=user).count()
    novel_count = Novel.objects.filter(user=user).count()

    # Son eklenenler (select_related('user') gereksiz, sadece title/pk lazım olabilir ama ekleyelim)
    # Sadece 5 öğe alınıyor, performans etkisi düşük.
    recent_anime = Anime.objects.filter(user=user).order_by("-added_date")[:5]
    recent_webtoons = Webtoon.objects.filter(user=user).order_by("-added_date")[:5]
    recent_mangas = Manga.objects.filter(user=user).order_by("-added_date")[:5]
    recent_novels = Novel.objects.filter(user=user).order_by("-added_date")[:5]

    # En yüksek puanlılar (apply_sorting helper'ını kullan)
    # Rating null olmayanları filtrele
    top_anime = apply_sorting(Anime.objects.filter(user=user, rating__isnull=False), "rating_desc")[:5]
    top_webtoons = apply_sorting(Webtoon.objects.filter(user=user, rating__isnull=False), "rating_desc")[:5]
    top_mangas = apply_sorting(Manga.objects.filter(user=user, rating__isnull=False), "rating_desc")[:5]
    top_novels = apply_sorting(Novel.objects.filter(user=user, rating__isnull=False), "rating_desc")[:5]

    # Grafik verileri (Mevcut aggregation sorguları genellikle verimlidir)
    type_labels = ["Anime", "Webtoon", "Manga", "Novel"]
    type_counts = [anime_count, webtoon_count, manga_count, novel_count]
    status_choices = Anime.STATUS_CHOICES # Tüm modeller için aynı
    status_counts_dict = {value: 0 for value, _ in status_choices}

    # Tüm modellerdeki durum sayılarını topla
    all_models = [Anime, Webtoon, Manga, Novel]
    for model in all_models:
        # Tek sorguyla model başına durum sayılarını al
        counts = model.objects.filter(user=user).values("status").annotate(count=Count("id")).order_by("status")
        for item in counts:
            if item["status"] in status_counts_dict:
                status_counts_dict[item["status"]] += item["count"]

    status_labels = [display for _, display in status_choices]
    status_data = [status_counts_dict[value] for value, _ in status_choices]
    chart_data = {
        "typeLabels": type_labels, "typeCounts": type_counts,
        "statusLabels": status_labels, "statusData": status_data
    }

    context = {
        "anime_count": anime_count, "webtoon_count": webtoon_count,
        "manga_count": manga_count, "novel_count": novel_count,
        "recent_anime": recent_anime, "recent_webtoons": recent_webtoons,
        "recent_mangas": recent_mangas, "recent_novels": recent_novels,
        "top_anime": top_anime, "top_webtoons": top_webtoons,
        "top_mangas": top_mangas, "top_novels": top_novels,
        "chart_data_json": json.dumps(chart_data) # JSON'ı template'e güvenli gönder
    }
    return render(request, "tracker/dashboard.html", context)

# Signup View (Genellikle değişmez)
def signup_view(request):
    """Yeni kullanıcı kayıt işlemini yapar."""
    if request.user.is_authenticated:
        # Zaten giriş yapmışsa dashboard'a yönlendir
        return redirect('tracker:dashboard')

    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save() # Kullanıcıyı kaydet
            username = form.cleaned_data.get('username')
            messages.success(request, f'Hesap "{username}" başarıyla oluşturuldu! Giriş yapabilirsiniz.')
            return redirect('login') # Login sayfasına yönlendir
        else:
            # Form hatalıysa mesaj göster (template zaten hataları gösterecek)
             messages.error(request, 'Lütfen formdaki hataları düzeltin.')
    else:
        # GET isteği ise boş formu göster
        form = UserCreationForm()
    return render(request, 'registration/signup.html', {'form': form})

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

# Favoriler Listesi (Optimize Edildi)
@login_required
def favorites_view(request):
    """Kullanıcının favori öğelerini gruplanmış olarak listeler."""
    # 1. Kullanıcının tüm favorilerini ve ilişkili content_type'ları tek sorguyla al
    user_favorites = Favorite.objects.filter(user=request.user).select_related('content_type')

    # 2. Favorileri content type'a göre grupla (Python içinde)
    fav_ids_by_type = {}
    for fav in user_favorites:
        # fav.content_type zaten önceden yüklendi (select_related sayesinde)
        model_name = fav.content_type.model # örn: "anime"
        #setdefault ile anahtar yoksa boş liste oluştur ve ID'yi ekle
        fav_ids_by_type.setdefault(model_name, []).append(fav.object_id)

    # Model adı -> Model sınıfı eşlemesi
    # apps.get_model kullanmak daha dinamik olabilir ama bu daha basit
    models_map = {'anime': Anime, 'webtoon': Webtoon, 'manga': Manga, 'novel': Novel}

    # 3. Her grup için ilgili öğeleri tek sorguyla getir
    grouped_favs = {}
    all_fav_pks_for_template = set() # Template'deki butonları işaretlemek için tüm PK'lar

    for model_name, ids in fav_ids_by_type.items():
        if ids: # Sadece ID listesi boş değilse sorgu yap
            model_class = models_map.get(model_name)
            if model_class:
                try:
                    # Tek sorguyla ilgili modelin öğelerini getir
                    # user ve tags alanlarını önceden yükle
                    items = list(model_class.objects
                                 .select_related('user') # Kullanıcı bilgisini getir
                                 .prefetch_related('tags') # Etiketleri getir
                                 .filter(pk__in=ids) # Sadece favori ID'ler
                                 .order_by('-added_date', 'title')) # Sırala
                    grouped_favs[model_name] = items
                    # Template'de kullanılacak PK set'ine ekle
                    all_fav_pks_for_template.update(ids)
                except Exception as e:
                    logger.error(f"Favori öğeler alınırken hata (Model: {model_name}): {e}", exc_info=True)

    # 4. Template'de göstermek için gruplanmış listeyi hazırla (sıralı)
    # Sadece içinde öğe olan grupları al
    grouped_favs_list = [(k, v) for k, v in grouped_favs.items() if v]
    # Grupları belirli bir sıraya göre diz (Anime, Webtoon, Manga, Novel)
    grouped_favs_list.sort(key=lambda x: list(models_map.keys()).index(x[0]))

    # 5. Context'i oluştur ve template'i render et
    context = {
        'grouped_favorites_list': grouped_favs_list, # [(model_adı, [item1, item2]), ...]
        'total_favorites': user_favorites.count(), # Toplam favori sayısı (ilk sorgudan)
        'favorited_pks': all_fav_pks_for_template # Bu sayfadaki tüm öğeler favori olduğu için
    }
    return render(request, "tracker/favorites.html", context)


# ==============================================================================
# 4. CRUD VIEW'LARI (Refactored - İşleyici Fonksiyonları Kullanıyor)
# ==============================================================================

# --- Liste/Create Views ---
@login_required
def anime_list_and_create(request):
    return _process_list_view(request, Anime, AnimeForm, "tracker/anime_list.html", "tracker:anime_list_view")
@login_required
def webtoon_list_and_create(request):
    return _process_list_view(request, Webtoon, WebtoonForm, "tracker/webtoon_list.html", "tracker:webtoon_list_view")
@login_required
def manga_list_and_create(request):
    return _process_list_view(request, Manga, MangaForm, "tracker/manga_list.html", "tracker:manga_list_view")
@login_required
def novel_list_and_create(request):
    return _process_list_view(request, Novel, NovelForm, "tracker/novel_list.html", "tracker:novel_list_view")

# --- Edit Views ---
@login_required
def anime_edit(request, pk):
    return _process_edit_view(request, pk, Anime, AnimeForm, "tracker/anime_form.html")
@login_required
def webtoon_edit(request, pk):
    return _process_edit_view(request, pk, Webtoon, WebtoonForm, "tracker/webtoon_form.html")
@login_required
def manga_edit(request, pk):
    return _process_edit_view(request, pk, Manga, MangaForm, "tracker/manga_form.html")
@login_required
def novel_edit(request, pk):
    return _process_edit_view(request, pk, Novel, NovelForm, "tracker/novel_form.html")

# --- Delete Views ---
@login_required
def anime_delete(request, pk):
    return _process_delete_view(request, pk, Anime, "tracker:anime_list_view")
@login_required
def webtoon_delete(request, pk):
    return _process_delete_view(request, pk, Webtoon, "tracker:webtoon_list_view")
@login_required
def manga_delete(request, pk):
    return _process_delete_view(request, pk, Manga, "tracker:manga_list_view")
@login_required
def novel_delete(request, pk):
    return _process_delete_view(request, pk, Novel, "tracker:novel_list_view")

# --- Detail Views ---
@login_required
def anime_detail(request, pk):
    return _render_detail_view(request, pk, Anime)
@login_required
def webtoon_detail(request, pk):
    return _render_detail_view(request, pk, Webtoon)
@login_required
def manga_detail(request, pk):
    return _render_detail_view(request, pk, Manga)
@login_required
def novel_detail(request, pk):
    return _render_detail_view(request, pk, Novel)


# ==============================================================================
# 5. API VE EXPORT VIEW'LARI
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


# --- CSV Export View'ları (Refactored - _export_csv'yi kullanıyor) ---
# Alan eşleştirmeleri (model alanı -> CSV başlığı)
ANIME_FIELDS_MAP = {"pk":"ID", "title":"Baslik", "get_status_display":"Durum", "rating":"Puan", "studio":"Stüdyo", "episodes_watched":"Izlenen Bolum", "total_episodes":"Toplam Bolum", "start_date":"Baslama Tarihi", "end_date":"Bitirme Tarihi", "added_date":"Eklenme Tarihi", "tags":"Etiketler", "mal_id":"MAL ID", "notes":"Notlar", "cover_image_url":"Kapak URL"}
WEBTOON_FIELDS_MAP = {"pk":"ID", "title":"Baslik", "get_status_display":"Durum", "rating":"Puan", "author":"Yazar", "artist":"Cizer", "chapters_read":"Okunan Bolum", "total_chapters":"Toplam Bolum", "platform":"Platform", "start_date":"Baslama Tarihi", "end_date":"Bitirme Tarihi", "added_date":"Eklenme Tarihi", "tags":"Etiketler", "mangadex_id":"MangaDex ID", "notes":"Notlar", "cover_image_url":"Kapak URL"}
MANGA_FIELDS_MAP = {"pk":"ID", "title":"Baslik", "get_status_display":"Durum", "rating":"Puan", "author":"Yazar", "artist":"Cizer", "chapters_read":"Okunan Bolum", "volumes_read":"Okunan Cilt", "total_chapters":"Toplam Bolum", "total_volumes":"Toplam Cilt", "start_date":"Baslama Tarihi", "end_date":"Bitirme Tarihi", "added_date":"Eklenme Tarihi", "tags":"Etiketler", "mangadex_id":"MangaDex ID", "notes":"Notlar", "cover_image_url":"Kapak URL"}
NOVEL_FIELDS_MAP = {"pk":"ID", "title":"Baslik", "get_status_display":"Durum", "rating":"Puan", "author":"Yazar", "chapters_read":"Okunan Bolum", "volumes_read":"Okunan Cilt", "total_chapters":"Toplam Bolum", "total_volumes":"Toplam Cilt", "start_date":"Baslama Tarihi", "end_date":"Bitirme Tarihi", "added_date":"Eklenme Tarihi", "tags":"Etiketler", "mal_id":"MAL ID", "notes":"Notlar", "cover_image_url":"Kapak URL"}

@login_required
def export_anime_csv(request):
    return _export_csv(request, Anime, "anime", ANIME_FIELDS_MAP)
@login_required
def export_webtoon_csv(request):
     return _export_csv(request, Webtoon, "webtoon", WEBTOON_FIELDS_MAP)
@login_required
def export_manga_csv(request):
     return _export_csv(request, Manga, "manga", MANGA_FIELDS_MAP)
@login_required
def export_novel_csv(request):
     return _export_csv(request, Novel, "novel", NOVEL_FIELDS_MAP)