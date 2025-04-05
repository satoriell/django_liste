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
from django.http import HttpResponse, JsonResponse
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from taggit.models import Tag # <- YENİ: Tag modelini import et

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
    # Null değerleri sona atmak için F objesi kullanmaya devam edelim
    if order_field == "rating_desc":
        return queryset.order_by(F("rating").desc(nulls_last=True), "-added_date")
    elif order_field == "rating_asc":
        return queryset.order_by(F("rating").asc(nulls_last=True), "-added_date")
    else:
        return queryset.order_by(order_field)

def _process_list_view(
    request, model, form_class, template_name, redirect_url_name, paginate_by=15
):
    """Liste görünümü ve manuel form işleme için ortak mantık (Etiket filtreleme eklendi)."""
    # --- GET İşlemleri ---
    status_filter = request.GET.get("status", "")
    search_query = request.GET.get("q", "")
    sort_by = request.GET.get("sort", "-added_date")
    tag_filter = request.GET.get("tag", "") # <- YENİ: Etiket filtresi

    queryset = model.objects.filter(user=request.user)
    if status_filter: queryset = queryset.filter(status=status_filter)
    if search_query: queryset = queryset.filter(title__icontains=search_query)
    if tag_filter: # <- YENİ: Etikete göre filtrele
        queryset = queryset.filter(tags__slug=tag_filter) # django-taggit'in slug alanı üzerinden filtreleme

    queryset = apply_sorting(queryset, sort_by)

    # Kullanıcının bu modeldeki tüm etiketlerini al (Filtreleme seçenekleri için)
    # Dikkat: Performans için optimize edilebilir (örn. sadece popüler etiketleri gösterme)
    all_tags = Tag.objects.filter(
        pk__in=model.objects.filter(user=request.user).values_list('tags', flat=True)
    ).distinct().order_by('name')

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
        # form_class'ın __init__'inde request.user'ı alıp almadığına bağlı olarak
        # form = form_class(request.POST, request=request) gibi bir kullanım gerekebilir.
        # Şimdilik standart varsayalım.
        form = form_class(request.POST)
        if form.is_valid():
            instance = form.save(commit=False)
            instance.user = request.user
            instance.save()
            # ModelForm ve TaggableManager sayesinde form.save() etiketleri de kaydeder.
            # Eğer form.save_m2m() gerektiren bir durum varsa (genelde TaggableManager ile gerekmez)
            # form.save_m2m() çağrılmalıydı.
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

    api_search_url = None
    item_type_lower = model.__name__.lower()
    if item_type_lower in ['manga', 'webtoon']:
         try:
             # tracker:manga_api_search veya tracker:webtoon_api_search gibi bir URL adı varsayılıyor
             api_search_url = reverse(f'tracker:{item_type_lower}_api_search')
         except Exception as e:
              print(f"API Arama URL Hatası ({item_type_lower}): {e}")
              api_search_url = None

    context = {
        "page_obj": page_obj,
        "paginator": paginator,
        "form": form,
        "status_choices": model.STATUS_CHOICES,
        "current_status_filter": status_filter,
        "search_query": search_query,
        "current_sort": sort_by,
        "current_tag_filter": tag_filter, # <- YENİ: Mevcut etiket filtresi
        "all_tags": all_tags,             # <- YENİ: Filtreleme için tüm etiketler
        "params_encoded": params_encoded,
        "model_name_plural": model._meta.verbose_name_plural.capitalize(),
        "favorited_pks": favorited_pks,
        "item_type_str": item_type_lower,
        "list_url_name": redirect_url_name,
        "export_url_name": f"tracker:export_{item_type_lower}_csv",
        "api_search_url": api_search_url
    }
    return render(request, template_name, context)

def _process_edit_view(request, pk, model, form_class, template_name, redirect_url_name):
    """Düzenleme görünümü (Etiketler form üzerinden yönetilir)."""
    instance = get_object_or_404(model, pk=pk, user=request.user)
    model_verbose_name = model._meta.verbose_name.capitalize()
    if request.method == "POST":
        # request.FILES eklemeyi unutma (eğer formda dosya alanı varsa)
        form = form_class(request.POST, instance=instance)
        if form.is_valid():
            saved_instance = form.save() # TaggableManager save ile etiketleri günceller
            messages.success(request, f'{model_verbose_name} "{saved_instance.title}" başarıyla güncellendi.')
            # Düzenlenen öğenin detayına gitmek daha mantıklı olabilir
            detail_url_name = f'tracker:{model.__name__.lower()}_detail'
            try:
                detail_url = reverse(detail_url_name, kwargs={'pk': saved_instance.pk})
                return redirect(detail_url)
            except Exception: # URL bulunamazsa listeye dön
                 return redirect(redirect_url_name)
        else:
            messages.error(request, "Formda hatalar var.")
    else:
        form = form_class(instance=instance) # Form etiketleri otomatik yükler
    context = {
        "form": form,
        "item": instance,
        "model_name": model_verbose_name,
        "list_url_name": redirect_url_name # Geri dön linki için
    }
    return render(request, template_name, context)

def _process_delete_view(request, pk, model, redirect_url_name):
    # Bu fonksiyon etiketlerle doğrudan ilgili değil, aynı kalabilir.
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
    """Detay görünümü (Etiketler template içinde gösterilir)."""
    # Bu fonksiyon etiketlerle doğrudan ilgili değil, context'e eklemeye gerek yok.
    # Template item.tags.all() ile erişebilir.
    instance = get_object_or_404(model, pk=pk) # Herkes detayı görebilir mi? Yoksa user=request.user ekle.
    model_name_lower = model.__name__.lower()
    is_favorite = False
    if request.user.is_authenticated:
        try:
            content_type = ContentType.objects.get_for_model(model)
            is_favorite = Favorite.objects.filter(user=request.user, content_type=content_type, object_id=instance.pk).exists()
        except ContentType.DoesNotExist:
            messages.error(request, "İçerik türü hatası.")

    # İlgili liste view'ının URL'ini oluştur (etiketlere link vermek için)
    list_view_url_name = f'tracker:{model_name_lower}_list_view'
    try:
        list_url_base = reverse(list_view_url_name)
    except Exception:
        list_url_base = None # URL bulunamazsa link vermeyiz

    context = {
        "item": instance,
        "model_name": model._meta.verbose_name.capitalize(),
        "item_type": model_name_lower,
        "is_favorite": is_favorite,
        "is_owner": request.user == instance.user if request.user.is_authenticated else False,
        "list_url_base": list_url_base, # <- YENİ: Etiket linkleri için temel URL
    }
    return render(request, "tracker/detail_base.html", context)

def _export_csv(request, model, filename_prefix, fields_map):
    """CSV Export (Etiketler eklendi)."""
    if not request.user.is_authenticated:
        return HttpResponse("Yetkisiz Erişim", status=401)

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response.write("\ufeff".encode("utf8")) # UTF-8 BOM for Excel
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    status_filter = request.GET.get("status", "")
    search_query = request.GET.get("q", "")
    tag_filter = request.GET.get("tag", "") # <- YENİ: Export'u da filtrele
    filename_suffix = ""
    if status_filter: filename_suffix += f"_durum-{status_filter.replace(' ', '_')}"
    if tag_filter: filename_suffix += f"_etiket-{tag_filter}" # <- YENİ
    if search_query: filename_suffix += f"_arama-{search_query[:15].replace(' ','_')}"

    filename = f"{filename_prefix}_export_{timestamp}{filename_suffix}.csv"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    writer = csv.writer(response, delimiter=";", quotechar='"', quoting=csv.QUOTE_MINIMAL)
    header = list(fields_map.values())
    writer.writerow(header)

    queryset = model.objects.filter(user=request.user)
    if status_filter: queryset = queryset.filter(status=status_filter)
    if tag_filter: queryset = queryset.filter(tags__slug=tag_filter) # <- YENİ
    if search_query: queryset = queryset.filter(title__icontains=search_query)
    # Etiketleri de prefetch edebiliriz (çok sayıda öğe varsa performansı artırır)
    queryset = queryset.prefetch_related('tags').order_by("-added_date", "title")

    for item in queryset:
        row = []
        for field_name in fields_map.keys():
            value = ""
            try:
                if field_name == 'get_status_display':
                    value = item.get_status_display()
                elif field_name == 'tags': # <- YENİ: Etiketleri işle
                    # item.tags.all() yerine prefetch ettiğimiz için .names() daha verimli olabilir
                    value = ", ".join(t.name for t in item.tags.all()) # veya item.tags.names()
                elif '__' in field_name: # İlişkili alanlar için
                    related_attrs = field_name.split('__')
                    related_obj = item
                    for attr in related_attrs:
                        related_obj = getattr(related_obj, attr, None)
                        if related_obj is None: break
                    value = str(related_obj) if related_obj is not None else ""
                else: # Normal model alanı
                    value = getattr(item, field_name, "")

                # Tarih/Zaman formatlama ve None kontrolü
                if isinstance(value, datetime.datetime):
                    if timezone.is_aware(value): value = timezone.localtime(value)
                    value = value.strftime("%Y-%m-%d %H:%M:%S") if value else ""
                elif isinstance(value, datetime.date):
                    value = value.strftime("%Y-%m-%d") if value else ""
                elif value is None:
                    value = ""

            except Exception as e:
                print(f"CSV Export Hatası ({model.__name__} - {field_name} - ID: {item.pk}): {e}")
                value = "HATA"

            row.append(str(value))
        writer.writerow(row)
    return response


# ==============================================================================
# 2. ANA VIEW FONKSİYONLARI (Çoğu aynı kalır, _process_* fonksiyonlarına dayanır)
# ==============================================================================
# dashboard_view, signup_view, toggle_favorite, favorites_view aynı kalabilir.

@login_required
def dashboard_view(request):
    # Bu view'da etiketlerle ilgili özel bir gösterim istenmiyorsa aynı kalabilir.
    # İstenirse: Popüler etiketler, son eklenen etiketler vb. eklenebilir.
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

    # Chart Data (Etiketleri eklemek istersek burası güncellenebilir)
    type_labels = ["Anime", "Webtoon", "Manga", "Novel"]
    type_counts = [anime_count, webtoon_count, manga_count, novel_count]
    status_choices = Anime.STATUS_CHOICES # Herhangi bir modelden alınabilir
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
    # Aynı kalabilir
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
    # Aynı kalabilir
    try:
        data = json.loads(request.body)
        item_type_str = data.get('item_type')
        item_id = data.get('item_id')
        if not item_type_str or not item_id: return JsonResponse({'status': 'error', 'message': 'Eksik parametre.'}, status=400)
        content_type = ContentType.objects.get(model=item_type_str.lower())
        model_class = content_type.model_class()
        # Öğe varlığını kontrol et (güvenlik)
        target_item = model_class.objects.filter(pk=item_id).first()
        if not target_item: return JsonResponse({'status': 'error', 'message': 'Öğe bulunamadı.'}, status=404)

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
    # Bu view'da etiket göstermek gerekirse güncellenebilir. Şimdilik aynı kalabilir.
    user = request.user
    user_favorites = Favorite.objects.filter(user=user).select_related('content_type')
    # Favorilenen öğeleri tiplerine göre gruplayıp ID'lerini toplayalım
    favorite_ids_by_type = {'anime': [], 'webtoon': [], 'manga': [], 'novel': []}
    for fav in user_favorites:
        model_name = fav.content_type.model # 'anime', 'webtoon' vb.
        if model_name in favorite_ids_by_type: favorite_ids_by_type[model_name].append(fav.object_id)
    # Modelleri mapleyelim
    models_map = {'anime': Anime, 'webtoon': Webtoon, 'manga': Manga, 'novel': Novel}
    # Gruplanmış favori öğeleri (model nesneleri olarak) tutacak sözlük
    grouped_favorites = {}
    all_favorited_pks = set() # Tüm favori ID'lerini tutalım (template'de hızlı kontrol için)
    # Her model tipi için ilgili öğeleri çekelim
    for model_name, ids in favorite_ids_by_type.items():
        if ids: # Eğer bu tipte favori varsa
            model_class = models_map.get(model_name)
            if model_class:
                # prefetch_related('tags') ekleyerek etiketleri de verimli çekebiliriz
                items = list(model_class.objects.filter(pk__in=ids).prefetch_related('tags').order_by('-added_date', 'title'))
                grouped_favorites[model_name] = items
                all_favorited_pks.update(ids) # ID'leri sete ekle

    # Template'de sıralı göstermek için listeye çevirelim
    grouped_favorites_list = [(k, v) for k, v in grouped_favorites.items() if v] # Boş listeleri atla
    # Önceden tanımlanmış sıraya göre sırala (Anime, Webtoon, Manga, Novel)
    grouped_favorites_list.sort(key=lambda x: list(models_map.keys()).index(x[0]))

    total_favorites = user_favorites.count()
    context = {
        'grouped_favorites_list': grouped_favorites_list,
        'total_favorites': total_favorites,
        # Template'de item.pk in favorited_pks kontrolü yerine doğrudan is_favorite kullanılabilir,
        # ama bu set tüm favori ID'lerini içerir, belki başka bir amaçla lazım olur.
        'favorited_pks': all_favorited_pks
    }
    return render(request, "tracker/favorites.html", context)


# --- CRUD View Fonksiyonları (Aynı kalır, _process_* kullanırlar) ---
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

@login_required
def webtoon_list_and_create(request):
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

@login_required
def manga_list_and_create(request):
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
# MangaDex API View Fonksiyonları (Etiket ekleme denemesi eklendi)
# ==============================================================================
@login_required
def manga_api_search_view(request):
    # Bu view etiketlerle doğrudan ilgili değil, aynı kalabilir.
    context = {
        'search_results': None,
        'query': request.GET.get('query', None),
        'add_item_url_name': 'tracker:md_add_item'
    }
    query = request.POST.get('query', context['query'] or '').strip()

    if request.method == 'POST' and not query:
         messages.warning(request, "Lütfen aramak için bir başlık girin.")
         return render(request, 'tracker/manga_api_search.html', context)

    if query:
        context['query'] = query
        results = mangadex_service.search_manga(query)
        if results is None:
             messages.error(request, "MangaDex API'ına bağlanırken bir hata oluştu.")
             context['search_results'] = None
        elif not results:
            if request.method == 'POST':
                 messages.warning(request, f"'{query}' için MangaDex üzerinde sonuç bulunamadı.")
            context['search_results'] = []
        else:
             context['search_results'] = results
             if request.method == 'POST':
                 messages.success(request, f"'{query}' için {len(results)} sonuç bulundu.")

    return render(request, 'tracker/manga_api_search.html', context)

@login_required
def md_add_item_view(request, mangadex_id):
    """Seçilen MangaDex ID'si ile detayları getirir, uygun formu doldurur ve kaydeder (Etiketleri eklemeyi dener)."""
    # MangaDex servisinin etiketleri liste olarak döndürdüğünü varsayalım: initial_data['tags_list'] = ['Action', 'Fantasy']
    initial_data = mangadex_service.get_manga_details(str(mangadex_id))

    if initial_data is None:
        messages.error(request, "Detaylar MangaDex API'sından alınamadı veya öğe bulunamadı.")
        return redirect('tracker:manga_api_search')

    detected_type = initial_data.get('detected_type', 'MANGA')

    if detected_type == 'WEBTOON':
        ModelClass = Webtoon
        FormClass = WebtoonForm
        model_verbose_name = "Webtoon"
        list_url_name = 'tracker:webtoon_list_view'
        form_template = 'tracker/md_form_api.html'
    else: # Varsayılan MANGA
        ModelClass = Manga
        FormClass = MangaForm
        model_verbose_name = "Manga"
        list_url_name = 'tracker:manga_list_view'
        form_template = 'tracker/md_form_api.html'

    existing_item = ModelClass.objects.filter(mangadex_id=mangadex_id, user=request.user).first()
    if existing_item:
        messages.info(request, f"'{existing_item.title}' ({model_verbose_name}) zaten listenizde mevcut.")
        detail_url_name = f'tracker:{model_verbose_name.lower()}_detail'
        return redirect(detail_url_name, pk=existing_item.pk)

    if request.method == 'POST':
        form = FormClass(request.POST) # API'dan gelen veriyi değil, kullanıcının POST ettiği veriyi al
        if form.is_valid():
            instance = form.save(commit=False)
            instance.user = request.user
            instance.mangadex_id = mangadex_id
            # API'dan gelen diğer verileri (notes, cover vs.) form temiz verisi üzerine yazma,
            # çünkü kullanıcı formda değişiklik yapmış olabilir. Sadece ID'yi eklemek yeterli.
            instance.save() # Ana nesneyi kaydet

            # --- YENİ: API'dan gelen etiketleri ekle ---
            # Eğer mangadex_service 'tags_list' adında bir liste döndürüyorsa:
            api_tags = initial_data.get('tags_list', [])
            if api_tags and isinstance(api_tags, list):
                try:
                    # instance.tags.add() string argümanlar kabul eder
                    instance.tags.add(*api_tags)
                    # Başarılı olursa mesaj vermeye gerek yok, ana mesaj yeterli
                except Exception as e:
                    # Etiket eklemede hata olursa logla veya mesaj ver (opsiyonel)
                    print(f"API'dan etiket ekleme hatası (ID: {instance.pk}): {e}")
            # ------------------------------------------

            # form.save_m2m() normalde TaggableManager için gerekli değil ama
            # eğer formda manuel TagField kullansaydık gerekebilirdi. Şimdilik gerek yok.

            messages.success(request, f"{model_verbose_name} '{instance.title}' başarıyla listenize eklendi.")
            detail_url_name = f'tracker:{model_verbose_name.lower()}_detail'
            return redirect(detail_url_name, pk=instance.pk)
        else:
             messages.error(request, "Formda hatalar var. Lütfen işaretli alanları kontrol edin.")
             context = {
                  'form': form,
                  'mangadex_data': initial_data,
                  'model_verbose_name': model_verbose_name
             }
             return render(request, form_template, context)
    else:
        # GET isteği: Formu API verisiyle doldur
        # `django-taggit`'in `TagField`'i initial data olarak virgülle ayrılmış string bekler.
        if 'tags_list' in initial_data:
             initial_data['tags'] = ", ".join(initial_data['tags_list'])

        form = FormClass(initial=initial_data)
        context = {
            'form': form,
            'mangadex_data': initial_data,
            'model_verbose_name': model_verbose_name
        }
        return render(request, form_template, context)

# ==============================================================================
# CSV EXPORT View'ları (Etiketler eklendi)
# ==============================================================================
@login_required
def export_anime_csv(request):
    fields = {
        "pk": "ID", "title": "Baslik", "get_status_display": "Durum", "rating": "Puan",
        "studio": "Stüdyo", "episodes_watched": "Izlenen Bolum", "total_episodes": "Toplam Bolum",
        "start_date": "Baslama Tarihi", "end_date": "Bitirme Tarihi", "added_date": "Eklenme Tarihi",
        "tags": "Etiketler", # <- YENİ
        "notes": "Notlar", "cover_image_url": "Kapak URL",
    }
    return _export_csv(request, Anime, "anime", fields)
@login_required
def export_webtoon_csv(request):
    fields = {
        "pk": "ID", "title": "Baslik", "get_status_display": "Durum", "rating": "Puan",
        "author": "Yazar", "artist": "Cizer", "chapters_read": "Okunan Bolum", "total_chapters": "Toplam Bolum",
        "platform": "Platform", "start_date": "Baslama Tarihi", "end_date": "Bitirme Tarihi",
        "added_date": "Eklenme Tarihi",
        "tags": "Etiketler", # <- YENİ
        "notes": "Notlar", "cover_image_url": "Kapak URL",
    }
    return _export_csv(request, Webtoon, "webtoon", fields)
@login_required
def export_manga_csv(request):
    fields = {
        "pk": "ID", "title": "Baslik", "get_status_display": "Durum", "rating": "Puan",
        "author": "Yazar", "artist": "Cizer", "chapters_read": "Okunan Bolum", "volumes_read": "Okunan Cilt",
        "total_chapters": "Toplam Bolum", "total_volumes": "Toplam Cilt", "start_date": "Baslama Tarihi",
        "end_date": "Bitirme Tarihi", "added_date": "Eklenme Tarihi",
        "tags": "Etiketler", # <- YENİ
        "notes": "Notlar", "cover_image_url": "Kapak URL",
    }
    return _export_csv(request, Manga, "manga", fields)
@login_required
def export_novel_csv(request):
    fields = {
        "pk": "ID", "title": "Baslik", "get_status_display": "Durum", "rating": "Puan",
        "author": "Yazar", "chapters_read": "Okunan Bolum", "volumes_read": "Okunan Cilt",
        "total_chapters": "Toplam Bolum", "total_volumes": "Toplam Cilt", "start_date": "Baslama Tarihi",
        "end_date": "Bitirme Tarihi", "added_date": "Eklenme Tarihi",
        "tags": "Etiketler", # <- YENİ
        "notes": "Notlar", "cover_image_url": "Kapak URL",
    }
    return _export_csv(request, Novel, "novel", fields)