# tracker/tests.py
# Kapsamlı Güncelleme: Refactoring, Yeni Özellik Testleri (Favori, Tag, API Mocking), Model Testleri Güncellendi.

import csv
import io # CSV içeriğini kontrol etmek için
import json # AJAX testleri için
import uuid # MangaDex ID için
import datetime # datetime modülünü import et
from unittest.mock import patch # API çağrılarını mocklamak için

from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm # Signup testi için
from django.contrib.contenttypes.models import ContentType
from django.contrib.messages import get_messages # Mesajları kontrol etmek için
from django.db import IntegrityError # Unique constraint testi için
from taggit.models import Tag # Etiket testleri için

# Modelleri ve Formları import et
from .models import Anime, Novel, Webtoon, Manga, Favorite
from .forms import AnimeForm, WebtoonForm, MangaForm, NovelForm


# --- Test Setup Mixin ---
class SetupMixin:
    """Testler için ortak kurulum (kullanıcı, modeller, etiketler vb.)"""
    @classmethod
    def setUpTestData(cls):
        # Bu metod sınıf başına bir kez çalışır, veritabanı durumu korunur.
        # Daha verimli olabilir, ancak instance'lar üzerinde değişiklik yapılacaksa setUp kullanılır.
        # Şimdilik setUp kullanalım.
        pass

    def setUp(self):
        # Bu metod her test fonksiyonu (test_...) başında çalışır.
        self.client = Client()
        self.test_user1 = User.objects.create_user(username='testuser1', password='password123')
        self.other_user = User.objects.create_user(username='otheruser', password='password123')
        self.anonymous_client = Client() # Giriş yapmamış kullanıcı

        # --- Örnek Etiketler ---
        self.tag_action = Tag.objects.create(name="Aksiyon")
        self.tag_comedy = Tag.objects.create(name="Komedi")
        self.tag_isekai = Tag.objects.create(name="Isekai")

        # --- Örnek Veriler (test_user1'a ait) ---
        self.anime1 = Anime.objects.create(
            user=self.test_user1, title="Test Anime Alpha", status="Watching", rating=8, total_episodes=12, episodes_watched=5, added_date=timezone.now() - datetime.timedelta(days=2), studio="Studio A"
        )
        self.anime1.tags.add(self.tag_action, self.tag_comedy)

        self.anime2 = Anime.objects.create(
            user=self.test_user1, title="Test Anime Beta", status="Completed", rating=9, total_episodes=24, episodes_watched=24, added_date=timezone.now() - datetime.timedelta(days=1), mal_id=12345
        )
        self.anime2.tags.add("Fantastik", "Macera") # String olarak da eklenebilir

        self.anime3_plan = Anime.objects.create(
            user=self.test_user1, title="Anime Gamma Plan", status="Plan to Watch", rating=None, added_date=timezone.now()
        )
        # anime3 etiket eklemedik

        self.webtoon1 = Webtoon.objects.create(
            user=self.test_user1, title="Test Webtoon 1", status="Watching", total_chapters=100, chapters_read=50, author="WT Author", platform="Webtoon", mangadex_id=uuid.uuid4()
        )
        self.webtoon1.tags.add(self.tag_action)

        self.manga1 = Manga.objects.create(
            user=self.test_user1, title="Test Manga 1", status="On Hold", rating=7, total_volumes=10, volumes_read=3, total_chapters=50, chapters_read=15, author="M Author", artist="M Artist"
        )
        self.manga1.tags.add(self.tag_comedy)

        self.novel1 = Novel.objects.create(
            user=self.test_user1, title="Test Novel 1", status="Plan to Watch", rating=None, total_chapters=200, chapters_read=0, total_volumes=5, volumes_read=0, author="N Author", mal_id=54321
        )
        self.novel1.tags.add(self.tag_isekai)

        # Örnek Cilt Bilgisi Olan Manga/Novel (Progress Testi İçin)
        self.manga_vols_only = Manga.objects.create(
             user=self.test_user1, title="Manga Vols Only", status="Watching", total_volumes=10, volumes_read=5
        )
        self.novel_vols_only = Novel.objects.create(
             user=self.test_user1, title="Novel Vols Only", status="Watching", total_volumes=8, volumes_read=2
        )

        # --- Örnek Veriler (other_user'a ait) ---
        self.other_user_anime = Anime.objects.create(
            user=self.other_user, title="Other User Anime", status="Watching"
        )
        self.other_user_webtoon = Webtoon.objects.create(
            user=self.other_user, title="Other User Webtoon", status="Completed"
        )
        self.other_user_anime.tags.add(self.tag_action)


        # --- ContentType'lar (Favori testleri için) ---
        self.anime_content_type = ContentType.objects.get_for_model(Anime)
        self.webtoon_content_type = ContentType.objects.get_for_model(Webtoon)
        self.manga_content_type = ContentType.objects.get_for_model(Manga)
        self.novel_content_type = ContentType.objects.get_for_model(Novel)

        # --- Mock API Yanıtları (İhtiyaç halinde kullanılacak) ---
        self.mock_mangadex_search_result = [
            {'id': 'c77c9b3b-e14b-4a7c-a870-797c6d857f81', 'title': 'Mock MangaDex Manga', 'description_snippet': 'Açıklama...', 'year': 2020, 'status': 'ongoing', 'cover_url': 'http://example.com/cover.jpg', 'authors': "Yazar A", 'artists': "Çizer B"}
        ]
        self.mock_mangadex_details_manga = {
            'mangadex_id': 'a96676e5-8ae2-425e-b549-7f15dd34a6d8', 'title': 'Mock Manga Detail', 'cover_image_url': 'http://example.com/detail.jpg', 'author': 'Yazar Detay', 'artist': 'Çizer Detay', 'notes': 'Detaylı açıklama.', 'total_chapters': None, 'chapters_read': 0, 'total_volumes': None, 'volumes_read': 0, 'status': 'Plan to Watch', 'rating': None, 'start_date': None, 'end_date': None, 'detected_type': 'MANGA', 'tags_list': ['aksiyon', 'macera'], 'tags': 'aksiyon, macera'
        }
        self.mock_mangadex_details_webtoon = {
             'mangadex_id': '3f65e893-63ff-4a50-9450-c63860917b33', 'title': 'Mock Webtoon Detail', 'cover_image_url': 'http://example.com/webtoon.jpg', 'author': 'Webtoon Yazar', 'artist': 'Webtoon Çizer', 'notes': 'Webtoon açıklaması.', 'total_chapters': 150, 'chapters_read': 0, 'total_volumes': None, 'volumes_read': 0, 'platform':'', 'status': 'Plan to Watch', 'rating': None, 'start_date': None, 'end_date': None, 'detected_type': 'WEBTOON', 'tags_list': ['webtoon', 'fantastik'], 'tags': 'webtoon, fantastik'
         }
        self.mock_jikan_search_result = [
            {'mal_id': 99901, 'title': 'Mock Jikan Anime', 'image_url': 'http://example.com/jikan.jpg', 'type': 'TV', 'episodes': 12, 'score': 8.5, 'status': 'Finished Airing', 'synopsis_snippet': 'Jikan özet...'}
        ]
        self.mock_jikan_details_anime = {
            'mal_id': 99901, 'title': 'Mock Jikan Anime Detail', 'cover_image_url': 'http://example.com/jikan_detail.jpg', 'notes': 'Detaylı Jikan Açıklaması.', 'status': 'Completed', 'rating': 9, 'total_episodes': 12, 'studio': 'Mock Studio', 'episodes_watched': 0, 'start_date': None, 'end_date': None, 'tags': ''
        }
        self.mock_jikan_details_novel = {
             'mal_id': 88801, 'title': 'Mock Jikan Novel Detail', 'cover_image_url': 'http://example.com/jikan_novel.jpg', 'notes': 'Novel Jikan Açıklaması.', 'status': 'Watching', 'rating': 8, 'total_chapters': 100, 'total_volumes': 10, 'author': 'Novel Yazar', 'chapters_read': 0, 'volumes_read': 0, 'start_date': None, 'end_date': None, 'tags': ''
         }


# =========================================
# --- Model Testleri ---
# =========================================
class MediaModelTests(SetupMixin, TestCase):
    """Model testleri (get_progress_percent güncellendi)."""

    def test_media_creation_and_str(self):
        self.assertEqual(str(self.anime1), "Test Anime Alpha")
        self.assertEqual(str(self.webtoon1), "Test Webtoon 1")
        self.assertEqual(str(self.manga1), "Test Manga 1")
        self.assertEqual(str(self.novel1), "Test Novel 1")
        print("Test Başarılı: Medya modelleri __str__.")

    def test_anime_progress(self):
        self.assertAlmostEqual(self.anime1.get_progress_percent(), (5/12)*100)
        self.assertEqual(self.anime2.get_progress_percent(), 100)
        anime_no_total = Anime.objects.create(user=self.test_user1, title="No Total Eps", episodes_watched=5)
        self.assertIsNone(anime_no_total.get_progress_percent())
        anime_zero_total = Anime.objects.create(user=self.test_user1, title="Zero Total Eps", total_episodes=0, episodes_watched=0)
        self.assertIsNone(anime_zero_total.get_progress_percent())
        print("Test Başarılı: Anime progress %.")

    def test_webtoon_progress(self):
        self.assertAlmostEqual(self.webtoon1.get_progress_percent(), (50/100)*100)
        webtoon_no_chap = Webtoon.objects.create(user=self.test_user1, title="WT No Chap")
        self.assertIsNone(webtoon_no_chap.get_progress_percent())
        print("Test Başarılı: Webtoon progress %.")

    def test_manga_progress(self):
        """Manga ilerleme yüzdesini test eder (chapter > volume fallback)."""
        # Sadece chapter var
        manga_chaps_only = Manga.objects.create(user=self.test_user1, title="Manga Chaps", total_chapters=60, chapters_read=30)
        self.assertAlmostEqual(manga_chaps_only.get_progress_percent(), 50.0)
        # Hem chapter hem volume var (chapter öncelikli)
        self.assertAlmostEqual(self.manga1.get_progress_percent(), (15/50)*100)
        # Sadece volume var
        self.assertAlmostEqual(self.manga_vols_only.get_progress_percent(), (5/10)*100)
        # Chapter var ama total=0, volume'a düşmeli
        manga_zero_chap_total = Manga.objects.create(user=self.test_user1, title="Manga Zero Chap", total_chapters=0, chapters_read=0, total_volumes=20, volumes_read=5)
        self.assertAlmostEqual(manga_zero_chap_total.get_progress_percent(), (5/20)*100)
         # Chapter var ama total=None, volume'a düşmeli
        manga_none_chap_total = Manga.objects.create(user=self.test_user1, title="Manga None Chap", total_chapters=None, chapters_read=0, total_volumes=20, volumes_read=5)
        self.assertAlmostEqual(manga_none_chap_total.get_progress_percent(), (5/20)*100)
        # Hiçbir bilgi yok
        manga_no_info = Manga.objects.create(user=self.test_user1, title="Manga No Info")
        self.assertIsNone(manga_no_info.get_progress_percent())
        print("Test Başarılı: Manga progress % (volume fallback dahil).")

    def test_novel_progress(self):
        """Novel ilerleme yüzdesini test eder (chapter > volume fallback)."""
        # Sadece chapter var
        novel_chaps_only = Novel.objects.create(user=self.test_user1, title="Novel Chaps", total_chapters=150, chapters_read=75)
        self.assertAlmostEqual(novel_chaps_only.get_progress_percent(), 50.0)
        # Hem chapter hem volume var (chapter öncelikli)
        self.assertAlmostEqual(self.novel1.get_progress_percent(), (0/200)*100)
        # Sadece volume var
        self.assertAlmostEqual(self.novel_vols_only.get_progress_percent(), (2/8)*100)
        # Chapter var ama total=0, volume'a düşmeli
        novel_zero_chap_total = Novel.objects.create(user=self.test_user1, title="Novel Zero Chap", total_chapters=0, chapters_read=0, total_volumes=12, volumes_read=3)
        self.assertAlmostEqual(novel_zero_chap_total.get_progress_percent(), (3/12)*100)
         # Chapter var ama total=None, volume'a düşmeli
        novel_none_chap_total = Novel.objects.create(user=self.test_user1, title="Novel None Chap", total_chapters=None, chapters_read=0, total_volumes=12, volumes_read=3)
        self.assertAlmostEqual(novel_none_chap_total.get_progress_percent(), (3/12)*100)
        # Hiçbir bilgi yok
        novel_no_info = Novel.objects.create(user=self.test_user1, title="Novel No Info")
        self.assertIsNone(novel_no_info.get_progress_percent())
        print("Test Başarılı: Novel progress % (volume fallback dahil).")

    def test_favorite_creation_and_str(self):
        favorite = Favorite.objects.create(
            user=self.test_user1, content_type=self.anime_content_type, object_id=self.anime1.pk
        )
        self.assertEqual(favorite.user, self.test_user1)
        self.assertEqual(favorite.content_object, self.anime1)
        self.assertEqual(str(favorite), f"{self.test_user1.username} - {self.anime1.title}")
        # Unique constraint testi
        with self.assertRaises(IntegrityError):
             Favorite.objects.create(user=self.test_user1, content_type=self.anime_content_type, object_id=self.anime1.pk)
        print("Test Başarılı: Favorite modeli.")


# =========================================
# --- Form Testleri ---
# =========================================
class MediaFormTests(SetupMixin, TestCase):
    """Form testleri (tags alanı dahil)."""

    def test_anime_form_valid_with_tags(self):
        form_data = {
            'title': 'Valid Anime Form', 'status': 'Watching', 'rating': 7,
            'episodes_watched': 10, 'total_episodes': 20, 'studio': 'Test Studio',
            'start_date': '2025-01-15', 'end_date': '', 'tags': 'aksiyon, yeni etiket' # tags eklendi
        }
        form = AnimeForm(data=form_data)
        self.assertTrue(form.is_valid(), f"AnimeForm hataları: {form.errors.as_json()}")
        # Formu kaydetmeyi test et (etiketlerin kaydedildiğini görmek için)
        instance = form.save(commit=False)
        instance.user = self.test_user1 # Kullanıcıyı ata
        instance.save()
        form.save_m2m() # Etiketleri kaydet
        # Yeni etiketin oluştuğunu ve instance'a eklendiğini kontrol et
        self.assertTrue(Tag.objects.filter(name='yeni etiket').exists())
        self.assertIn('aksiyon', [tag.name for tag in instance.tags.all()])
        self.assertIn('yeni etiket', [tag.name for tag in instance.tags.all()])
        print("Test Başarılı: AnimeForm geçerli veri (etiketler dahil).")

    # ... (Diğer form geçerlilik testleri benzer şekilde tags içerebilir) ...

    def test_media_base_form_invalid_rating(self):
        # Geçersiz puan (-1)
        form_data = {'title': 'Invalid Rating', 'status': 'Dropped', 'rating': -1}
        form = AnimeForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('rating', form.errors)
        self.assertIn("0'dan küçük olamaz", form.errors['rating'][0])
        # Geçersiz puan (11)
        form_data = {'title': 'Invalid Rating', 'status': 'Dropped', 'rating': 11}
        form = AnimeForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('rating', form.errors)
        self.assertIn("10'dan büyük olamaz", form.errors['rating'][0])
        print("Test Başarılı: MediaItemBaseForm geçersiz puan hatası.")

    # ... (Diğer form geçersizlik testleri aynı kalabilir) ...

# =========================================
# --- View Testleri ---
# =========================================
class TrackerViewTests(SetupMixin, TestCase):
    """Genel tracker view testleri (refactored helpers, context checks, AJAX, Mocking)."""

    # --- Test Yardımcı Metodları (Güncellendi) ---
    def _assert_common_list_context(self, response, model_class, form_class):
        """Liste view'larında ortak context değişkenlerini kontrol eder."""
        self.assertIn('page_obj', response.context)
        self.assertIn('paginator', response.context)
        self.assertIn('form', response.context)
        self.assertIsInstance(response.context['form'], form_class)
        self.assertIn('status_choices', response.context)
        self.assertIn('current_status_filter', response.context)
        self.assertIn('search_query', response.context)
        self.assertIn('current_sort', response.context)
        self.assertIn('params_encoded', response.context)
        self.assertIn('model_name_plural', response.context)
        self.assertIn('favorited_pks', response.context)
        self.assertIsInstance(response.context['favorited_pks'], set)
        self.assertIn('item_type_str', response.context)
        self.assertIn('list_url_name', response.context)
        self.assertIn('export_url_name', response.context)
        self.assertIn('all_tags', response.context) # Etiketler eklendi
        self.assertIn('current_tag_filter', response.context) # Etiket filtresi eklendi
        self.assertIn('api_search_url', response.context) # API URL'i eklendi

    def _test_list_view_get(self, url_name, template_name, model_instance, other_user_model_instance, form_class):
        """Liste görünümünün GET isteğini test eder (giriş yapmış kullanıcı)."""
        self.client.login(username='testuser1', password='password123')
        url = reverse(f"tracker:{url_name}")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, f"tracker/{template_name}")
        self.assertContains(response, model_instance.title) # Kendi öğesi görünmeli
        if other_user_model_instance:
             self.assertNotContains(response, other_user_model_instance.title) # Başkasının öğesi görünmemeli
        # Ortak context değişkenlerini kontrol et
        self._assert_common_list_context(response, model_instance.__class__, form_class)
        # Favori PK'larının doğruluğunu basitçe kontrol et (örn: kendi öğesi favori değilse)
        self.assertNotIn(model_instance.pk, response.context['favorited_pks'])
        print(f"Test Başarılı: {url_name} GET (Girişli). Context & İçerik OK.")

    def _test_list_view_get_filtered_sorted(self, url_name, template_name, params, expected_item, unexpected_item=None):
        """Liste görünümünün GET isteğini filtreleme/sıralama ile test eder."""
        self.client.login(username='testuser1', password='password123')
        url = reverse(f"tracker:{url_name}")
        response = self.client.get(url, params)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, f"tracker/{template_name}")
        self.assertContains(response, expected_item.title) # Beklenen öğe görünmeli
        if unexpected_item:
            self.assertNotContains(response, unexpected_item.title) # Beklenmeyen öğe görünmemeli
        # Context'teki filtre/sıralama değerlerini kontrol et
        if 'status' in params: self.assertEqual(response.context['current_status_filter'], params['status'])
        if 'q' in params: self.assertEqual(response.context['search_query'], params['q'])
        if 'sort' in params: self.assertEqual(response.context['current_sort'], params['sort'])
        if 'tag' in params: self.assertEqual(response.context['current_tag_filter'], params['tag'])
        print(f"Test Başarılı: {url_name} GET (Filtre/Sıralama: {params}). İçerik OK.")

    def _test_create_view_post_valid(self, url_name, model_class, form_data, expected_tags=None):
        """Öğe oluşturma (Create) POST isteğini geçerli veriyle test eder (etiketler dahil)."""
        self.client.login(username='testuser1', password='password123')
        url = reverse(f"tracker:{url_name}")
        initial_count = model_class.objects.filter(user=self.test_user1).count()
        if 'status' not in form_data: form_data['status'] = 'Plan to Watch'
        if 'tags' not in form_data: form_data['tags'] = '' # Etiket alanı yoksa boş string

        response = self.client.post(url, form_data) # follow=False

        # Yönlendirme kontrolü (Liste view'ına)
        self.assertEqual(response.status_code, 302, f"{url_name} POST sonrası 302 bekleniyordu, {response.status_code} alındı.")
        list_url = reverse(f"tracker:{url_name}")
        self.assertEqual(response.url, list_url, f"{url_name} POST sonrası yanlış yönlendirme: {response.url} (beklenen: {list_url})")

        # Veritabanı kontrolü
        self.assertEqual(model_class.objects.filter(user=self.test_user1).count(), initial_count + 1)
        created_instance = model_class.objects.get(user=self.test_user1, title=form_data['title'])
        self.assertIsNotNone(created_instance)

        # Etiket kontrolü
        if expected_tags:
            instance_tags = set(tag.name for tag in created_instance.tags.all())
            self.assertSetEqual(instance_tags, set(expected_tags))

        # Mesaj kontrolü (yönlendirme sonrası)
        response_followed = self.client.get(response.url)
        self.assertEqual(response_followed.status_code, 200)
        messages = list(get_messages(response_followed.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertTrue(f'"{form_data["title"]}" başarıyla eklendi.' in str(messages[0]))

        print(f"Test Başarılı: {url_name} Create POST (Geçerli). Veritabanı & Mesaj OK. Etiketler: {expected_tags or 'Yok'}")

    def _test_edit_view_post_valid(self, url_name, detail_url_name, model_instance, update_data):
        """Düzenleme görünümünün POST isteğini geçerli veriyle test eder."""
        self.client.login(username='testuser1', password='password123')
        url = reverse(f"tracker:{url_name}", kwargs={'pk': model_instance.pk})
        # Mevcut instance verilerini kopyala ve güncelle
        form_data = model_instance.__dict__.copy()
        form_data.update(update_data)
        # Gerekli olmayan/değişmemesi gereken alanları çıkar/formatla (setUp'takine benzer)
        form_data.pop('_state', None); form_data.pop('id', None); form_data.pop('user_id', None); form_data.pop('added_date', None);
        fields_to_format = ['start_date', 'end_date', 'rating', 'cover_image_url', 'notes', 'studio','episodes_watched', 'total_episodes', 'author', 'artist', 'chapters_read','total_chapters', 'platform', 'volumes_read', 'total_volumes', 'tags']
        for field in fields_to_format:
            if field in form_data:
                value = form_data[field]
                if isinstance(value, datetime.date) and not isinstance(value, datetime.datetime): form_data[field] = value.strftime('%Y-%m-%d')
                elif isinstance(value, datetime.datetime): form_data[field] = value.strftime('%Y-%m-%d %H:%M:%S')
                elif value is None: form_data[field] = ''
                elif isinstance(value, uuid.UUID): form_data[field] = str(value)
                # Taggit alanı için, tags ilişkisinden string oluştur
                elif field == 'tags':
                     form_data[field] = ", ".join(t.name for t in model_instance.tags.all())

        # Beklenen yönlendirme URL'i (Detay sayfası)
        detail_url = reverse(f"tracker:{detail_url_name}", kwargs={'pk': model_instance.pk})

        # POST isteği (yönlendirmeyi takip etme)
        response = self.client.post(url, form_data, follow=True)

        # Yönlendirme kontrolü
        self.assertRedirects(response, detail_url, status_code=302, target_status_code=200, msg_prefix=f"{url_name} Edit POST yönlendirme hatası: ")

        # Veritabanı kontrolü
        model_instance.refresh_from_db()
        for key, value in update_data.items():
            if key == 'tags': # Etiketleri ayrı kontrol et
                 instance_tags = set(t.name for t in model_instance.tags.all())
                 expected_tags = set(t.strip() for t in value.split(',') if t.strip())
                 self.assertSetEqual(instance_tags, expected_tags, f"Etiketler güncellenmedi/yanlış güncellendi.")
            else:
                 self.assertEqual(str(getattr(model_instance, key)), str(value), f"Alan '{key}' güncellenmedi.")

        # Mesaj kontrolü
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertTrue("başarıyla güncellendi" in str(messages[0]))

        print(f"Test Başarılı: {url_name} Edit POST (Geçerli). Veritabanı & Mesaj OK.")


    # ... (Diğer helper methodlar: _test_list_view_get_unauthenticated, _test_create_view_post_invalid, _test_detail_view_get, _test_edit_view_get, _test_edit_view_get_other_user, _test_delete_view_get, _test_delete_view_get_other_user, _test_delete_view_post, _test_export_csv_view aynı kalabilir veya küçük ayarlamalar yapılabilir) ...


    # --- Anime View Testleri (Etiket Filtresi Eklendi) ---
    def test_anime_list_views(self):
        self._test_list_view_get('anime_list_view', 'anime_list.html', self.anime1, self.other_user_anime, AnimeForm)
        self._test_list_view_get_unauthenticated('anime_list_view')
        valid_data = {'title': 'Created Anime Test', 'episodes_watched': 0, 'tags': 'Yeni, Test'}
        invalid_data = {'title': '', 'status': 'Watching'}
        self._test_create_view_post_valid('anime_list_view', Anime, valid_data, expected_tags=['Yeni', 'Test'])
        # self._test_create_view_post_invalid(...) # Bu test aynı kalabilir

    def test_anime_list_view_filtered_sorted_tags(self):
        # Sadece 'Aksiyon' etiketli animeleri getir (anime1)
        params_tag_action = {'tag': self.tag_action.slug}
        self._test_list_view_get_filtered_sorted('anime_list_view', 'anime_list.html', params_tag_action, self.anime1, self.anime2)
        # 'Komedi' etiketli ve 'Watching' durumunda olanları getir (anime1)
        params_tag_status = {'tag': self.tag_comedy.slug, 'status': 'Watching'}
        self._test_list_view_get_filtered_sorted('anime_list_view', 'anime_list.html', params_tag_status, self.anime1, self.anime2)
        # Var olmayan etiket (sonuç yok)
        params_no_tag = {'tag': 'olmayan-etiket'}
        response = self.client.get(reverse('tracker:anime_list_view'), params_no_tag)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, self.anime1.title)
        self.assertNotContains(response, self.anime2.title)
        self.assertContains(response, "bulunamadı") # Sonuç yok mesajı

    def test_anime_detail_view(self):
        # Detay sayfasında etiketlerin göründüğünü kontrol et
        self.client.login(username='testuser1', password='password123')
        url = reverse('tracker:anime_detail', kwargs={'pk': self.anime1.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.anime1.title)
        self.assertContains(response, self.tag_action.name) # Etiket görünmeli
        self.assertContains(response, self.tag_comedy.name) # Etiket görünmeli
        self.assertContains(response, f"?tag={self.tag_action.slug}") # Etiket linki doğru mu?
        self.assertIn('is_favorite', response.context) # Favori durumu
        self.assertTrue(response.context['is_owner']) # Sahibi mi?

    def test_anime_edit_view_post_tags(self):
        # Etiketleri güncelleme testi
        update_data = {'title': 'Updated Anime Tags', 'tags': 'Güncel, Test'}
        self._test_edit_view_post_valid('anime_edit', 'anime_detail', self.anime1, update_data)
        # Etiketleri temizleme testi
        update_data = {'tags': ''}
        self._test_edit_view_post_valid('anime_edit', 'anime_detail', self.anime1, update_data)


    # --- Favori View Testleri (Güncellendi) ---
    def test_toggle_favorite_view(self):
        """Favori ekleme/çıkarma AJAX view'ını test eder."""
        self.client.login(username='testuser1', password='password123')
        url = reverse("tracker:toggle_favorite")
        # Başlangıçta favori sayısını kontrol et (context processor henüz test edilmiyor)
        initial_fav_count = Favorite.objects.filter(user=self.test_user1).count()

        # 1. Anime Ekleme
        data_anime = {'item_id': self.anime1.pk, 'item_type': 'anime'}
        response_add = self.client.post(url, json.dumps(data_anime), content_type='application/json', HTTP_X_REQUESTED_WITH='XMLHttpRequest') # AJAX isteği olduğunu belirt
        self.assertEqual(response_add.status_code, 200)
        self.assertJSONEqual(response_add.content, {'status': 'ok', 'is_favorite': True})
        self.assertEqual(Favorite.objects.filter(user=self.test_user1).count(), initial_fav_count + 1)
        self.assertTrue(Favorite.objects.filter(user=self.test_user1, content_type=self.anime_content_type, object_id=self.anime1.pk).exists())

        # 2. Tekrar Ekleme (Durum değişmemeli)
        response_add_again = self.client.post(url, json.dumps(data_anime), content_type='application/json', HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response_add_again.status_code, 200)
        self.assertJSONEqual(response_add_again.content, {'status': 'ok', 'is_favorite': False}) # Tekrar basınca kaldırır
        self.assertEqual(Favorite.objects.filter(user=self.test_user1).count(), initial_fav_count) # Sayı eski haline dönmeli
        self.assertFalse(Favorite.objects.filter(user=self.test_user1, content_type=self.anime_content_type, object_id=self.anime1.pk).exists())

        # 3. Tekrar ekle (sonraki test için)
        self.client.post(url, json.dumps(data_anime), content_type='application/json', HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(Favorite.objects.filter(user=self.test_user1).count(), initial_fav_count + 1)

        # 4. Farklı Tip Ekleme (Webtoon)
        data_webtoon = {'item_id': self.webtoon1.pk, 'item_type': 'webtoon'}
        response_add_webtoon = self.client.post(url, json.dumps(data_webtoon), content_type='application/json', HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response_add_webtoon.status_code, 200)
        self.assertJSONEqual(response_add_webtoon.content, {'status': 'ok', 'is_favorite': True})
        self.assertEqual(Favorite.objects.filter(user=self.test_user1).count(), initial_fav_count + 2) # Toplam 2 favori
        self.assertTrue(Favorite.objects.filter(user=self.test_user1, content_type=self.webtoon_content_type, object_id=self.webtoon1.pk).exists())

        # ... (Hata durumları testleri: _test_toggle_favorite_view_invalid_method, _test_toggle_favorite_view_unauthenticated vb. aynı kalabilir) ...
        print("Test Başarılı: Toggle Favorite (Ekleme/Çıkarma - Farklı Tipler).")


    def test_favorites_list_view(self):
        """Favoriler listesi görünümünü test eder."""
        self.client.login(username='testuser1', password='password123')
        # Favorileri ekle
        fav1 = Favorite.objects.create(user=self.test_user1, content_type=self.anime_content_type, object_id=self.anime1.pk)
        fav2 = Favorite.objects.create(user=self.test_user1, content_type=self.webtoon_content_type, object_id=self.webtoon1.pk)

        url = reverse("tracker:favorites_view")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "tracker/favorites.html")
        # Context ve içerik kontrolleri
        self.assertIn('grouped_favorites_list', response.context)
        self.assertEqual(len(response.context['grouped_favorites_list']), 2) # 2 grup (anime, webtoon)
        self.assertEqual(response.context['total_favorites'], 2)
        self.assertContains(response, self.anime1.title)
        self.assertContains(response, self.webtoon1.title)
        self.assertNotContains(response, self.manga1.title) # Favori olmayan
        # favorited_pks kontrolü (bu sayfadaki tüm öğeler favori olmalı)
        self.assertIn('favorited_pks', response.context)
        self.assertSetEqual(response.context['favorited_pks'], {self.anime1.pk, self.webtoon1.pk})
        # Toplam sayı ID'sini kontrol et
        self.assertContains(response, 'id="favorites-page-total-count">2</span>')

        print("Test Başarılı: Favorites List View.")


    # --- API View Testleri (Mocking ile - YENİ) ---

    # MangaDex Arama Testi
    @patch('tracker.mangadex_service.search_manga') # search_manga fonksiyonunu mockla
    def test_manga_api_search_view(self, mock_search_manga):
        """MangaDex API arama view'ını test eder (mocklanmış)."""
        self.client.login(username='testuser1', password='password123')
        url = reverse("tracker:manga_api_search")
        search_query = "Test Manga"

        # 1. Mock servisin dönüş değerini ayarla
        mock_search_manga.return_value = self.mock_mangadex_search_result
        # Kullanıcının listesine mock sonuç ID'sini ekleyelim (önceden var kontrolü için)
        existing_manga = Manga.objects.create(user=self.test_user1, title="Existing Mock", mangadex_id=self.mock_mangadex_search_result[0]['id'])

        # 2. POST isteği gönder
        response = self.client.post(url, {'query': search_query})

        # 3. Yanıtı ve context'i kontrol et
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'tracker/manga_api_search.html')
        mock_search_manga.assert_called_once_with(search_query) # Servis doğru argümanla çağrıldı mı?
        self.assertEqual(response.context['query'], search_query)
        self.assertEqual(len(response.context['search_results']), 1)
        self.assertEqual(response.context['search_results'][0]['title'], self.mock_mangadex_search_result[0]['title'])
        # Var olan ID kontrolü
        self.assertIn('existing_ids_in_db', response.context)
        self.assertIn(str(existing_manga.mangadex_id), response.context['existing_ids_in_db'])
        # Template'de "Listede Mevcut" rozeti görünmeli
        self.assertContains(response, 'Listede Mevcut')
        self.assertNotContains(response, 'Listeme Ekle') # Ekle butonu olmamalı
        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(any("sonuç bulundu" in str(m) for m in messages)) # Başarı mesajı

        # 4. Sonuç bulunamama durumunu test et
        mock_search_manga.return_value = [] # Boş liste dön
        response_no_result = self.client.post(url, {'query': "bulunmaz"})
        self.assertEqual(response_no_result.status_code, 200)
        self.assertEqual(len(response_no_result.context['search_results']), 0)
        messages_no = list(get_messages(response_no_result.wsgi_request))
        self.assertTrue(any("bulunamadı" in str(m) for m in messages_no)) # Uyarı mesajı

        # 5. API hatası durumunu test et
        mock_search_manga.return_value = None # Hata durumu
        response_error = self.client.post(url, {'query': "hata"})
        self.assertEqual(response_error.status_code, 200)
        self.assertIsNone(response_error.context['search_results'])
        messages_err = list(get_messages(response_error.wsgi_request))
        self.assertTrue(any("hata oluştu" in str(m) for m in messages_err)) # Hata mesajı

        print("Test Başarılı: MangaDex API Arama View (Mocked).")


    # MangaDex Ekleme Testi
    @patch('tracker.mangadex_service.get_manga_details') # get_manga_details'i mockla
    def test_md_add_item_view_manga(self, mock_get_details):
        """MangaDex'ten manga ekleme view'ını test eder (mocklanmış)."""
        self.client.login(username='testuser1', password='password123')
        mock_id = self.mock_mangadex_details_manga['mangadex_id']
        url = reverse("tracker:md_add_item", kwargs={'mangadex_id': mock_id})

        # 1. GET isteği (Formu gösterme)
        mock_get_details.return_value = self.mock_mangadex_details_manga # Mock API yanıtı
        response_get = self.client.get(url)
        self.assertEqual(response_get.status_code, 200)
        self.assertTemplateUsed(response_get, 'tracker/md_form_api.html')
        self.assertIsInstance(response_get.context['form'], MangaForm) # Doğru form mu?
        self.assertEqual(response_get.context['form'].initial['title'], self.mock_mangadex_details_manga['title']) # Form dolu mu?
        self.assertEqual(response_get.context['form'].initial['tags'], self.mock_mangadex_details_manga['tags']) # Etiketler geldi mi?
        mock_get_details.assert_called_once_with(str(mock_id)) # Servis çağrıldı mı?

        # 2. POST isteği (Kaydetme)
        form_data = self.mock_mangadex_details_manga.copy() # API verisini al
        form_data['status'] = 'Watching' # Kullanıcı durumu seçti
        form_data['rating'] = 8 # Kullanıcı puan verdi
        form_data['chapters_read'] = 10 # Kullanıcı okuma bilgisi girdi
        form_data.pop('detected_type', None) # Formda olmayanları çıkar
        form_data.pop('tags_list', None)
        form_data.pop('mangadex_id', None) # ID formda gönderilmez

        initial_manga_count = Manga.objects.filter(user=self.test_user1).count()
        response_post = self.client.post(url, form_data)

        # Kayıt sonrası kontrol
        self.assertEqual(Manga.objects.filter(user=self.test_user1).count(), initial_manga_count + 1)
        new_manga = Manga.objects.get(user=self.test_user1, mangadex_id=mock_id)
        self.assertEqual(new_manga.title, form_data['title'])
        self.assertEqual(new_manga.status, 'Watching')
        self.assertEqual(new_manga.rating, 8)
        self.assertEqual(new_manga.chapters_read, 10)
        self.assertSetEqual(set(t.name for t in new_manga.tags.all()), set(self.mock_mangadex_details_manga['tags_list'])) # Etiketler kaydedildi mi?

        # Yönlendirme kontrolü (Detay sayfasına)
        detail_url = reverse('tracker:manga_detail', kwargs={'pk': new_manga.pk})
        self.assertRedirects(response_post, detail_url)

        # Mesaj kontrolü
        response_followed = self.client.get(detail_url)
        messages = list(get_messages(response_followed.wsgi_request))
        self.assertTrue(any("başarıyla eklendi" in str(m) for m in messages))

        print("Test Başarılı: MangaDex Manga Ekleme View (Mocked).")

    # MangaDex Webtoon Ekleme Testi (Benzer şekilde yapılabilir, Manga yerine Webtoon kontrol edilir)
    @patch('tracker.mangadex_service.get_manga_details')
    def test_md_add_item_view_webtoon(self, mock_get_details):
        self.client.login(username='testuser1', password='password123')
        mock_id = self.mock_mangadex_details_webtoon['mangadex_id']
        url = reverse("tracker:md_add_item", kwargs={'mangadex_id': mock_id})
        mock_get_details.return_value = self.mock_mangadex_details_webtoon

        # GET
        response_get = self.client.get(url)
        self.assertEqual(response_get.status_code, 200)
        self.assertIsInstance(response_get.context['form'], WebtoonForm) # Webtoon formu mu?
        self.assertEqual(response_get.context['form'].initial['title'], self.mock_mangadex_details_webtoon['title'])

        # POST
        form_data = self.mock_mangadex_details_webtoon.copy()
        form_data['status'] = 'Completed'; form_data['chapters_read'] = 150;
        form_data.pop('detected_type', None); form_data.pop('tags_list', None); form_data.pop('mangadex_id', None)
        response_post = self.client.post(url, form_data)

        # Kontroller
        self.assertTrue(Webtoon.objects.filter(user=self.test_user1, mangadex_id=mock_id).exists())
        new_webtoon = Webtoon.objects.get(user=self.test_user1, mangadex_id=mock_id)
        self.assertEqual(new_webtoon.status, 'Completed')
        self.assertSetEqual(set(t.name for t in new_webtoon.tags.all()), set(self.mock_mangadex_details_webtoon['tags_list']))
        detail_url = reverse('tracker:webtoon_detail', kwargs={'pk': new_webtoon.pk})
        self.assertRedirects(response_post, detail_url)

        print("Test Başarılı: MangaDex Webtoon Ekleme View (Mocked).")


    # Jikan Anime Arama/Ekleme testleri de benzer şekilde @patch ile yazılabilir.
    # ...

    # --- Diğer View Testleri ---
    # Dashboard, Signup testleri genellikle aynı kalabilir.


# Testleri çalıştırmak için: python manage.py test tracker