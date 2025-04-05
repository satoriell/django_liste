# tracker/urls.py
# Konum: /home/admin/App/django_liste/tracker/urls.py
# YENİ: Jikan API (Novel) için URL'ler eklendi.

from django.urls import path
import uuid # MangaDex ID için
from . import views

app_name = "tracker"

urlpatterns = [
    # --- Dashboard ---
    path("", views.dashboard_view, name="dashboard"),

    # --- Kayıt (Signup) ---
    # Ana projenin urls.py'sinde 'accounts/' altında handle ediliyor.

    # --- Favori URL'leri ---
    path("favorite/toggle/", views.toggle_favorite, name="toggle_favorite"),
    path("favorites/", views.favorites_view, name="favorites_view"),

    # --- MangaDex API (Manga/Webtoon) ---
    path("manga/search-api/", views.manga_api_search_view, name="manga_api_search"),
    path("webtoon/search-api/", views.manga_api_search_view, name="webtoon_api_search"),
    path("add-from-mangadex/<uuid:mangadex_id>/", views.md_add_item_view, name="md_add_item"),

    # --- Anime URL'leri ---
    path("anime/", views.anime_list_and_create, name="anime_list_view"),
    path("anime/<int:pk>/", views.anime_detail, name="anime_detail"),
    path("anime/<int:pk>/edit/", views.anime_edit, name="anime_edit"),
    path("anime/<int:pk>/delete/", views.anime_delete, name="anime_delete"),
    path("anime/export/csv/", views.export_anime_csv, name="export_anime_csv"),
    # --- Jikan API (Anime) URL'leri ---
    path("anime/search-api/", views.anime_api_search_view, name="anime_api_search"),
    path("add-from-jikan/<int:mal_id>/", views.jikan_add_anime_view, name="jikan_add_anime"),

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
    # --- YENİ: Jikan API (Novel) URL'leri ---
    path("novel/search-api/", views.novel_api_search_view, name="novel_api_search"),
    path("add-novel-from-jikan/<int:mal_id>/", views.jikan_add_novel_view, name="jikan_add_novel"),
    # ---------------------------------------

    # Opsiyonel: Etikete göre listeleme (varsa)
    # path("tags/<slug:tag_slug>/", views.items_by_tag_view, name="items_by_tag"),
]