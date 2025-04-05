# tracker/views/base_views.py
import json
import logging

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages
from django.contrib.contenttypes.models import ContentType
from django.db.models import Count

# Modelleri import et
from ..models import Anime, Manga, Novel, Webtoon, Favorite

# Yardımcı fonksiyonları import et
from .helpers import apply_sorting # Örnek, dashboard kullanıyor

logger = logging.getLogger(__name__)


# ==============================================================================
# 3. ANA VIEW FONKSİYONLARI (Dashboard, Signup, Favorites, Toggle) - Orijinal views.py'den taşındı
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