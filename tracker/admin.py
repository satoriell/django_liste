# tracker/admin.py
from django.contrib import admin
# YENİ: contenttypes admin için (opsiyonel ama faydalı)
from django.contrib.contenttypes.admin import GenericTabularInline

# '.' aynı klasördeki models modülünü (models.py dosyasını) işaret eder
# YENİ: Favorite modelini import et
from .models import Anime, Manga, Novel, Webtoon, Favorite


# Modellerini admin sitesine kaydet
@admin.register(Anime)
class AnimeAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "status", "rating", "added_date") # Kullanıcı eklendi
    list_filter = ("status", "rating", "user") # Kullanıcı eklendi
    search_fields = ("title", "studio", "user__username") # Kullanıcı adına göre arama eklendi
    list_per_page = 20 # Sayfada gösterilecek öğe sayısı (opsiyonel)
    # Tarih alanları için filtreleme (opsiyonel)
    date_hierarchy = 'added_date'


@admin.register(Webtoon)
class WebtoonAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "status", "rating", "author", "platform", "added_date")
    list_filter = ("status", "rating", "platform", "user")
    search_fields = ("title", "author", "artist", "platform", "user__username")
    list_per_page = 20
    date_hierarchy = 'added_date'


@admin.register(Manga)
class MangaAdmin(admin.ModelAdmin):
    list_display = (
        "title", "user", "status", "rating", "author", "chapters_read", "volumes_read", "added_date"
    )
    list_filter = ("status", "rating", "user")
    search_fields = ("title", "author", "artist", "user__username")
    list_per_page = 20
    date_hierarchy = 'added_date'


@admin.register(Novel)
class NovelAdmin(admin.ModelAdmin):
    list_display = (
        "title", "user", "status", "rating", "author", "chapters_read", "volumes_read", "added_date"
    )
    list_filter = ("status", "rating", "user")
    search_fields = ("title", "author", "user__username")
    list_per_page = 20
    date_hierarchy = 'added_date'


# YENİ: Favorite modelini admin paneline kaydet
@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ('user', 'content_object_display', 'content_type', 'created_at')
    list_filter = ('user', 'content_type', 'created_at')
    search_fields = ('user__username',) # Sadece kullanıcı adına göre arama
    list_per_page = 25
    date_hierarchy = 'created_at'
    # GenericForeignKey alanları doğrudan list_display/filter/search'de kullanılamaz
    # Ancak özel bir metodla gösterebiliriz:
    @admin.display(description='Favorilenen Öğe')
    def content_object_display(self, obj):
        return obj.content_object # Modelin __str__ metodunu kullanır

    # İlişkili objeleri (user, content_type) seçmek için raw_id_fields kullanışlı olabilir
    # özellikle çok fazla kullanıcı veya içerik türü varsa
    # raw_id_fields = ('user', 'content_type',) # Kullanıcı seçimi için popup açar