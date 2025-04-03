# tracker/admin.py
from django.contrib import admin

# '.' aynı klasördeki models modülünü (models.py dosyasını) işaret eder
from .models import Anime, Manga, Novel, Webtoon


# Modellerini admin sitesine kaydet
# Bu sayede admin panelinde görünür ve yönetilebilir olurlar
@admin.register(Anime)
class AnimeAdmin(admin.ModelAdmin):
    list_display = ("title", "status", "rating", "added_date") # Listede görünecek sütunlar
    list_filter = ("status", "rating") # Filtreleme seçenekleri
    search_fields = ("title", "studio") # Arama yapılacak alanlar


@admin.register(Webtoon)
class WebtoonAdmin(admin.ModelAdmin):
    list_display = ("title", "status", "rating", "author", "platform", "added_date")
    list_filter = ("status", "rating", "platform")
    search_fields = ("title", "author", "artist", "platform")


@admin.register(Manga)
class MangaAdmin(admin.ModelAdmin):
    list_display = (
        "title", "status", "rating", "author", "chapters_read", "volumes_read", "added_date"
    )
    list_filter = ("status", "rating")
    search_fields = ("title", "author", "artist")


@admin.register(Novel)
class NovelAdmin(admin.ModelAdmin):
    list_display = (
        "title", "status", "rating", "author", "chapters_read", "volumes_read", "added_date"
    )
    list_filter = ("status", "rating")
    search_fields = ("title", "author")


# Yukarıdaki @admin.register ve ModelAdmin sınıfları, admin panelindeki
# görünümü ve kullanılabilirliği artırır (listeleme, filtreleme, arama).
# Sadece admin.site.register(ModelAdi) kullanmak da yeterlidir ancak daha az özellik sunar.