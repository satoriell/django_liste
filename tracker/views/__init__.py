# tracker/views/__init__.py

# base_views.py dosyasından ilgili view'ları import et
from .base_views import dashboard_view, signup_view, favorites_view

# crud_views.py dosyasından ilgili view'ları import et
from .crud_views import (
    anime_list_and_create, anime_detail, anime_edit, anime_delete,
    webtoon_list_and_create, webtoon_detail, webtoon_edit, webtoon_delete,
    manga_list_and_create, manga_detail, manga_edit, manga_delete,
    novel_list_and_create, novel_detail, novel_edit, novel_delete,
)

# api_views.py dosyasından ilgili view'ları import et
from .api_views import (
    manga_api_search_view, anime_api_search_view, novel_api_search_view,
    md_add_item_view, jikan_add_anime_view, jikan_add_novel_view
)

# ajax_views.py dosyasından ilgili view'ları import et
from .ajax_views import toggle_favorite

# export_views.py dosyasından ilgili view'ları import et
from .export_views import (
    export_anime_csv, export_webtoon_csv, export_manga_csv, export_novel_csv
)

# Opsiyonel: Eğer yardımcı fonksiyonları başka view'larda doğrudan kullanmayacaksanız
# __init__.py'ye import etmenize gerek yok. helpers.py içinden çağrılabilirler.

# İsteğe bağlı: Tüm import edilenleri __all__ listesine eklemek iyi bir pratiktir.
__all__ = [
    'dashboard_view', 'signup_view', 'favorites_view',
    'anime_list_and_create', 'anime_detail', 'anime_edit', 'anime_delete',
    'webtoon_list_and_create', 'webtoon_detail', 'webtoon_edit', 'webtoon_delete',
    'manga_list_and_create', 'manga_detail', 'manga_edit', 'manga_delete',
    'novel_list_and_create', 'novel_detail', 'novel_edit', 'novel_delete',
    'manga_api_search_view', 'anime_api_search_view', 'novel_api_search_view',
    'md_add_item_view', 'jikan_add_anime_view', 'jikan_add_novel_view',
    'toggle_favorite',
    'export_anime_csv', 'export_webtoon_csv', 'export_manga_csv', 'export_novel_csv',
]