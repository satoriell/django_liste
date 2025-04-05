# tracker/views.py
# Konum: /home/admin/App/django_liste/tracker/views.py

import csv
import datetime
import json

from django.apps import apps
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Count, F, Q
from django.http import HttpResponse, JsonResponse # JsonResponse gerekli
from django.contrib.contenttypes.models import ContentType
# reverse import edilmiş olmalı (reverse_lazy yerine reverse daha sık kullanılır)
from django.urls import reverse
from django.views.decorators.http import require_http_methods # require_http_methods gerekli
from django.utils import timezone

# Formları import et
from .forms import AnimeForm, MangaForm, NovelForm, WebtoonForm

# Modelleri import et
from .models import Anime, Manga, Novel, Webtoon, Favorite # Favorite gerekli

# MangaDex Servisini import et
from . import mangadex_service

# ==============================================================================
# 1. YARDIMCI FONKSİYONLAR
# ==============================================================================

def apply_sorting(queryset, sort_by_param, default_sort="-added_date"):
    """Verilen queryset'i belirtilen parametreye göre sıralar."""
    valid_sort_options = {
        "title_asc": "title", "title_desc": "-title",
        "rating_asc": "rating", "rating_desc": "-rating",
        "date_asc": "added_date", "date_desc": "-added_date",
    }
    order_field = valid_sort_options.get(sort_by_param, default_sort)
    if order_field == "rating_desc":
        return queryset.order_by(F("rating").desc(nulls_last=True), "-added_date")
    elif order_field == "rating_asc":
        return queryset.order_by(F("rating").asc(nulls_last=True), "-added_date")
    else:
        return queryset.order_by(order_field)

def _process_list_view(
    request, model, form_class, template_name, redirect_url_name, paginate_by=15
):
    """Liste görünümü ve manuel form işleme için ortak mantık."""
    # --- GET İşlemleri ---
    status_filter = request.GET.get("status", "")
    search_query = request.GET.get("q", "")
    sort_by = request.GET.get("sort", "-added_date")

    queryset = model.objects.filter(user=request.user)
    if status_filter: queryset = queryset.filter(status=status_filter)
    if search_query: queryset = queryset.filter(title__icontains=search_query)
    queryset = apply_sorting(queryset, sort_by)

    paginator = Paginator(queryset, paginate_by)
    page_number = request.GET.get("page")
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    # --- POST (Manuel Ekleme) ---
    form = None
    if request.method == "POST":
        form = form_class(request.POST)
        if form.is_valid():
            instance = form.save(commit=False)
            instance.user = request.user
            instance.save()
            messages.success(request, f'{model._meta.verbose_name.capitalize()} "{instance.title}" başarıyla eklendi.')
            return redirect(redirect_url_name)
        else:
            messages.error(request, "Formda hatalar var. Lütfen işaretli alanları kontrol edin.")
    else:
        form = form_class() # GET için boş form

    # --- Context ---
    existing_params = request.GET.copy()
    if "page" in existing_params: del existing_params["page"]
    params_encoded = existing_params.urlencode()

    favorited_pks = set()
    if request.user.is_authenticated and page_obj.object_list:
        item_ids = [item.pk for item in page_obj.object_list]
        try:
            content_type = ContentType.objects.get_for_model(model)
            favorited_pks = set(Favorite.objects.filter(
                user=request.user, content_type=content_type, object_id__in=item_ids
            ).values_list('object_id', flat=True))
        except ContentType.DoesNotExist:
            messages.error(request, "İçerik türü hatası.")

    # API arama URL'si
    api_search_url = None
    item_type_lower = model.__name__.lower()
    if item_type_lower in ['manga', 'webtoon']:
         try:
             api_search_url = reverse(f'tracker:{item_type_lower}_api_search')
         except Exception:
              api_search_url = None

    context = {
        "page_obj": page_obj,
        "paginator": paginator,
        "form": form, # Manuel ekleme formu
        "status_choices": model.STATUS_CHOICES,
        "current_status_filter": status_filter,
        "search_query": search_query,
        "current_sort": sort_by,
        "params_encoded": params_encoded,
        "model_name_plural": model._meta.verbose_name_plural.capitalize(),
        "favorited_pks": favorited_pks,
        "item_type_str": item_type_lower,
        "list_url_name": redirect_url_name,
        "export_url_name": f"tracker:export_{item_type_lower}_csv",
        "api_search_url": api_search_url # URL'in kendisini gönderelim
    }
    return render(request, template_name, context)


def _process_edit_view(request, pk, model, form_class, template_name, redirect_url_name):
    # ... (Bu fonksiyon aynı kalabilir) ...
    instance = get_object_or_404(model, pk=pk, user=request.user)
    model_verbose_name = model._meta.verbose_name.capitalize()
    if request.method == "POST":
        form = form_class(request.POST, instance=instance)
        if form.is_valid():
            saved_instance = form.save()
            messages.success(request, f'{model_verbose_name} "{saved_instance.title}" başarıyla güncellendi.')
            return redirect(redirect_url_name)
        else:
            messages.error(request, "Formda hatalar var.")
    else:
        form = form_class(instance=instance)
    context = {"form": form, "item": instance, "model_name": model_verbose_name}
    return render(request, template_name, context)


def _process_delete_view(request, pk, model, redirect_url_name):
    # ... (Bu fonksiyon aynı kalabilir) ...
    instance = get_object_or_404(model, pk=pk, user=request.user)
    model_verbose_name = model._meta.verbose_name.capitalize()
    if request.method == "POST":
        title = instance.title
        instance.delete()
        messages.success(request, f'{model_verbose_name} "{title}" başarıyla silindi.')
        return redirect(redirect_url_name)
    context = {"item": instance, "model_name": model_verbose_name}
    return render(request, "tracker/confirm_delete_base.html", context)


def _render_detail_view(request, pk, model):
    # ... (Bu fonksiyon aynı kalabilir) ...
    instance = get_object_or_404(model, pk=pk)
    model_name_lower = model.__name__.lower()
    is_favorite = False
    if request.user.is_authenticated:
        try:
            content_type = ContentType.objects.get_for_model(model)
            is_favorite = Favorite.objects.filter(user=request.user, content_type=content_type, object_id=instance.pk).exists()
        except ContentType.DoesNotExist:
            messages.error(request, "İçerik türü hatası.")
    context = {
        "item": instance,
        "model_name": model._meta.verbose_name.capitalize(),
        "item_type": model_name_lower,
        "is_favorite": is_favorite,
        "is_owner": request.user == instance.user if request.user.is_authenticated else False
    }
    return render(request, "tracker/detail_base.html", context)


def _export_csv(request, model, filename_prefix, fields_map):
    # ... (Bu fonksiyon aynı kalabilir, fields_map kullanımı doğru) ...
    if not request.user.is_authenticated:
        return HttpResponse("Yetkisiz Erişim", status=401)
    # ... (Geri kalan CSV oluşturma kodu) ...
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response.write("\ufeff".encode("utf8"))
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    status_filter = request.GET.get("status", "")
    search_query = request.GET.get("q", "")
    filename_suffix = ""
    if status_filter: filename_suffix += f"_durum-{status_filter.replace(' ', '_')}"
    if search_query: filename_suffix += f"_arama-{search_query[:15].replace(' ','_')}"
    filename = f"{filename_prefix}_export_{timestamp}{filename_suffix}.csv"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    writer = csv.writer(response, delimiter=";", quotechar='"', quoting=csv.QUOTE_MINIMAL)
    header = list(fields_map.values())
    writer.writerow(header)
    queryset = model.objects.filter(user=request.user)
    if status_filter: queryset = queryset.filter(status=status_filter)
    if search_query: queryset = queryset.filter(title__icontains=search_query)
    queryset = queryset.order_by("-added_date", "title")
    for item in queryset:
        row = []
        for field_name in fields_map.keys():
            value = ""
            try:
                if field_name == 'get_status_display':
                    value = item.get_status_display()
                elif '__' in field_name:
                    related_attrs = field_name.split('__')
                    related_obj = item
                    for attr in related_attrs:
                        related_obj = getattr(related_obj, attr, None)
                        if related_obj is None: break
                    value = str(related_obj) if related_obj is not None else ""
                else:
                    value = getattr(item, field_name, "")
            except Exception as e:
                print(f"CSV Export Hatası ({model.__name__} - {field_name}): {e}")
                value = "HATA"
            if isinstance(value, datetime.datetime):
                if timezone.is_aware(value): value = timezone.localtime(value)
                value = value.strftime("%Y-%m-%d %H:%M:%S") if value else ""
            elif isinstance(value, datetime.date):
                value = value.strftime("%Y-%m-%d") if value else ""
            elif value is None:
                value = ""
            row.append(str(value))
        writer.writerow(row)
    return response


# ==============================================================================
# 2. ANA VIEW FONKSİYONLARI
# ==============================================================================

@login_required
def dashboard_view(request):
    # ... (Bu fonksiyon aynı kalabilir) ...
    user = request.user
    anime_count = Anime.objects.filter(user=user).count()
    webtoon_count = Webtoon.objects.filter(user=user).count()
    manga_count = Manga.objects.filter(user=user).count()
    novel_count = Novel.objects.filter(user=user).count()
    recent_anime = Anime.objects.filter(user=user).order_by("-added_date")[:5]
    recent_webtoons = Webtoon.objects.filter(user=user).order_by("-added_date")[:5]
    recent_mangas = Manga.objects.filter(user=user).order_by("-added_date")[:5]
    recent_novels = Novel.objects.filter(user=user).order_by("-added_date")[:5]
    top_anime = apply_sorting(Anime.objects.filter(user=user, rating__isnull=False), "rating_desc")[:5]
    top_webtoons = apply_sorting(Webtoon.objects.filter(user=user, rating__isnull=False), "rating_desc")[:5]
    top_mangas = apply_sorting(Manga.objects.filter(user=user, rating__isnull=False), "rating_desc")[:5]
    top_novels = apply_sorting(Novel.objects.filter(user=user, rating__isnull=False), "rating_desc")[:5]
    type_labels = ["Anime", "Webtoon", "Manga", "Novel"]
    type_counts = [anime_count, webtoon_count, manga_count, novel_count]
    status_choices = Anime.STATUS_CHOICES
    status_counts_dict = {status_value: 0 for status_value, _ in status_choices}
    all_models = [Anime, Webtoon, Manga, Novel]
    for model in all_models:
        counts = model.objects.filter(user=user).values("status").annotate(count=Count("id")).order_by("status")
        for item in counts:
            if item["status"] in status_counts_dict: status_counts_dict[item["status"]] += item["count"]
    status_labels = [display for _, display in status_choices]
    status_data = [status_counts_dict[value] for value, _ in status_choices]
    chart_data = {"typeLabels": type_labels, "typeCounts": type_counts, "statusLabels": status_labels, "statusData": status_data}
    context = {
        "anime_count": anime_count, "webtoon_count": webtoon_count, "manga_count": manga_count, "novel_count": novel_count,
        "recent_anime": recent_anime, "recent_webtoons": recent_webtoons, "recent_mangas": recent_mangas, "recent_novels": recent_novels,
        "top_anime": top_anime, "top_webtoons": top_webtoons, "top_mangas": top_mangas, "top_novels": top_novels,
        "chart_data_json": json.dumps(chart_data),
    }
    return render(request, "tracker/dashboard.html", context)


def signup_view(request):
    # ... (Bu fonksiyon aynı kalabilir) ...
    if request.user.is_authenticated:
        return redirect('tracker:dashboard')
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            messages.success(request, f'Hesap "{username}" başarıyla oluşturuldu! Giriş yapabilirsiniz.')
            return redirect('login')
        else:
            messages.error(request, 'Lütfen formdaki hataları düzeltin.')
    else:
        form = UserCreationForm()
    return render(request, 'registration/signup.html', {'form': form})


@login_required
@require_http_methods(["POST"])
def toggle_favorite(request):
    # ... (Bu fonksiyon aynı kalabilir) ...
    try:
        data = json.loads(request.body)
        item_type_str = data.get('item_type')
        item_id = data.get('item_id')
        if not item_type_str or not item_id: return JsonResponse({'status': 'error', 'message': 'Eksik parametre.'}, status=400)
        content_type = ContentType.objects.get(model=item_type_str.lower())
        model_class = content_type.model_class()
        if not model_class.objects.filter(pk=item_id).exists(): return JsonResponse({'status': 'error', 'message': 'Öğe bulunamadı.'}, status=404)
        favorite, created = Favorite.objects.get_or_create(user=request.user, content_type=content_type, object_id=item_id)
        is_favorite_now = False
        if created: is_favorite_now = True
        else: favorite.delete(); is_favorite_now = False
        return JsonResponse({'status': 'ok', 'is_favorite': is_favorite_now})
    except json.JSONDecodeError: return JsonResponse({'status': 'error', 'message': 'Geçersiz JSON.'}, status=400)
    except ContentType.DoesNotExist: return JsonResponse({'status': 'error', 'message': 'Geçersiz öğe türü.'}, status=400)
    except Exception as e: print(f"Toggle Favorite Error: {e}"); return JsonResponse({'status': 'error', 'message': 'Bir sunucu hatası oluştu.'}, status=500)


@login_required
def favorites_view(request):
    # ... (Bu fonksiyon aynı kalabilir) ...
    user = request.user
    user_favorites = Favorite.objects.filter(user=user).select_related('content_type')
    favorite_ids_by_type = {'anime': [], 'webtoon': [], 'manga': [], 'novel': []}
    for fav in user_favorites:
        model_name = fav.content_type.model
        if model_name in favorite_ids_by_type: favorite_ids_by_type[model_name].append(fav.object_id)
    models_map = {'anime': Anime, 'webtoon': Webtoon, 'manga': Manga, 'novel': Novel}
    grouped_favorites = {}
    all_favorited_pks = set()
    for model_name, ids in favorite_ids_by_type.items():
        if ids:
            model_class = models_map.get(model_name)
            if model_class:
                items = list(model_class.objects.filter(pk__in=ids).order_by('-added_date', 'title'))
                grouped_favorites[model_name] = items
                all_favorited_pks.update(ids)
    grouped_favorites_list = [(k, v) for k, v in grouped_favorites.items() if v]
    grouped_favorites_list.sort(key=lambda x: list(models_map.keys()).index(x[0]))
    total_favorites = user_favorites.count()
    context = {'grouped_favorites_list': grouped_favorites_list, 'total_favorites': total_favorites, 'favorited_pks': all_favorited_pks}
    return render(request, "tracker/favorites.html", context)


# --- Anime CRUD View'ları ---
@login_required
def anime_list_and_create(request):
    return _process_list_view(request, Anime, AnimeForm, "tracker/anime_list.html", "tracker:anime_list_view")
@login_required
def anime_edit(request, pk):
    return _process_edit_view(request, pk, Anime, AnimeForm, "tracker/anime_form.html", "tracker:anime_list_view")
@login_required
def anime_delete(request, pk):
    return _process_delete_view(request, pk, Anime, "tracker:anime_list_view")
@login_required
def anime_detail(request, pk):
    return _render_detail_view(request, pk, Anime)

# --- Webtoon CRUD View'ları ---
@login_required
def webtoon_list_and_create(request):
    # API Arama linkini context'e ekledik (_process_list_view içinde)
    return _process_list_view(request, Webtoon, WebtoonForm, "tracker/webtoon_list.html", "tracker:webtoon_list_view")
@login_required
def webtoon_edit(request, pk):
    return _process_edit_view(request, pk, Webtoon, WebtoonForm, "tracker/webtoon_form.html", "tracker:webtoon_list_view")
@login_required
def webtoon_delete(request, pk):
    return _process_delete_view(request, pk, Webtoon, "tracker:webtoon_list_view")
@login_required
def webtoon_detail(request, pk):
    return _render_detail_view(request, pk, Webtoon)

# --- Manga CRUD View'ları ---
@login_required
def manga_list_and_create(request):
    # API Arama linkini context'e ekledik (_process_list_view içinde)
    return _process_list_view(request, Manga, MangaForm, "tracker/manga_list.html", "tracker:manga_list_view")
@login_required
def manga_edit(request, pk):
    return _process_edit_view(request, pk, Manga, MangaForm, "tracker/manga_form.html", "tracker:manga_list_view")
@login_required
def manga_delete(request, pk):
    return _process_delete_view(request, pk, Manga, "tracker:manga_list_view")
@login_required
def manga_detail(request, pk):
    return _render_detail_view(request, pk, Manga)

# --- Novel CRUD View'ları ---
@login_required
def novel_list_and_create(request):
    return _process_list_view(request, Novel, NovelForm, "tracker/novel_list.html", "tracker:novel_list_view")
@login_required
def novel_edit(request, pk):
    return _process_edit_view(request, pk, Novel, NovelForm, "tracker/novel_form.html", "tracker:novel_list_view")
@login_required
def novel_delete(request, pk):
    return _process_delete_view(request, pk, Novel, "tracker:novel_list_view")
@login_required
def novel_detail(request, pk):
    return _render_detail_view(request, pk, Novel)

# ==============================================================================
# MangaDex API View Fonksiyonları (GÜNCELLENMİŞ)
# ==============================================================================

@login_required
def manga_api_search_view(request):
    """MangaDex API'da Manga/Webtoon aramak için formu gösterir ve arama yapar."""
    context = {
        'search_results': None,
        'query': request.GET.get('query', None), # GET ile de sorgu alabiliriz (örn. başka sayfadan link)
        # Arama sonuçlarındaki linkin doğru URL'e gitmesi için
        'add_item_url_name': 'tracker:md_add_item'
    }
    # Hem GET hem POST'ta sorgu varsa arama yapalım
    query = request.POST.get('query', context['query'] or '').strip() # Önce POST'a, sonra GET'e bak

    if request.method == 'POST' and not query:
         messages.warning(request, "Lütfen aramak için bir başlık girin.")
         # Boş POST isteği geldiyse arama yapmadan formu tekrar göster
         return render(request, 'tracker/manga_api_search.html', context)

    if query:
        context['query'] = query # Sorguyu template'e gönder
        results = mangadex_service.search_manga(query)
        if results is None:
             messages.error(request, "MangaDex API'ına bağlanırken bir hata oluştu.")
             context['search_results'] = None # Hata durumunu belirt
        elif not results:
            # Sonuç yoksa mesajı sadece ilk arama için gösterelim (POST)
            if request.method == 'POST':
                 messages.warning(request, f"'{query}' için MangaDex üzerinde sonuç bulunamadı.")
            context['search_results'] = [] # Boş liste
        else:
             context['search_results'] = results
             # Sadece POST isteğinde başarı mesajı gösterelim
             if request.method == 'POST':
                 messages.success(request, f"'{query}' için {len(results)} sonuç bulundu.")

    # Hem GET hem de (sonuçları olan) POST isteği için template'i render et
    return render(request, 'tracker/manga_api_search.html', context)


@login_required
# --- Fonksiyon adı güncellendi ---
def md_add_item_view(request, mangadex_id):
    """Seçilen MangaDex ID'si ile detayları getirir, uygun formu (Manga/Webtoon) doldurur ve kaydeder."""
    initial_data = mangadex_service.get_manga_details(str(mangadex_id))

    if initial_data is None:
        messages.error(request, "Detaylar MangaDex API'sından alınamadı veya öğe bulunamadı.")
        # Arama sayfasına geri dön (son sorguyla dönmek daha iyi olabilir)
        # Şimdilik basitçe manga aramaya dönelim
        return redirect('tracker:manga_api_search')

    # --- Dinamik Tip, Model, Form, URL, Template Seçimi ---
    detected_type = initial_data.get('detected_type', 'MANGA')

    if detected_type == 'WEBTOON':
        ModelClass = Webtoon
        FormClass = WebtoonForm
        model_verbose_name = "Webtoon"
        list_url_name = 'tracker:webtoon_list_view'
        # Ortak template adı (önceki adımda md_form_api.html olarak belirlemiştik)
        form_template = 'tracker/md_form_api.html'
        search_url_name = 'tracker:webtoon_api_search' # İlgili arama URL'i
    else: # Varsayılan MANGA
        ModelClass = Manga
        FormClass = MangaForm
        model_verbose_name = "Manga"
        list_url_name = 'tracker:manga_list_view'
        form_template = 'tracker/md_form_api.html' # Ortak template
        search_url_name = 'tracker:manga_api_search'
    # ------------------------------------------------------

    # Bu ID ve TİP ile veritabanında zaten kayıt var mı?
    existing_item = ModelClass.objects.filter(mangadex_id=mangadex_id, user=request.user).first()
    if existing_item:
        messages.info(request, f"'{existing_item.title}' ({model_verbose_name}) zaten listenizde mevcut.")
        detail_url_name = f'tracker:{model_verbose_name.lower()}_detail'
        return redirect(detail_url_name, pk=existing_item.pk)

    if request.method == 'POST':
        # Seçilen FormClass ile formu POST verisinden oluştur
        form = FormClass(request.POST)
        if form.is_valid():
            instance = form.save(commit=False)
            instance.user = request.user
            instance.mangadex_id = mangadex_id # UUID'yi ata
            # API'dan gelen bazı değerleri (örn. notes, cover_image_url) form verisi üzerine yazabilir miyiz?
            # Veya formda bu alanlar yoksa instance'a ekleyebiliriz.
            # Şimdilik formdan gelen veriye güvenelim, sadece ID'yi ekleyelim.
            instance.save()
            messages.success(request, f"{model_verbose_name} '{instance.title}' başarıyla listenize eklendi.")
            # Eklenen öğenin detayına yönlendirmek daha iyi olabilir
            detail_url_name = f'tracker:{model_verbose_name.lower()}_detail'
            return redirect(detail_url_name, pk=instance.pk) # Yönlendirmeyi detaya yapalım
        else:
             messages.error(request, "Formda hatalar var. Lütfen işaretli alanları kontrol edin.")
             context = {
                  'form': form, # Hatalı form
                  'mangadex_data': initial_data, # API verisi
                  'model_verbose_name': model_verbose_name
             }
             return render(request, form_template, context)
    else:
        # GET isteği: Seçilen FormClass ile API verisini ('initial') kullanarak formu oluştur
        form = FormClass(initial=initial_data)
        context = {
            'form': form, # Önceden doldurulmuş form
            'mangadex_data': initial_data, # API verisi (teyit için)
            'model_verbose_name': model_verbose_name # Template başlığı için
        }
        return render(request, form_template, context)

# ==============================================================================
# GÜNCELLENMİŞ VIEW FONKSİYONLARI SONU
# ==============================================================================


# --- CSV EXPORT View'ları ---
@login_required
def export_anime_csv(request):
    fields = {
        "pk": "ID", "title": "Baslik", "get_status_display": "Durum", "rating": "Puan",
        "studio": "Stüdyo", "episodes_watched": "Izlenen Bolum", "total_episodes": "Toplam Bolum",
        "start_date": "Baslama Tarihi", "end_date": "Bitirme Tarihi", "added_date": "Eklenme Tarihi",
        "notes": "Notlar", "cover_image_url": "Kapak URL",
    }
    return _export_csv(request, Anime, "anime", fields)
@login_required
def export_webtoon_csv(request):
    fields = {
        "pk": "ID", "title": "Baslik", "get_status_display": "Durum", "rating": "Puan",
        "author": "Yazar", "artist": "Cizer", "chapters_read": "Okunan Bolum", "total_chapters": "Toplam Bolum",
        "platform": "Platform", "start_date": "Baslama Tarihi", "end_date": "Bitirme Tarihi",
        "added_date": "Eklenme Tarihi", "notes": "Notlar", "cover_image_url": "Kapak URL",
    }
    return _export_csv(request, Webtoon, "webtoon", fields)
@login_required
def export_manga_csv(request):
    fields = {
        "pk": "ID", "title": "Baslik", "get_status_display": "Durum", "rating": "Puan",
        "author": "Yazar", "artist": "Cizer", "chapters_read": "Okunan Bolum", "volumes_read": "Okunan Cilt",
        "total_chapters": "Toplam Bolum", "total_volumes": "Toplam Cilt", "start_date": "Baslama Tarihi",
        "end_date": "Bitirme Tarihi", "added_date": "Eklenme Tarihi", "notes": "Notlar", "cover_image_url": "Kapak URL",
    }
    return _export_csv(request, Manga, "manga", fields)
@login_required
def export_novel_csv(request):
    fields = {
        "pk": "ID", "title": "Baslik", "get_status_display": "Durum", "rating": "Puan",
        "author": "Yazar", "chapters_read": "Okunan Bolum", "volumes_read": "Okunan Cilt",
        "total_chapters": "Toplam Bolum", "total_volumes": "Toplam Cilt", "start_date": "Baslama Tarihi",
        "end_date": "Bitirme Tarihi", "added_date": "Eklenme Tarihi", "notes": "Notlar", "cover_image_url": "Kapak URL",
    }
    return _export_csv(request, Novel, "novel", fields)