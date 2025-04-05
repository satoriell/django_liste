# tracker/urls.py
# Konum: /home/admin/App/django_liste/tracker/urls.py

from django.urls import path
# YENİ: UUID tipini import et
import uuid
from . import views # signup_view ve yeni view'ları import edilmiş olmalı

# Uygulama ad alanı (namespace) - URL'leri tersine çevirirken kullanılır
app_name = "tracker"

urlpatterns = [
    # --- Dashboard ---
    path("", views.dashboard_view, name="dashboard"),

    # --- Kayıt (Signup) ---
    path("accounts/signup/", views.signup_view, name="signup"),

    # --- Favori URL'leri (Veritabanı Tabanlı) ---
    path("favorite/toggle/", views.toggle_favorite, name="toggle_favorite"),
    path("favorites/", views.favorites_view, name="favorites_view"),

    # --- YENİ: MangaDex API Arama ve Ekleme URL'leri ---
    path("manga/search-api/", views.manga_api_search_view, name="manga_api_search"),
    # Arama sonuçları GET ile aynı view'da gösterilebilir veya ayrı bir URL olabilir.
    # Şimdilik aynı view'da (manga_api_search_view) hem GET (form) hem POST (arama) yapısını kuralım.
    path("manga/add-from-api/<uuid:mangadex_id>/", views.manga_add_from_api_view, name="manga_add_from_api"),
    # ----------------------------------------------------
    # --- YENİ: Webtoon için de benzerleri eklenebilir ---
    # path("webtoon/search-api/", views.webtoon_api_search_view, name="webtoon_api_search"),
    # path("webtoon/add-from-api/<uuid:mangadex_id>/", views.webtoon_add_from_api_view, name="webtoon_add_from_api"),
    # ----------------------------------------------------

    # --- Anime URL'leri ---
    path("anime/", views.anime_list_and_create, name="anime_list_view"),
    path("anime/<int:pk>/", views.anime_detail, name="anime_detail"),
    path("anime/<int:pk>/edit/", views.anime_edit, name="anime_edit"),
    path("anime/<int:pk>/delete/", views.anime_delete, name="anime_delete"),
    path("anime/export/csv/", views.export_anime_csv, name="export_anime_csv"),

    # --- Webtoon URL'leri ---
    path("webtoon/", views.webtoon_list_and_create, name="webtoon_list_view"),
    path("webtoon/<int:pk>/", views.webtoon_detail, name="webtoon_detail"),
    path("webtoon/<int:pk>/edit/", views.webtoon_edit, name="webtoon_edit"),
    path("webtoon/<int:pk>/delete/", views.webtoon_delete, name="webtoon_delete"),
    path("webtoon/export/csv/", views.export_webtoon_csv, name="export_webtoon_csv"),

    # --- Manga URL'leri ---
    path("manga/", views.manga_list_and_create, name="manga_list_view"),
    path("manga/<int:pk>/", views.manga_detail, name="manga_detail"),
    path("manga/<int:pk>/edit/", views.manga_edit, name="manga_edit"),
    path("manga/<int:pk>/delete/", views.manga_delete, name="manga_delete"),
    path("manga/export/csv/", views.export_manga_csv, name="export_manga_csv"),

    # --- Novel URL'leri ---
    path("novel/", views.novel_list_and_create, name="novel_list_view"),
    path("novel/<int:pk>/", views.novel_detail, name="novel_detail"),
    path("novel/<int:pk>/edit/", views.novel_edit, name="novel_edit"),
    path("novel/<int:pk>/delete/", views.novel_delete, name="novel_delete"),
    path("novel/export/csv/", views.export_novel_csv, name="export_novel_csv"),
]