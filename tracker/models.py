# tracker/models.py
# Konum: /home/admin/App/django_liste/tracker/models.py
# YENİ: Novel modeline mal_id eklendi.

import uuid
from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator
from django.utils import timezone
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from taggit.managers import TaggableManager

# Ortak alanları burada tanımlayıp diğer modellerde tekrar yazmaktan kurtulabiliriz.
class MediaItem(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='%(class)s_items',
        verbose_name="Kullanıcı"
    )
    STATUS_CHOICES = [
        ("Watching", "İzliyorum/Okuyorum"),
        ("Completed", "Tamamladım"),
        ("On Hold", "Beklemede"),
        ("Dropped", "Bıraktım"),
        ("Plan to Watch", "İzleyeceğim/Okuyacağım"),
    ]
    title = models.CharField(max_length=255, verbose_name="Başlık")
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="Plan to Watch",
        verbose_name="Durum",
    )
    rating = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name="Puan (0-10)",
        validators=[
            MinValueValidator(0, message="Puan 0'dan küçük olamaz."),
            MaxValueValidator(10, message="Puan 10'dan büyük olamaz."),
        ],
    )
    start_date = models.DateField(
        null=True, blank=True, verbose_name="Başlama Tarihi"
    )
    end_date = models.DateField(
        null=True, blank=True, verbose_name="Bitirme Tarihi"
    )
    notes = models.TextField(blank=True, verbose_name="Notlar")
    cover_image_url = models.URLField(
        blank=True, null=True, verbose_name="Kapak Resmi URL"
    )
    added_date = models.DateTimeField(
        default=timezone.now, verbose_name="Eklenme Tarihi"
    )
    mangadex_id = models.UUIDField(
        null=True,
        blank=True,
        unique=True,
        db_index=True,
        verbose_name="MangaDex ID"
    )
    tags = TaggableManager(
        blank=True,
        verbose_name="Etiketler",
        help_text="Etiketleri virgülle ayırarak giriniz."
    )

    class Meta:
        abstract = True
        ordering = ['user', "-added_date", "title"]

    def __str__(self):
        return self.title

    def get_progress_percent(self):
        total = None
        current = None
        if hasattr(self, "total_episodes") and self.total_episodes is not None and self.total_episodes > 0:
            total = self.total_episodes
            current = getattr(self, "episodes_watched", 0)
        elif hasattr(self, "total_chapters") and self.total_chapters is not None and self.total_chapters > 0:
            total = self.total_chapters
            current = getattr(self, "chapters_read", 0)
        if total is None:
             if hasattr(self, "total_volumes") and self.total_volumes is not None and self.total_volumes > 0:
                 total = self.total_volumes
                 current = getattr(self, "volumes_read", 0)
        if (total is not None and total > 0 and current is not None and isinstance(current, (int, float)) and isinstance(total, (int, float))):
            try:
                current = max(0, current)
                percentage = (current / total) * 100
                return min(percentage, 100)
            except ZeroDivisionError: return None
            except (TypeError, ValueError): return None
        return None

# --- Medya Modelleri ---
class Anime(MediaItem):
    studio = models.CharField(max_length=100, blank=True, verbose_name="Stüdyo")
    episodes_watched = models.PositiveIntegerField(default=0, verbose_name="İzlenen Bölüm")
    total_episodes = models.PositiveIntegerField(null=True, blank=True, verbose_name="Toplam Bölüm")
    mal_id = models.PositiveIntegerField(
        null=True, blank=True, unique=True, db_index=True, verbose_name="MyAnimeList ID"
    )

class Webtoon(MediaItem):
    author = models.CharField(max_length=100, blank=True, verbose_name="Yazar")
    artist = models.CharField(max_length=100, blank=True, verbose_name="Çizer")
    chapters_read = models.PositiveIntegerField(default=0, verbose_name="Okunan Bölüm")
    total_chapters = models.PositiveIntegerField(null=True, blank=True, verbose_name="Toplam Bölüm")
    platform = models.CharField(max_length=100, blank=True, verbose_name="Platform (Webtoon, Tapas vb.)")

class Manga(MediaItem):
    author = models.CharField(max_length=100, blank=True, verbose_name="Yazar (Mangaka)")
    artist = models.CharField(max_length=100, blank=True, verbose_name="Çizer")
    chapters_read = models.PositiveIntegerField(default=0, verbose_name="Okunan Bölüm")
    volumes_read = models.PositiveIntegerField(default=0, verbose_name="Okunan Cilt")
    total_chapters = models.PositiveIntegerField(null=True, blank=True, verbose_name="Toplam Bölüm")
    total_volumes = models.PositiveIntegerField(null=True, blank=True, verbose_name="Toplam Cilt")

class Novel(MediaItem):
    author = models.CharField(max_length=100, blank=True, verbose_name="Yazar")
    chapters_read = models.PositiveIntegerField(default=0, verbose_name="Okunan Bölüm")
    volumes_read = models.PositiveIntegerField(default=0, verbose_name="Okunan Cilt")
    total_chapters = models.PositiveIntegerField(null=True, blank=True, verbose_name="Toplam Bölüm")
    total_volumes = models.PositiveIntegerField(null=True, blank=True, verbose_name="Toplam Cilt")

    # YENİ: Jikan API (MyAnimeList) ID alanı (Novel için de)
    # Jikan novelleri de manga endpoint'i altında listeler ve MAL ID'leri vardır.
    mal_id = models.PositiveIntegerField(
        null=True,       # API'dan eklenmeyenler için boş olabilir
        blank=True,      # Formlarda boş bırakılabilir
        unique=True,     # Her MAL ID'si benzersiz olmalı (ama null olabilir)
        db_index=True,   # Bu alana göre arama yapılacağı için index iyi olur
        verbose_name="MyAnimeList ID"
    )

# --- Favori Modeli ---
class Favorite(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='favorites',
        verbose_name="Kullanıcı"
    )
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        verbose_name="İçerik Türü"
    )
    object_id = models.PositiveIntegerField(
        verbose_name="Obje ID"
    )
    content_object = GenericForeignKey('content_type', 'object_id')
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Eklenme Zamanı"
    )
    class Meta:
        constraints = [ models.UniqueConstraint(fields=['user', 'content_type', 'object_id'], name='unique_user_content_favorite') ]
        ordering = ['-created_at']
        verbose_name = "Favori"
        verbose_name_plural = "Favoriler"
    def __str__(self):
        item_title = str(self.content_object) if self.content_object else f"{self.content_type.model}-{self.object_id}"
        return f"{self.user.username} - {item_title}"