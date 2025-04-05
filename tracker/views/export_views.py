# tracker/views/export_views.py
import logging

from django.contrib.auth.decorators import login_required

# Modelleri import et
from ..models import Anime, Manga, Novel, Webtoon

# Yardımcı fonksiyonları import et
from .helpers import _export_csv

logger = logging.getLogger(__name__)


# ==============================================================================
# 5. API VE EXPORT VIEW'LARI (Export kısmı) - Orijinal views.py'den taşındı
# ==============================================================================

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