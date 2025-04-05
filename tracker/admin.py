# tracker/admin.py
# İyileştirmeler: @admin.register, list_display, list_filter, search_fields,
# date_hierarchy, list_per_page, FavoriteAdmin eklendi.

from django.contrib import admin
# GenericForeignKey'i admin panelinde göstermek için (opsiyonel ama faydalı olabilir)
# from django.contrib.contenttypes.admin import GenericTabularInline

# Modelleri import et
from .models import Anime, Manga, Novel, Webtoon, Favorite

# Ortak Admin Ayarları (Opsiyonel - Tekrarlanan ayarlar için)
# class BaseMediaAdmin(admin.ModelAdmin):
#     list_filter = ("status", "rating", "user")
#     list_per_page = 25
#     date_hierarchy = 'added_date'
#     # ... diğer ortak ayarlar ...

@admin.register(Anime)
class AnimeAdmin(admin.ModelAdmin): # Veya BaseMediaAdmin'den miras alabilir
    list_display = ("title", "user", "status", "rating", "episodes_watched", "total_episodes", "mal_id", "added_date")
    list_filter = ("status", "rating", "user") # Kullanıcıya göre filtrele
    search_fields = ("title", "studio", "user__username", "mal_id") # Kullanıcı adı ve MAL ID ile ara
    list_per_page = 25 # Sayfada gösterilecek öğe sayısı
    date_hierarchy = 'added_date' # Tarihe göre gezinme
    # raw_id_fields = ('user',) # Çok fazla kullanıcı varsa seçimi kolaylaştırır

@admin.register(Webtoon)
class WebtoonAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "status", "rating", "author", "platform", "chapters_read", "mangadex_id", "added_date")
    list_filter = ("status", "rating", "platform", "user")
    search_fields = ("title", "author", "artist", "platform", "user__username", "mangadex_id")
    list_per_page = 25
    date_hierarchy = 'added_date'
    # raw_id_fields = ('user',)

@admin.register(Manga)
class MangaAdmin(admin.ModelAdmin):
    list_display = (
        "title", "user", "status", "rating", "author", "chapters_read",
        "volumes_read", "total_chapters", "total_volumes", "mangadex_id", "added_date"
    )
    list_filter = ("status", "rating", "user")
    search_fields = ("title", "author", "artist", "user__username", "mangadex_id")
    list_per_page = 25
    date_hierarchy = 'added_date'
    # raw_id_fields = ('user',)

@admin.register(Novel)
class NovelAdmin(admin.ModelAdmin):
    list_display = (
        "title", "user", "status", "rating", "author", "chapters_read",
        "volumes_read", "total_chapters", "total_volumes", "mal_id", "added_date"
    )
    list_filter = ("status", "rating", "user")
    search_fields = ("title", "author", "user__username", "mal_id")
    list_per_page = 25
    date_hierarchy = 'added_date'
    # raw_id_fields = ('user',)


# --- Favorite Modeli İçin Admin ---
@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ('user', 'content_object_display', 'content_type', 'object_id', 'created_at')
    list_filter = ('user', 'content_type', 'created_at')
    search_fields = ('user__username', 'object_id') # Kullanıcı adı veya obje ID'sine göre ara
    list_per_page = 30
    date_hierarchy = 'created_at'
    # GenericForeignKey alanları doğrudan list_display/filter/search'de kullanılamaz.
    # Ancak ilişkili objeyi özel bir metodla gösterebiliriz:
    @admin.display(description='Favorilenen Öğe', ordering='content_type') # Sıralama ekle (isteğe bağlı)
    def content_object_display(self, obj):
        # İlişkili nesne (Anime, Manga vb.) varsa onun __str__ metodunu kullanır.
        # Eğer nesne silinmişse (content_object=None), tip ve ID'yi gösterir.
        if obj.content_object:
            return str(obj.content_object)
        return f"{obj.content_type.model} (ID: {obj.object_id}) - [Silinmiş?]"

    # İlişkili objeleri (user, content_type) seçmek için raw_id_fields kullanışlı olabilir
    # özellikle çok fazla kullanıcı veya içerik türü varsa. Popup açarak seçimi sağlar.
    raw_id_fields = ('user',) # Sadece kullanıcı için raw_id kullanalım
    # raw_id_fields = ('user', 'content_type',)