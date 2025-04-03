# tracker/models.py
# Konum: /home/admin/App/django_liste/tracker/models.py

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone  # Tarih/zaman işlemleri için gerekli


# Ortak alanları burada tanımlayıp diğer modellerde tekrar yazmaktan kurtulabiliriz.
class MediaItem(models.Model):
    # Durum seçenekleri: Veritabanında İngilizce, Arayüzde Türkçe gösterim için
    STATUS_CHOICES = [
        ("Watching", "İzliyorum/Okuyorum"),
        ("Completed", "Tamamladım"),
        ("On Hold", "Beklemede"),
        ("Dropped", "Bıraktım"),
        ("Plan to Watch", "İzleyeceğim/Okuyacağım"),
    ]

    # Alanlar (Veritabanı Sütunları)
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
    # verbose_name eklenmişti, korunuyor
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
    )  # Otomatik eklenme zamanı

    # Meta sınıfı: Modelin kendisiyle ilgili ayarlar
    class Meta:
        abstract = True  # Bu model için tablo oluşturma, sadece miras alınsın.
        ordering = [
            "-added_date",
            "title",
        ]  # Varsayılan sıralama (yeni->eski, sonra başlık)

    # Admin panelinde ve model objesini yazdırınca görünecek temsil
    def __str__(self):
        return self.title

    # İlerleme yüzdesini hesaplayan bir method (detayda kullanılabilir)
    def get_progress_percent(self):
        """İlerleme yüzdesini hesaplar (bölüm veya chapter bazında)."""
        total = None
        current = None

        # Önce anime kontrolü
        if hasattr(self, "total_episodes") and self.total_episodes:
            total = self.total_episodes
            current = getattr(self, "episodes_watched", None)
        # Sonra chapter bazlı kontrol (Webtoon, Manga, Novel)
        elif hasattr(self, "total_chapters") and self.total_chapters:
            total = self.total_chapters
            current = getattr(self, "chapters_read", None)
        # Diğer tipler için de eklenebilir (örn. Ciltler)

        # Hesaplama (current None değilse ve total > 0 ise)
        if (
            total is not None
            and total > 0
            and current is not None
            and isinstance(current, int) # current'ın sayı olduğundan emin ol
            and isinstance(total, int)   # total'ın sayı olduğundan emin ol
        ):
            try:
                # Negatif değerleri ve total'den büyük değerleri kontrol et
                current = max(0, current) # En az 0
                # current = min(current, total) # Eğer izlenen > toplam olamazsa
                percentage = int((current / total) * 100)
                return min(percentage, 100) # %100'ü geçmemesini sağla
            except ZeroDivisionError:
                return None # Toplam 0 ise yüzde hesaplanamaz
            except (TypeError, ValueError):
                # Beklenmedik bir tip hatası olursa None dön
                return None
        # Eğer total veya current uygun değilse None dön
        return None


# Anime modeli, MediaItem'dan miras alıyor
class Anime(MediaItem):
    studio = models.CharField(max_length=100, blank=True, verbose_name="Stüdyo")
    episodes_watched = models.PositiveIntegerField(
        default=0, verbose_name="İzlenen Bölüm"
    )
    total_episodes = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="Toplam Bölüm"
    )


# Webtoon modeli, MediaItem'dan miras alıyor
class Webtoon(MediaItem):
    author = models.CharField(max_length=100, blank=True, verbose_name="Yazar")
    artist = models.CharField(max_length=100, blank=True, verbose_name="Çizer")
    chapters_read = models.PositiveIntegerField(
        default=0, verbose_name="Okunan Bölüm"
    )
    total_chapters = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="Toplam Bölüm"
    )
    platform = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Platform (Webtoon, Tapas vb.)",
    )


# Manga modeli, MediaItem'dan miras alıyor
class Manga(MediaItem):
    author = models.CharField(
        max_length=100, blank=True, verbose_name="Yazar (Mangaka)"
    )
    artist = models.CharField(max_length=100, blank=True, verbose_name="Çizer")
    chapters_read = models.PositiveIntegerField(
        default=0, verbose_name="Okunan Bölüm"
    )
    volumes_read = models.PositiveIntegerField(
        default=0, verbose_name="Okunan Cilt"
    )
    total_chapters = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="Toplam Bölüm"
    )
    total_volumes = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="Toplam Cilt"
    )


# Novel modeli, MediaItem'dan miras alıyor
class Novel(MediaItem):
    author = models.CharField(max_length=100, blank=True, verbose_name="Yazar")
    chapters_read = models.PositiveIntegerField(
        default=0, verbose_name="Okunan Bölüm"
    )
    volumes_read = models.PositiveIntegerField(
        default=0, verbose_name="Okunan Cilt"
    )
    total_chapters = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="Toplam Bölüm"
    )
    total_volumes = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="Toplam Cilt"
    )