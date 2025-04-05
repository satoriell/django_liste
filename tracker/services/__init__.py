# tracker/services/__init__.py

from .mangadex_service import search_manga, get_manga_details
from .jikan_service import search_anime, get_anime_details, search_novel, get_novel_details

# Opsiyonel: Bu paketten '*' ile import edildiğinde nelerin dahil edileceğini belirtir
__all__ = [
    'search_manga', 'get_manga_details',
    'search_anime', 'get_anime_details',
    'search_novel', 'get_novel_details',
]