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
from django.urls import reverse, reverse_lazy
from django.views.decorators.http import require_http_methods # require_http_methods gerekli
from django.utils import timezone # DÜZELTME: timezone import edildi

# Formları import et
from .forms import AnimeForm, MangaForm, NovelForm, WebtoonForm

# Modelleri import et
from .models import Anime, Manga, Novel, Webtoon, Favorite # Favorite gerekli

# YENİ: MangaDex Servisini import et
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
    # Puanlamaya göre sıralarken None değerleri sona at
    if order_field == "rating_desc":
        # F() objesi ile nulls_last=True kullanarak None değerleri sona atıyoruz
        return queryset.order_by(F("rating").desc(nulls_last=True), "-added_date")
    elif order_field == "rating_asc":
        return queryset.order_by(F("rating").asc(nulls_last=True), "-added_date")
    else:
        return queryset.order_by(order_field)

# DÜZELTME: _process_list_view fonksiyonundaki POST mantığı düzeltildi
def _process_list_view(
    request, model, form_class, template_name, redirect_url_name, paginate_by=15
):
    """Liste görünümü ve form işleme için ortak mantık (Kullanıcıya Özel + Favori Bilgisi)."""
    # --- GET İsteği İşlemleri (Sıralama, Filtreleme, Sayfalama) ---
    status_filter = request.GET.get("status", "")
    search_query = request.GET.get("q", "")
    sort_by = request.GET.get("sort", "-added_date") # Varsayılan sıralama

    # Sadece giriş yapmış kullanıcının öğelerini al
    # DİKKAT: Giriş yapmamış kullanıcılar bu view'a gelmemeli (@login_required ile)
    # Bu yüzden filter(user=request.user) güvenli.
    queryset = model.objects.filter(user=request.user)

    # Filtreleme uygula
    if status_filter:
        queryset = queryset.filter(status=status_filter)
    if search_query:
        queryset = queryset.filter(title__icontains=search_query) # Başlıkta arama

    # Sıralamayı uygula
    queryset = apply_sorting(queryset, sort_by)

    # Sayfalama
    paginator = Paginator(queryset, paginate_by)
    page_number = request.GET.get("page")
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    # --- POST İsteği İşlemleri (Yeni öğe ekleme - Manuel) ---
    form = None # Formu başlangıçta None yap
    if request.method == "POST":
        # API'dan ekleme POST'ları buraya gelmemeli, onlar kendi view'larında.
        # Bu kontrol _process_list_view'ın sadece manuel eklemeyi işlemesini sağlar.
        # Eğer API arama formu da bu view'a POST yapıyorsa, formları ayırt etmek için
        # form içinde gizli bir alan veya buton adı kullanılabilir. Şimdilik ayırdığımızı varsayıyoruz.

        # DÜZELTME: Formu POST verisiyle burada oluştur
        form = form_class(request.POST)
        if form.is_valid():
            instance = form.save(commit=False)
            instance.user = request.user # Öğeyi mevcut kullanıcıya ata
            # Manuel eklemede API ID'leri boş kalacak
            instance.save()
            messages.success(request, f'{model._meta.verbose_name.capitalize()} "{instance.title}" başarıyla eklendi.')
            # Başarılı kayıttan sonra YÖNLENDİRME yapılıyor
            return redirect(redirect_url_name)
        else:
            # Form geçerli değilse hata mesajı göster (yönlendirme yok)
            messages.error(request, "Formda hatalar var. Lütfen işaretli alanları kontrol edin.")
            # Hatalı form template'e gönderilecek (aşağıda context'e ekleniyor)
    else:
        # GET isteği için boş form
        form = form_class()

    # --- Context Hazırlama ---
    # Sayfalama linkleri için mevcut GET parametrelerini koru
    existing_params = request.GET.copy()
    if "page" in existing_params:
        del existing_params["page"]
    params_encoded = existing_params.urlencode()

    # Görüntülenen sayfadaki öğelerin favori durumunu al (PK'larını set olarak)
    favorited_pks = set()
    if request.user.is_authenticated and page_obj.object_list:
        item_ids = [item.pk for item in page_obj.object_list]
        try:
            content_type = ContentType.objects.get_for_model(model)
            favorited_pks = set(Favorite.objects.filter(
                user=request.user, content_type=content_type, object_id__in=item_ids
            ).values_list('object_id', flat=True))
        except ContentType.DoesNotExist:
            messages.error(request, "İçerik türü hatası.") # Bu mesaj kullanıcıya gösterilmeyebilir

    context = {
        "page_obj": page_obj,
        "paginator": paginator,
        "form": form, # POST ise hatalı formu, GET ise boş formu içerir (Manuel ekleme için)
        "status_choices": model.STATUS_CHOICES,
        "current_status_filter": status_filter,
        "search_query": search_query,
        "current_sort": sort_by,
        "params_encoded": params_encoded, # Sayfalama için
        "model_name_plural": model._meta.verbose_name_plural.capitalize(),
        "favorited_pks": favorited_pks, # Favori butonları için (set olarak gönderiliyor)
        "item_type_str": model.__name__.lower(), # Favori butonları için
        "list_url_name": redirect_url_name, # _list_controls partial'ı için
        "export_url_name": f"tracker:export_{model.__name__.lower()}_csv", # _list_controls partial'ı için
        # YENİ: API arama URL'sini template'e gönderebiliriz
        "api_search_url_name": f"tracker:{model.__name__.lower()}_api_search" if model in [Manga, Webtoon] else None
    }
    # GET veya hatalı POST durumunda render et (status 200)
    return render(request, template_name, context)

# Diğer yardımcı fonksiyonlar (_process_edit_view, _process_delete_view, vb.) aynı kalabilir.

def _process_edit_view(
    request, pk, model, form_class, template_name, redirect_url_name
):
    """Düzenleme görünümü için ortak mantık (Kullanıcıya Özel)."""
    instance = get_object_or_404(model, pk=pk, user=request.user) # Sadece kendi öğesini düzenleyebilir
    model_verbose_name = model._meta.verbose_name.capitalize()

    if request.method == "POST":
        form = form_class(request.POST, instance=instance)
        if form.is_valid():
            saved_instance = form.save()
            messages.success(request, f'{model_verbose_name} "{saved_instance.title}" başarıyla güncellendi.')
            # Başarılı düzenleme sonrası listeye yönlendir
            return redirect(redirect_url_name)
        else:
            messages.error(request, "Formda hatalar var. Lütfen işaretli alanları kontrol edin.")
    else:
        # GET isteği için mevcut veriyle dolu formu göster
        form = form_class(instance=instance)

    context = {"form": form, "item": instance, "model_name": model_verbose_name}
    return render(request, template_name, context)

def _process_delete_view(request, pk, model, redirect_url_name):
    """Silme onayı ve işlemi için ortak mantık (Kullanıcıya Özel)."""
    instance = get_object_or_404(model, pk=pk, user=request.user) # Sadece kendi öğesini silebilir
    model_verbose_name = model._meta.verbose_name.capitalize()

    if request.method == "POST":
        title = instance.title
        instance.delete()
        messages.success(request, f'{model_verbose_name} "{title}" başarıyla silindi.')
        # Başarılı silme sonrası listeye yönlendir
        return redirect(redirect_url_name)

    # GET isteği için onay sayfasını göster
    context = {"item": instance, "model_name": model_verbose_name}
    return render(request, "tracker/confirm_delete_base.html", context)

def _render_detail_view(request, pk, model):
    """Ortak detay view render mantığı (Herkes görebilir + Favori Bilgisi)."""
    # Herkesin eklediği görülebilir/favorilenebilir
    instance = get_object_or_404(model, pk=pk)
    model_name_lower = model.__name__.lower()
    is_favorite = False
    # Favori durumunu kontrol et (giriş yapmışsa)
    if request.user.is_authenticated:
        try:
            content_type = ContentType.objects.get_for_model(model)
            is_favorite = Favorite.objects.filter(
                user=request.user, content_type=content_type, object_id=instance.pk
            ).exists()
        except ContentType.DoesNotExist:
            messages.error(request, "İçerik türü hatası.") # Bu pek görünmez

    context = {
        "item": instance,
        "model_name": model._meta.verbose_name.capitalize(),
        "item_type": model_name_lower, # Favori butonu ve URL'ler için
        "is_favorite": is_favorite, # Favori butonu için
        # DİKKAT: Şablonda (detail_base.html) düzenle/sil butonlarını sadece sahibi görsün diye kontrol ekle
        "is_owner": request.user == instance.user if request.user.is_authenticated else False
    }
    return render(request, "tracker/detail_base.html", context)

def _export_csv(request, model, filename_prefix, fields_map):
    """Genel CSV export fonksiyonu (Kullanıcıya Özel)."""
    # Sadece giriş yapmış kullanıcı kendi verisini export edebilir
    if not request.user.is_authenticated:
        # Normalde @login_required bunu engeller ama ekstra kontrol
        return HttpResponse("Yetkisiz Erişim", status=401)

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response.write("\ufeff".encode("utf8")) # Excel uyumluluğu için BOM
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    status_filter = request.GET.get("status", "")
    search_query = request.GET.get("q", "")
    filename_suffix = ""
    if status_filter: filename_suffix += f"_durum-{status_filter.replace(' ', '_')}"
    if search_query: filename_suffix += f"_arama-{search_query[:15].replace(' ','_')}" # Arama terimini de ekle (kısaltılmış)

    filename = f"{filename_prefix}_export_{timestamp}{filename_suffix}.csv"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    writer = csv.writer(response, delimiter=";", quotechar='"', quoting=csv.QUOTE_MINIMAL)
    header = list(fields_map.values())
    writer.writerow(header)

    queryset = model.objects.filter(user=request.user) # Sadece kullanıcının kendi öğeleri
    if status_filter: queryset = queryset.filter(status=status_filter)
    if search_query: queryset = queryset.filter(title__icontains=search_query)
    queryset = queryset.order_by("-added_date", "title") # Mantıklı bir sıralama

    for item in queryset:
        row = []
        for field_name, _ in fields_map.items():
            value = ""
            try:
                # get_status_display gibi metodları çağırmak için
                if field_name == 'get_status_display': # Özel durum
                    value = item.get_status_display()
                # user gibi ilişkili alanları almak için (str ile)
                elif '__' in field_name: # Örneğin 'user__username' gibi (şu an kullanılmıyor ama ileride gerekebilir)
                    related_attrs = field_name.split('__')
                    related_obj = item
                    for attr in related_attrs:
                        related_obj = getattr(related_obj, attr, None)
                        if related_obj is None: break
                    value = str(related_obj) if related_obj is not None else ""
                # Diğer normal alanlar
                else:
                    value = getattr(item, field_name, "")
            except Exception as e:
                print(f"CSV Export Hatası ({model.__name__} - {field_name}): {e}")
                value = "HATA" # Hata durumunda belirt

            # Tarih ve None formatlama
            if isinstance(value, datetime.datetime):
                # Zaman dilimi farkında ise yerel saate çevir (settings.TIME_ZONE)
                if timezone.is_aware(value): # DÜZELTME: timezone kullanılıyor
                    value = timezone.localtime(value) # DÜZELTME: timezone kullanılıyor
                value = value.strftime("%Y-%m-%d %H:%M:%S") if value else ""
            elif isinstance(value, datetime.date):
                value = value.strftime("%Y-%m-%d") if value else ""
            elif value is None:
                value = ""
            # Satıra ekle (string olarak)
            row.append(str(value))
        writer.writerow(row)

    return response

# ==============================================================================
# 2. ANA VIEW FONKSİYONLARI
# ==============================================================================

@login_required # Giriş gerektirir
def dashboard_view(request):
    """Dashboard sayfasını gösterir, kullanıcının genel istatistiklerini içerir."""
    user = request.user
    # Kullanıcıya ait verileri al
    anime_count = Anime.objects.filter(user=user).count()
    webtoon_count = Webtoon.objects.filter(user=user).count()
    manga_count = Manga.objects.filter(user=user).count()
    novel_count = Novel.objects.filter(user=user).count()

    # Son eklenenler (performans için sadece gerekli alanları seçebiliriz - .values() veya only()/defer())
    recent_anime = Anime.objects.filter(user=user).order_by("-added_date")[:5]
    recent_webtoons = Webtoon.objects.filter(user=user).order_by("-added_date")[:5]
    recent_mangas = Manga.objects.filter(user=user).order_by("-added_date")[:5]
    recent_novels = Novel.objects.filter(user=user).order_by("-added_date")[:5]

    # En yüksek puanlılar (apply_sorting helper'ını kullanalım)
    top_anime = apply_sorting(Anime.objects.filter(user=user, rating__isnull=False), "rating_desc")[:5]
    top_webtoons = apply_sorting(Webtoon.objects.filter(user=user, rating__isnull=False), "rating_desc")[:5]
    top_mangas = apply_sorting(Manga.objects.filter(user=user, rating__isnull=False), "rating_desc")[:5]
    top_novels = apply_sorting(Novel.objects.filter(user=user, rating__isnull=False), "rating_desc")[:5]

    # Grafik verileri için hazırlık
    type_labels = ["Anime", "Webtoon", "Manga", "Novel"]
    type_counts = [anime_count, webtoon_count, manga_count, novel_count]

    # Durum grafiği için tüm modellerdeki durumları topla
    status_choices = Anime.STATUS_CHOICES # Her modelde aynı olduğunu varsayıyoruz
    status_counts_dict = {status_value: 0 for status_value, _ in status_choices}
    all_models = [Anime, Webtoon, Manga, Novel]
    for model in all_models:
        counts = (
            model.objects.filter(user=user)
            .values("status")
            .annotate(count=Count("id"))
            .order_by("status") # Gruplama için gerekli değil ama tutarlı olabilir
        )
        for item in counts:
            if item["status"] in status_counts_dict:
                status_counts_dict[item["status"]] += item["count"]

    status_labels = [display for _, display in status_choices]
    status_data = [status_counts_dict[value] for value, _ in status_choices]

    chart_data = {
        "typeLabels": type_labels, "typeCounts": type_counts,
        "statusLabels": status_labels, "statusData": status_data,
    }

    context = {
        # Sayılar
        "anime_count": anime_count, "webtoon_count": webtoon_count,
        "manga_count": manga_count, "novel_count": novel_count,
        # Listeler
        "recent_anime": recent_anime, "recent_webtoons": recent_webtoons,
        "recent_mangas": recent_mangas, "recent_novels": recent_novels,
        "top_anime": top_anime, "top_webtoons": top_webtoons,
        "top_mangas": top_mangas, "top_novels": top_novels,
        # Grafik verisi (JSON'a çevrilecek)
        "chart_data_json": json.dumps(chart_data),
    }
    return render(request, "tracker/dashboard.html", context)

# DİKKAT: signup_view fonksiyonundaki POST mantığını kontrol edelim
def signup_view(request):
    """Kullanıcı kayıt sayfası."""
    # Giriş yapmış kullanıcıyı dashboard'a yönlendir
    if request.user.is_authenticated:
        return redirect('tracker:dashboard')

    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            # DİKKAT: Kullanıcı başarıyla oluşturuluyor mu?
            form.save()
            username = form.cleaned_data.get('username')
            messages.success(request, f'Hesap "{username}" başarıyla oluşturuldu! Giriş yapabilirsiniz.')
            # Başarılı kayıt sonrası login sayfasına yönlendir
            return redirect('login')
        else:
            # DİKKAT: Form geçersizse hata mesajı gösteriliyor (test bunu yakalayabilir)
            messages.error(request, 'Lütfen formdaki hataları düzeltin.')
    else:
        # GET isteği için boş form
        form = UserCreationForm()

    # GET veya hatalı POST durumunda formu render et
    return render(request, 'registration/signup.html', {'form': form})

@login_required
@require_http_methods(["POST"]) # Sadece POST isteklerini kabul et
def toggle_favorite(request):
    """Bir öğeyi favorilere ekler veya çıkarır (AJAX POST)."""
    try:
        # İsteğin gövdesinden JSON verisini al
        data = json.loads(request.body)
        item_type_str = data.get('item_type')
        item_id = data.get('item_id')

        if not item_type_str or not item_id:
            return JsonResponse({'status': 'error', 'message': 'Eksik parametre.'}, status=400)

        # item_type_str'den ContentType'ı al
        try:
            # Model adının küçük harf olduğundan emin ol
            content_type = ContentType.objects.get(model=item_type_str.lower())
        except ContentType.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Geçersiz öğe türü.'}, status=400)

        # İlgili modelin varlığını kontrol et (opsiyonel ama iyi pratik)
        model_class = content_type.model_class()
        # get_object_or_404 yerine exists() kullanmak daha verimli olabilir
        if not model_class.objects.filter(pk=item_id).exists():
            return JsonResponse({'status': 'error', 'message': 'Öğe bulunamadı.'}, status=404)

        # Favoriyi bul veya oluştur (get_or_create)
        favorite, created = Favorite.objects.get_or_create(
            user=request.user,
            content_type=content_type,
            object_id=item_id
        )

        is_favorite_now = False
        if created:
            # Yeni oluşturulduysa, artık favori
            is_favorite_now = True
        else:
            # Zaten varsa, sil (favoriden çıkar)
            favorite.delete()
            is_favorite_now = False

        # Başarılı yanıtı JSON olarak döndür
        return JsonResponse({'status': 'ok', 'is_favorite': is_favorite_now})

    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Geçersiz JSON.'}, status=400)
    except Exception as e:
        # Beklenmedik hataları loglamak iyi olur
        print(f"Toggle Favorite Error: {e}")
        return JsonResponse({'status': 'error', 'message': 'Bir sunucu hatası oluştu.'}, status=500)

@login_required
def favorites_view(request):
    """Giriş yapmış kullanıcının favori öğelerini listeler."""
    user = request.user
    # Kullanıcının tüm favorilerini al (performans için content_type'ı önceden çek)
    user_favorites = Favorite.objects.filter(user=user).select_related('content_type')

    # Favorileri türe göre gruplamak için ID'leri topla
    favorite_ids_by_type = {'anime': [], 'webtoon': [], 'manga': [], 'novel': []}
    for fav in user_favorites:
        model_name = fav.content_type.model # 'anime', 'webtoon' vb.
        if model_name in favorite_ids_by_type:
            favorite_ids_by_type[model_name].append(fav.object_id)

    # Her tür için ilgili nesneleri veritabanından çek
    models_map = {'anime': Anime, 'webtoon': Webtoon, 'manga': Manga, 'novel': Novel}
    grouped_favorites = {} # Sonuçları saklayacak dictionary
    all_favorited_pks = set() # DÜZELTME: Tüm favori PK'larını toplamak için set
    for model_name, ids in favorite_ids_by_type.items():
        if ids: # Eğer o türde favori varsa
            model_class = models_map.get(model_name)
            if model_class:
                # İlgili ID'lere sahip öğeleri çek ve sırala
                items = list(model_class.objects.filter(pk__in=ids).order_by('-added_date', 'title'))
                grouped_favorites[model_name] = items
                # DÜZELTME: Bu türdeki favori PK'ları genel sete ekle
                all_favorited_pks.update(ids)

    # Şablona göndermek için listeye çevir (sadece içinde öğe olanları)
    grouped_favorites_list = [
        (k, v) for k, v in grouped_favorites.items() if v
    ]
    # Anahtara göre sırala (opsiyonel, A-W-M-N sırası için)
    grouped_favorites_list.sort(key=lambda x: list(models_map.keys()).index(x[0]))


    total_favorites = user_favorites.count()

    context = {
        # Şablonda kullanılacak liste [(tür_adı, [öğe1, öğe2,...]), ...]
        'grouped_favorites_list': grouped_favorites_list,
        'total_favorites': total_favorites,
        # DÜZELTME: _list_item partial'ı için tüm favori PK'larını içeren seti gönder
        'favorited_pks': all_favorited_pks,
    }
    return render(request, "tracker/favorites.html", context)


# --- Anime CRUD View'ları (Yardımcı fonksiyonları kullanır) ---
@login_required
def anime_list_and_create(request):
    return _process_list_view(request, Anime, AnimeForm, "tracker/anime_list.html", "tracker:anime_list_view")
@login_required
def anime_edit(request, pk):
    return _process_edit_view(request, pk, Anime, AnimeForm, "tracker/anime_form.html", "tracker:anime_list_view") # Yönlendirme listeye
@login_required
def anime_delete(request, pk):
    return _process_delete_view(request, pk, Anime, "tracker:anime_list_view")
@login_required # Detay için de login gerekli mi? Şu anki koda göre evet.
def anime_detail(request, pk):
    return _render_detail_view(request, pk, Anime)

# --- Webtoon CRUD View'ları ---
@login_required
def webtoon_list_and_create(request):
    # DİKKAT: API entegrasyonu eklenirse, bu view _process_list_view'ı doğrudan çağırmak yerine
    # belki yeni API arama view'ına bir link göstermeli veya farklı çalışmalı.
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
    # DİKKAT: API entegrasyonu eklenirse, bu view _process_list_view'ı doğrudan çağırmak yerine
    # belki yeni API arama view'ına bir link göstermeli veya farklı çalışmalı.
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
# YENİ: MangaDex API View Fonksiyonları
# ==============================================================================

@login_required
def manga_api_search_view(request):
    """MangaDex API'da arama yapmak için formu gösterir ve arama yapar."""
    context = {
        'search_results': None,
        'query': None,
    }
    if request.method == 'POST':
        query = request.POST.get('query', '').strip()
        if query:
            context['query'] = query
            # MangaDex servisini kullanarak arama yap
            results = mangadex_service.search_manga(query)
            if results is None: # API hatası varsa
                 messages.error(request, "MangaDex API'ına bağlanırken bir hata oluştu. Lütfen tekrar deneyin.")
                 context['search_results'] = None
            elif not results: # Sonuç bulunamadıysa
                messages.warning(request, f"'{query}' için MangaDex üzerinde sonuç bulunamadı.")
                context['search_results'] = [] # Boş liste gönderelim
            else:
                 context['search_results'] = results
                 messages.success(request, f"'{query}' için {len(results)} sonuç bulundu.")
        else:
            messages.warning(request, "Lütfen aramak için bir başlık girin.")

        # POST isteği sonrası sonuçları aynı template'te gösterelim
        # Template adı varsayılan: 'tracker/manga_api_search.html'
        return render(request, 'tracker/manga_api_search.html', context)

    # GET isteği için sadece boş formu göster
    # Template adı varsayılan: 'tracker/manga_api_search.html'
    return render(request, 'tracker/manga_api_search.html', context)

@login_required
def manga_add_from_api_view(request, mangadex_id):
    """Seçilen MangaDex ID'si ile manga detaylarını getirir, formu doldurur ve kaydeder."""
    # 1. MangaDex'ten detayları al
    # MangaDex ID'si UUID olduğu için str() kullanmak iyi olabilir
    initial_data = mangadex_service.get_manga_details(str(mangadex_id))

    if initial_data is None:
        messages.error(request, "Manga detayları MangaDex API'sından alınamadı veya manga bulunamadı.")
        return redirect('tracker:manga_api_search') # Arama sayfasına geri dön

    # Bu ID ile veritabanında zaten kayıt var mı diye kontrol et
    # Hem Manga hem Webtoon modellerini kontrol etmeliyiz!
    existing_item = Manga.objects.filter(mangadex_id=mangadex_id, user=request.user).first()
    if not existing_item:
        existing_item = Webtoon.objects.filter(mangadex_id=mangadex_id, user=request.user).first()

    if existing_item:
        item_type_name = "Manga" if isinstance(existing_item, Manga) else "Webtoon"
        messages.info(request, f"'{existing_item.title}' ({item_type_name}) zaten listenizde mevcut.")
        # Mevcut kaydın detayına yönlendir
        detail_url_name = f'tracker:{item_type_name.lower()}_detail'
        return redirect(detail_url_name, pk=existing_item.pk)

    # Hangi formu kullanacağımıza karar ver (Manga mı, Webtoon mu?)
    # `map_mangadex_data_to_dict` içinde bir 'is_webtoon' anahtarı eklediysek onu kullanabiliriz
    # Veya burada tekrar API verisine bakabiliriz. Şimdilik varsayılan MangaForm.
    # TODO: Webtoon ayrımı için logic eklenecek.
    FormClass = MangaForm
    ModelClass = Manga
    model_verbose_name = "Manga" # Mesajlar için
    form_template = 'tracker/manga_form_api.html' # Ayrı bir template kullanacağız

    if request.method == 'POST':
        form = FormClass(request.POST) # Yeni kayıt, instance yok

        if form.is_valid():
            instance = form.save(commit=False)
            instance.user = request.user
            instance.mangadex_id = mangadex_id # UUID'yi ata
            # Formda olmayan ama API'dan gelen diğer alanları da atayabiliriz (örn. total_chapters/volumes None ise)
            # Ancak formun clean metotları API'dan gelen 'None' ile çakışabilir, dikkatli olmalı.
            # Şimdilik sadece ID'yi atayalım.
            instance.save()
            messages.success(request, f"{model_verbose_name} '{instance.title}' başarıyla listenize eklendi.")
            # Başarılı ekleme sonrası listenin olduğu sayfaya veya detaya git
            return redirect('tracker:manga_list_view')
        else:
             messages.error(request, "Formda hatalar var. Lütfen işaretli alanları kontrol edin.")
             # Hatalı formu tekrar gösterirken API verisini kaybetmeyelim
             context = {
                  'form': form,
                  'mangadex_data': initial_data # Başlık, kapak vb. göstermek için
             }
             return render(request, form_template, context)

    # GET isteği: API verisiyle doldurulmuş boş formu göster
    else:
        form = FormClass(initial=initial_data)
        context = {
            'form': form,
            'mangadex_data': initial_data # Template'te başlık, kapak gibi bilgileri göstermek için
        }
        return render(request, form_template, context)

# ==============================================================================
# YENİ VIEW FONKSİYONLARI SONU
# ==============================================================================


# --- CSV EXPORT View'ları ---
# (Bu kısım aynı kalabilir)
@login_required
def export_anime_csv(request):
    # ... (kod aynı) ...
    return _export_csv(request, Anime, "anime", fields)
@login_required
def export_webtoon_csv(request):
    # ... (kod aynı) ...
    return _export_csv(request, Webtoon, "webtoon", fields)
@login_required
def export_manga_csv(request):
    # ... (kod aynı) ...
    return _export_csv(request, Manga, "manga", fields)
@login_required
def export_novel_csv(request):
    # ... (kod aynı) ...
    return _export_csv(request, Novel, "novel", fields)