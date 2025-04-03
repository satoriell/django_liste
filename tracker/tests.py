# tracker/tests.py

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Anime, Novel # Test edilecek modelleri import et


# Create your tests here.
class MediaModelTests(TestCase):
    """Model testleri için örnek bir sınıf."""

    def test_anime_creation(self):
        """Anime modelinin başarılı bir şekilde oluşturulup oluşturulmadığını test eder."""
        title = "Test Anime Başlığı"
        anime = Anime.objects.create(title=title, status="Watching")
        self.assertEqual(anime.title, title)
        self.assertEqual(anime.status, "Watching")
        self.assertTrue(isinstance(anime.added_date, timezone.datetime))
        # __str__ methodunu test et
        self.assertEqual(str(anime), title)
        print(f"Test Başarılı: Anime '{title}' oluşturuldu.")

    def test_novel_creation_with_rating(self):
        """Novel modelinin puanla birlikte oluşturulmasını test eder."""
        novel = Novel.objects.create(
            title="Test Novel", status="Completed", rating=8
        )
        self.assertEqual(novel.title, "Test Novel")
        self.assertEqual(novel.status, "Completed")
        self.assertEqual(novel.rating, 8)
        print("Test Başarılı: Novel 'Test Novel' (Puan: 8) oluşturuldu.")


class ViewTests(TestCase):
    """View testleri için örnek bir sınıf."""

    def test_dashboard_view_status_code(self):
        """Dashboard sayfasının başarılı bir şekilde açılıp açılmadığını (HTTP 200) test eder."""
        url = reverse("tracker:dashboard") # Namespace kullanarak URL al
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        print("Test Başarılı: Dashboard sayfası (HTTP 200) yüklendi.")

    def test_anime_list_view_status_code(self):
        """Anime listesi sayfasının başarılı bir şekilde açılıp açılmadığını test eder."""
        url = reverse("tracker:anime_list_view")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # Sayfada belirli bir başlığın olup olmadığını kontrol et (opsiyonel)
        self.assertContains(response, "Anime Listem")
        print("Test Başarılı: Anime Listesi sayfası (HTTP 200) yüklendi.")

    def test_add_anime_via_post(self):
        """Form aracılığıyla yeni bir anime eklemeyi test eder."""
        url = reverse("tracker:anime_list_view")
        data = {
            "title": "Yeni Eklenen Anime",
            "status": "Plan to Watch",
            "episodes_watched": 0,
            # Diğer gerekli form alanları buraya eklenebilir
        }
        response = self.client.post(url, data)

        # Başarılı POST sonrası yönlendirme olup olmadığını kontrol et (HTTP 302)
        self.assertEqual(response.status_code, 302)
        # Yönlendirilen URL'in doğru olup olmadığını kontrol et
        self.assertRedirects(response, url)

        # Veritabanında animenin oluşturulup oluşturulmadığını kontrol et
        self.assertTrue(Anime.objects.filter(title="Yeni Eklenen Anime").exists())
        print("Test Başarılı: Yeni anime POST isteği ile eklendi ve yönlendirme yapıldı.")


# TODO: Form testleri ekle (geçerli ve geçersiz veri ile)
# TODO: Detay, düzenleme, silme view'ları için testler ekle
# TODO: Favori ekleme/çıkarma işlevselliği için testler ekle
# TODO: CSV export view'ları için testler ekle