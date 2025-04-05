# tracker/views/crud_views.py
import logging

from django.shortcuts import render # Sadece render gerekiyorsa
from django.contrib.auth.decorators import login_required
# django.urls import reverse # İşleyici fonksiyonlar içinde kullanılıyor, burada gerekmeyebilir

# Modelleri ve Formları import et
from ..models import Anime, Manga, Novel, Webtoon
from ..forms import AnimeForm, MangaForm, NovelForm, WebtoonForm

# Yardımcı fonksiyonları import et
from .helpers import (
    _process_list_view,
    _process_edit_view,
    _process_delete_view,
    _render_detail_view,
)

logger = logging.getLogger(__name__)


# ==============================================================================
# 4. CRUD VIEW'LARI (Refactored - İşleyici Fonksiyonları Kullanıyor) - Orijinal views.py'den taşındı
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