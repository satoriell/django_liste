# tracker/views/helpers.py
import csv
import datetime
import json
import logging
import uuid

from django.apps import apps
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Count, F, Q
from django.http import HttpResponse, JsonResponse, Http404
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse, NoReverseMatch
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from taggit.models import Tag

# Bir üst dizindeki modülleri import et
from ..models import Anime, Manga, Novel, Webtoon, Favorite
from ..forms import AnimeForm, MangaForm, NovelForm, WebtoonForm # Gerekliyse (handle_create_form vb. kullanıyor)
from ..services import mangadex as mangadex_service
from ..services import jikan as jikan_service

logger = logging.getLogger(__name__)


# ==============================================================================
# 1. YARDIMCI FONKSİYONLAR (HELPERS) - Orijinal views.py'den taşındı
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

    # Toplam öğe sayısını al (filtresiz) - Bu pahalı olabilir, opsiyonel
    # total_items_count = model.objects.filter(user=request.user).count()

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
        # "total_items_count": total_items_count, # Filtresiz toplam sayı (opsiyonel)
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
# 2. GENEL VIEW İŞLEYİCİLERİ (PROCESSORS using Helpers) - Orijinal views.py'den taşındı
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