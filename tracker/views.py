# tracker/views.py
# Konum: /home/admin/App/django_liste/tracker/views.py

import csv
import datetime
import json

from django.apps import apps
from django.contrib import messages
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Count, F, Q
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods # AJAX için eklendi

# Formları import et
from .forms import AnimeForm, MangaForm, NovelForm, WebtoonForm

# Modelleri import et
from .models import Anime, Manga, Novel, Webtoon


# --- Genel Sıralama Mantığı Fonksiyonu ---
def apply_sorting(queryset, sort_by_param, default_sort="-added_date"):
    """Verilen queryset'i belirtilen parametreye göre sıralar."""
    valid_sort_options = {
        "title_asc": "title",
        "title_desc": "-title",
        "rating_asc": "rating",
        "rating_desc": "-rating",
        "date_asc": "added_date",
        "date_desc": "-added_date",
    }
    order_field = valid_sort_options.get(sort_by_param, default_sort)

    if order_field == "rating_desc":
        return queryset.order_by(F("rating").desc(nulls_last=True), "-added_date")
    elif order_field == "rating_asc":
        return queryset.order_by(F("rating").asc(nulls_last=True), "-added_date")
    else:
        return queryset.order_by(order_field)


# --- Dashboard Görünümü ---
def dashboard_view(request):
    """Dashboard sayfasını gösterir, genel istatistikler ve listeler içerir."""
    anime_count = Anime.objects.count()
    webtoon_count = Webtoon.objects.count()
    manga_count = Manga.objects.count()
    novel_count = Novel.objects.count()

    recent_anime = Anime.objects.order_by("-added_date")[:5]
    recent_webtoons = Webtoon.objects.order_by("-added_date")[:5]
    recent_mangas = Manga.objects.order_by("-added_date")[:5]
    recent_novels = Novel.objects.order_by("-added_date")[:5]

    top_anime = apply_sorting(Anime.objects.all(), "rating_desc")[:5]
    top_webtoons = apply_sorting(Webtoon.objects.all(), "rating_desc")[:5]
    top_mangas = apply_sorting(Manga.objects.all(), "rating_desc")[:5]
    top_novels = apply_sorting(Novel.objects.all(), "rating_desc")[:5]

    type_labels = ["Anime", "Webtoon", "Manga", "Novel"]
    type_counts = [anime_count, webtoon_count, manga_count, novel_count]

    status_choices = Anime.STATUS_CHOICES
    status_counts_dict = {status_value: 0 for status_value, _ in status_choices}

    all_models = [Anime, Webtoon, Manga, Novel]
    for model in all_models:
        counts = (
            model.objects.values("status")
            .annotate(count=Count("id"))
            .order_by("status")
        )
        for item in counts:
            if item["status"] in status_counts_dict:
                status_counts_dict[item["status"]] += item["count"]

    status_labels = [display for _, display in status_choices]
    status_data = [status_counts_dict[value] for value, _ in status_choices]

    chart_data = {
        "typeLabels": type_labels,
        "typeCounts": type_counts,
        "statusLabels": status_labels,
        "statusData": status_data,
    }

    context = {
        "anime_count": anime_count,
        "webtoon_count": webtoon_count,
        "manga_count": manga_count,
        "novel_count": novel_count,
        "recent_anime": recent_anime,
        "recent_webtoons": recent_webtoons,
        "recent_mangas": recent_mangas,
        "recent_novels": recent_novels,
        "top_anime": top_anime,
        "top_webtoons": top_webtoons,
        "top_mangas": top_mangas,
        "top_novels": top_novels,
        "chart_data_json": json.dumps(chart_data),
    }
    return render(request, "tracker/dashboard.html", context)


# --- FAVORİLER İÇİN YARDIMCI FONKSİYONLAR ---
def get_model_map():
    """String isimden model class'ına haritalama sağlar."""
    return {
        "anime": Anime,
        "webtoon": Webtoon,
        "manga": Manga,
        "novel": Novel,
    }


def get_favorited_ids(request):
    """Kullanıcının oturumundaki favori ID'lerini türlerine göre dict olarak döner."""
    return request.session.get("favorites", {})


# --- FAVORİ VIEW'LARI ---

# GET (fallback) ve POST (AJAX için) metodlarına izin ver
@require_http_methods(["GET", "POST"])
def toggle_favorite(request, item_type, item_id):
    """Bir öğeyi favorilere ekler veya çıkarır (AJAX POST ve GET fallback destekli)."""
    model_map = get_model_map()
    is_ajax = request.headers.get("x-requested-with") == "XMLHttpRequest"

    if item_type not in model_map:
        if is_ajax:
            return JsonResponse(
                {"status": "error", "message": "Geçersiz öğe türü."}, status=400
            )
        messages.error(request, "Geçersiz öğe türü.")
        return HttpResponseRedirect(
            request.META.get("HTTP_REFERER", reverse("tracker:dashboard"))
        )

    model = model_map[item_type]
    try:
        item = model.objects.get(pk=item_id)
    except model.DoesNotExist:
        if is_ajax:
            return JsonResponse(
                {"status": "error", "message": "Öğe bulunamadı."}, status=404
            )
        messages.error(request, "Belirtilen öğe bulunamadı.")
        return HttpResponseRedirect(
            request.META.get("HTTP_REFERER", reverse("tracker:dashboard"))
        )

    favorites = get_favorited_ids(request)
    favorite_ids_for_type = favorites.get(item_type, [])
    is_currently_favorite = item_id in favorite_ids_for_type
    action_message = ""
    new_favorite_status = False

    if is_currently_favorite:
        favorite_ids_for_type.remove(item_id)
        action_message = f'"{item.title}" favorilerden çıkarıldı.'
        new_favorite_status = False  # Yeni durum: Artık favori değil
    else:
        favorite_ids_for_type.append(item_id)
        action_message = f'"{item.title}" favorilere eklendi.'
        new_favorite_status = True  # Yeni durum: Artık favori

    favorites[item_type] = favorite_ids_for_type
    request.session["favorites"] = favorites
    request.session.modified = True

    # Eğer istek AJAX ve POST ise, JSON yanıtı dön
    if is_ajax and request.method == "POST":
        return JsonResponse({"status": "ok", "is_favorite": new_favorite_status})

    # Eğer istek normal GET ise (veya AJAX olmayan POST), mesaj göster ve yönlendir
    messages.success(request, action_message)
    return HttpResponseRedirect(
        request.META.get("HTTP_REFERER", reverse("tracker:dashboard"))
    )


def favorites_view(request):
    """Favoriye eklenmiş öğeleri listeleyen sayfa."""
    model_map = get_model_map()
    favorites_dict = get_favorited_ids(request)
    favorited_items_list = []
    total_favorites = 0

    url_name_map = {
        model_str: {
            "detail": f"tracker:{model_str}_detail",
            "edit": f"tracker:{model_str}_edit",
            "delete": f"tracker:{model_str}_delete",
        }
        for model_str in model_map.keys()
    }

    for item_type, item_ids in favorites_dict.items():
        if item_ids and item_type in model_map:
            model = model_map[item_type]
            items = list(
                model.objects.filter(pk__in=item_ids).order_by(
                    "-added_date", "title"
                )
            )
            if items:
                favorited_items_list.append(
                    (item_type, items, url_name_map.get(item_type))
                )
                total_favorites += len(items)

    context = {
        "favorited_items_list": favorited_items_list,
        "total_favorites": total_favorites,
    }
    return render(request, "tracker/favorites.html", context)


# --- YARDIMCI İŞLEM FONKSİYONLARI ---

# _process_list_view, _process_edit_view, _process_delete_view, _render_detail_view
# fonksiyonları AJAX değişikliğinden etkilenmez, aynı kalır.
# Kod formatı düzenlenmiştir.


def _process_list_view(
    request, model, form_class, template_name, redirect_url_name, paginate_by=15
):
    """Liste görünümü ve form işleme için ortak mantık."""
    status_filter = request.GET.get("status", "")
    search_query = request.GET.get("q", "")
    sort_by = request.GET.get("sort", "-added_date")

    queryset = model.objects.all()
    if status_filter:
        queryset = queryset.filter(status=status_filter)
    if search_query:
        queryset = queryset.filter(title__icontains=search_query)

    queryset = apply_sorting(queryset, sort_by)

    paginator = Paginator(queryset, paginate_by)
    page_number = request.GET.get("page")
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    if request.method == "POST":
        form = form_class(request.POST)
        if form.is_valid():
            instance = form.save()
            model_verbose_name = model._meta.verbose_name.capitalize()
            messages.success(
                request,
                f'{model_verbose_name} "{instance.title}" başarıyla eklendi.',
            )
            return redirect(redirect_url_name)
        else:
            messages.error(
                request,
                "Formda hatalar var. Lütfen işaretli alanları kontrol edin.",
            )
    else:
        form = form_class()

    existing_params = request.GET.copy()
    if "page" in existing_params:
        del existing_params["page"]
    params_encoded = existing_params.urlencode()

    favorites_dict = get_favorited_ids(request)
    item_type_str = model.__name__.lower()
    favorited_in_this_list = set(favorites_dict.get(item_type_str, []))

    context = {
        "page_obj": page_obj,
        "paginator": paginator,
        "form": form,
        "status_choices": model.STATUS_CHOICES,
        "current_status_filter": status_filter,
        "search_query": search_query,
        "current_sort": sort_by,
        "params_encoded": params_encoded,
        "model_name_plural": model._meta.verbose_name_plural.capitalize(),
        "favorited_ids": favorited_in_this_list,
        "item_type": item_type_str,
    }
    return render(request, template_name, context)


def _process_edit_view(
    request, pk, model, form_class, template_name, redirect_url_name
):
    """Düzenleme görünümü için ortak mantık."""
    instance = get_object_or_404(model, pk=pk)
    model_verbose_name = model._meta.verbose_name.capitalize()

    if request.method == "POST":
        form = form_class(request.POST, instance=instance)
        if form.is_valid():
            saved_instance = form.save()
            messages.success(
                request,
                f'{model_verbose_name} "{saved_instance.title}" başarıyla güncellendi.',
            )
            return redirect(redirect_url_name)
        else:
            messages.error(
                request,
                "Formda hatalar var. Lütfen işaretli alanları kontrol edin.",
            )
    else:
        form = form_class(instance=instance)

    context = {
        "form": form,
        "item": instance,
        "model_name": model_verbose_name,
    }
    return render(request, template_name, context)


def _process_delete_view(request, pk, model, redirect_url_name):
    """Silme onayı ve işlemi için ortak mantık."""
    instance = get_object_or_404(model, pk=pk)
    model_verbose_name = model._meta.verbose_name.capitalize()

    if request.method == "POST":
        title = instance.title
        favorites = get_favorited_ids(request)
        item_type_str = model.__name__.lower()
        if item_type_str in favorites and pk in favorites[item_type_str]:
            favorites[item_type_str].remove(pk)
            request.session["favorites"] = favorites
            request.session.modified = True

        instance.delete()
        messages.success(
            request, f'{model_verbose_name} "{title}" başarıyla silindi.'
        )
        return redirect(redirect_url_name)

    context = {
        "item": instance,
        "model_name": model_verbose_name,
    }
    return render(request, "tracker/confirm_delete_base.html", context)


def _render_detail_view(request, pk, model):
    """Ortak detay view render mantığı."""
    instance = get_object_or_404(model, pk=pk)
    model_name_lower = model.__name__.lower()
    favorites_dict = get_favorited_ids(request)
    is_favorite = pk in favorites_dict.get(model_name_lower, [])

    context = {
        "item": instance,
        "model_name": model._meta.verbose_name.capitalize(),
        "item_type": model_name_lower,
        "is_favorite": is_favorite,
    }
    return render(request, "tracker/detail_base.html", context)


# --- CRUD VIEW FONKSİYONLARI ---

# Anime
def anime_list_and_create(request):
    return _process_list_view(
        request,
        Anime,
        AnimeForm,
        "tracker/anime_list.html",
        "tracker:anime_list_view",
    )

def anime_edit(request, pk):
    return _process_edit_view(
        request,
        pk,
        Anime,
        AnimeForm,
        "tracker/anime_form.html",
        "tracker:anime_list_view",
    )

def anime_delete(request, pk):
    return _process_delete_view(request, pk, Anime, "tracker:anime_list_view")

def anime_detail(request, pk):
    return _render_detail_view(request, pk, Anime)


# Webtoon
def webtoon_list_and_create(request):
    return _process_list_view(
        request,
        Webtoon,
        WebtoonForm,
        "tracker/webtoon_list.html",
        "tracker:webtoon_list_view",
    )

def webtoon_edit(request, pk):
    return _process_edit_view(
        request,
        pk,
        Webtoon,
        WebtoonForm,
        "tracker/webtoon_form.html",
        "tracker:webtoon_list_view",
    )

def webtoon_delete(request, pk):
    return _process_delete_view(
        request, pk, Webtoon, "tracker:webtoon_list_view"
    )

def webtoon_detail(request, pk):
    return _render_detail_view(request, pk, Webtoon)


# Manga
def manga_list_and_create(request):
    return _process_list_view(
        request,
        Manga,
        MangaForm,
        "tracker/manga_list.html",
        "tracker:manga_list_view",
    )

def manga_edit(request, pk):
    return _process_edit_view(
        request,
        pk,
        Manga,
        MangaForm,
        "tracker/manga_form.html",
        "tracker:manga_list_view",
    )

def manga_delete(request, pk):
    return _process_delete_view(request, pk, Manga, "tracker:manga_list_view")

def manga_detail(request, pk):
    return _render_detail_view(request, pk, Manga)


# Novel
def novel_list_and_create(request):
    return _process_list_view(
        request,
        Novel,
        NovelForm,
        "tracker/novel_list.html",
        "tracker:novel_list_view",
    )

def novel_edit(request, pk):
    return _process_edit_view(
        request,
        pk,
        Novel,
        NovelForm,
        "tracker/novel_form.html",
        "tracker:novel_list_view",
    )

def novel_delete(request, pk):
    return _process_delete_view(request, pk, Novel, "tracker:novel_list_view")

def novel_detail(request, pk):
    return _render_detail_view(request, pk, Novel)


# --- CSV EXPORT GÖRÜNÜMLERİ ---

# _export_csv fonksiyonu AJAX değişikliğinden etkilenmez, aynı kalır.
# Kod formatı düzenlenmiştir.

def _export_csv(request, model, filename_prefix, fields_map):
    """Genel CSV export fonksiyonu."""
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response.write("\ufeff".encode("utf8"))
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")

    status_filter = request.GET.get("status", "")
    search_query = request.GET.get("q", "")

    filename_suffix = ""
    if status_filter:
        filename_suffix += f"_durum-{status_filter.replace(' ', '_')}"
    if search_query:
        filename_suffix += "_arama"
    filename = f"{filename_prefix}_export_{timestamp}{filename_suffix}.csv"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    writer = csv.writer(
        response, delimiter=";", quotechar='"', quoting=csv.QUOTE_MINIMAL
    )

    header = list(fields_map.values())
    writer.writerow(header)

    queryset = model.objects.all()
    if status_filter:
        queryset = queryset.filter(status=status_filter)
    if search_query:
        queryset = queryset.filter(title__icontains=search_query)
    queryset = queryset.order_by("-added_date", "title")

    for item in queryset:
        row = []
        for field_name, _ in fields_map.items():
            value = ""
            try:
                if hasattr(item, field_name) and callable(
                    getattr(item, field_name)
                ):
                    value = getattr(item, field_name)()
                else:
                    value = getattr(item, field_name, "")
            except Exception as e:
                print(f"CSV Export Hatası ({field_name}): {e}")
                value = "HATA"

            if isinstance(value, datetime.datetime):
                value = value.strftime("%Y-%m-%d %H:%M:%S") if value else ""
            elif isinstance(value, datetime.date):
                value = value.strftime("%Y-%m-%d") if value else ""
            elif value is None:
                value = ""
            row.append(str(value))
        writer.writerow(row)

    return response


def export_anime_csv(request):
    fields = {
        "pk": "ID",
        "title": "Baslik",
        "get_status_display": "Durum",
        "rating": "Puan",
        "studio": "Stüdyo",
        "episodes_watched": "Izlenen Bolum",
        "total_episodes": "Toplam Bolum",
        "start_date": "Baslama Tarihi",
        "end_date": "Bitirme Tarihi",
        "added_date": "Eklenme Tarihi",
        "notes": "Notlar",
        "cover_image_url": "Kapak URL",
    }
    return _export_csv(request, Anime, "anime", fields)


def export_webtoon_csv(request):
    fields = {
        "pk": "ID",
        "title": "Baslik",
        "get_status_display": "Durum",
        "rating": "Puan",
        "author": "Yazar",
        "artist": "Cizer",
        "chapters_read": "Okunan Bolum",
        "total_chapters": "Toplam Bolum",
        "platform": "Platform",
        "start_date": "Baslama Tarihi",
        "end_date": "Bitirme Tarihi",
        "added_date": "Eklenme Tarihi",
        "notes": "Notlar",
        "cover_image_url": "Kapak URL",
    }
    return _export_csv(request, Webtoon, "webtoon", fields)


def export_manga_csv(request):
    fields = {
        "pk": "ID",
        "title": "Baslik",
        "get_status_display": "Durum",
        "rating": "Puan",
        "author": "Yazar",
        "artist": "Cizer",
        "chapters_read": "Okunan Bolum",
        "volumes_read": "Okunan Cilt",
        "total_chapters": "Toplam Bolum",
        "total_volumes": "Toplam Cilt",
        "start_date": "Baslama Tarihi",
        "end_date": "Bitirme Tarihi",
        "added_date": "Eklenme Tarihi",
        "notes": "Notlar",
        "cover_image_url": "Kapak URL",
    }
    return _export_csv(request, Manga, "manga", fields)


def export_novel_csv(request):
    fields = {
        "pk": "ID",
        "title": "Baslik",
        "get_status_display": "Durum",
        "rating": "Puan",
        "author": "Yazar",
        "chapters_read": "Okunan Bolum",
        "volumes_read": "Okunan Cilt",
        "total_chapters": "Toplam Bolum",
        "total_volumes": "Toplam Cilt",
        "start_date": "Baslama Tarihi",
        "end_date": "Bitirme Tarihi",
        "added_date": "Eklenme Tarihi",
        "notes": "Notlar",
        "cover_image_url": "Kapak URL",
    }
    return _export_csv(request, Novel, "novel", fields)