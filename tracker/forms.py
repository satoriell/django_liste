# tracker/forms.py
# Konum: /home/admin/App/django_liste/tracker/forms.py
# İyileştirmeler: Ortak alanlar MediaItemBaseForm'da toplandı, tags alanı eklendi, widget'lar iyileştirildi.

from django import forms
from django.core.exceptions import ValidationError
# taggit form alanı genellikle ModelForm ile otomatik halledilir.
# Özel bir widget (örn: autocompletion) istenirse ayrıca import edilir.
# from taggit.forms import TagField, TagWidget

from .models import Anime, Manga, Novel, Webtoon


# --- Ortak Form Mantığı (Base Form) ---
class MediaItemBaseForm(forms.ModelForm):
    # Tarih alanları için widget tanımlamaları (HTML5 date input)
    start_date = forms.DateField(
        required=False, # Zorunlu değil
        widget=forms.DateInput(
            format="%Y-%m-%d", # Tarayıcıların genellikle beklediği format
            attrs={"type": "date", "class": "form-control mb-2"},
        ),
        label="Başlama Tarihi",
    )
    end_date = forms.DateField(
        required=False, # Zorunlu değil
        widget=forms.DateInput(
            format="%Y-%m-%d",
            attrs={"type": "date", "class": "form-control mb-2"},
        ),
        label="Bitirme Tarihi",
    )

    # Not: TaggableManager alanı ModelForm tarafından otomatik olarak
    # forms.CharField ve TextInput widget'ı ile temsil edilir.
    # Eğer özel bir etiket widget'ı (örn: autocompletion) istenirse:
    # from taggit.forms import TagField, TagWidget
    # tags = TagField(required=False, widget=TagWidget(attrs={'class': 'form-control mb-2', 'placeholder': 'Etiketler (virgülle ayırın)'}))
    # Şimdilik varsayılan TextInput yeterli.

    class Meta:
        # Bu alanlar tüm alt formlar tarafından kullanılacak/miras alınacak
        # Model belirtmiyoruz çünkü bu abstract bir form.
        fields = [
            "title",
            "status",
            "rating",
            "start_date",
            "end_date",
            "cover_image_url",
            "notes",
            "tags",  # <- tags alanı buraya eklendi
        ]
        widgets = {
            "title": forms.TextInput(
                attrs={"class": "form-control mb-2", "placeholder": "Başlık", "required": True} # HTML required
            ),
            "status": forms.Select(attrs={"class": "form-select mb-2"}),
            "rating": forms.NumberInput(
                attrs={
                    "class": "form-control mb-2",
                    "placeholder": "Puan (0-10)",
                    "min": "0", # HTML tarafında da min/max kontrolü
                    "max": "10",
                    "step": "1", # Sadece tam sayı
                }
            ),
            "cover_image_url": forms.URLInput(
                attrs={
                    "class": "form-control mb-2",
                    "placeholder": "Kapak Resmi URL (http://...)",
                    "type": "url", # HTML5 URL tipi
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "form-control mb-2",
                    "rows": 3,
                    "placeholder": "Notlar...",
                }
            ),
            # tags alanı için widget (ModelForm varsayılan olarak TextInput kullanır)
            # Placeholder ekleyerek kullanıcıya yardımcı olalım.
            "tags": forms.TextInput(
                attrs={
                    "class": "form-control mb-2",
                    "placeholder": "Etiketleri virgülle ayırarak girin (örn: Aksiyon, Komedi)",
                }
            ),
        }

    # Form seviyesinde genel doğrulamalar
    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")
        rating = cleaned_data.get("rating")

        # 1. Tarih Kontrolü: Bitiş tarihi başlangıçtan önce olamaz.
        if start_date and end_date and end_date < start_date:
            # İki alana birden hata eklemek yerine form geneline hata ekleyebiliriz.
             # self.add_error('end_date', "Bitirme tarihi, başlama tarihinden önce olamaz.")
             raise ValidationError(
                 "Bitirme tarihi, başlama tarihinden önce olamaz.", code='invalid_date_range'
             )

        # 2. Puan Kontrolü (Modelde validator var ama burada da kontrol edilebilir)
        if rating is not None and (rating < 0 or rating > 10):
             # Belirli bir alana hata ekle
             self.add_error('rating', "Puan 0 ile 10 arasında olmalıdır.")
             # Alternatif: raise ValidationError({'rating': "Puan 0 ile 10 arasında olmalıdır."})

        return cleaned_data

# --- Anime Formu ---
class AnimeForm(MediaItemBaseForm):
    class Meta(MediaItemBaseForm.Meta): # Base Meta'dan miras al
        model = Anime
        # Base fields + Anime'ye özgü alanlar
        fields = MediaItemBaseForm.Meta.fields + [
            "episodes_watched",
            "total_episodes",
            "studio",
        ]
        # Base widgets + Anime'ye özgü widget'lar (varsa override et)
        widgets = {
            **MediaItemBaseForm.Meta.widgets, # Base widget'ları kopyala
            "episodes_watched": forms.NumberInput(
                attrs={
                    "class": "form-control mb-2",
                    "min": "0",
                    "placeholder": "İzlenen Bölüm",
                }
            ),
            "total_episodes": forms.NumberInput(
                attrs={
                    "class": "form-control mb-2",
                    "min": "0",
                    "placeholder": "Toplam Bölüm (Bilinmiyorsa boş bırakın)",
                }
            ),
            "studio": forms.TextInput(
                attrs={"class": "form-control mb-2", "placeholder": "Stüdyo"}
            ),
        }

    # Anime'ye özgü clean metodu
    def clean(self):
        cleaned_data = super().clean() # Önce base clean'i çalıştır (tarih, puan kontrolü)
        episodes_watched = cleaned_data.get("episodes_watched")
        total_episodes = cleaned_data.get("total_episodes")

        # İzlenen bölüm, toplam bölümden fazla olamaz
        if (
            total_episodes is not None # total_episodes girilmişse
            and episodes_watched is not None # episodes_watched girilmişse
            and episodes_watched > total_episodes # ve izlenen > toplam ise
        ):
            self.add_error( # episodes_watched alanına hata ekle
                "episodes_watched",
                "İzlenen bölüm sayısı toplam bölüm sayısından fazla olamaz.",
            )
            # raise ValidationError("İzlenen bölüm sayısı toplam bölüm sayısından fazla olamaz.") # Alternatif
        return cleaned_data

# --- Webtoon Formu ---
class WebtoonForm(MediaItemBaseForm):
    class Meta(MediaItemBaseForm.Meta):
        model = Webtoon
        fields = MediaItemBaseForm.Meta.fields + [
            "author",
            "artist",
            "chapters_read",
            "total_chapters",
            "platform",
        ]
        widgets = {
            **MediaItemBaseForm.Meta.widgets,
            "author": forms.TextInput(
                attrs={"class": "form-control mb-2", "placeholder": "Yazar"}
            ),
            "artist": forms.TextInput(
                attrs={"class": "form-control mb-2", "placeholder": "Çizer"}
            ),
            "chapters_read": forms.NumberInput(
                attrs={
                    "class": "form-control mb-2",
                    "min": "0",
                    "placeholder": "Okunan Bölüm",
                }
            ),
            "total_chapters": forms.NumberInput(
                attrs={
                    "class": "form-control mb-2",
                    "min": "0",
                    "placeholder": "Toplam Bölüm (Bilinmiyorsa boş bırakın)",
                }
            ),
            "platform": forms.TextInput(
                attrs={
                    "class": "form-control mb-2",
                    "placeholder": "Yayınlandığı Platform (Webtoon, Tapas vb.)",
                }
            ),
        }

    def clean(self):
        cleaned_data = super().clean()
        chapters_read = cleaned_data.get("chapters_read")
        total_chapters = cleaned_data.get("total_chapters")
        if (
            total_chapters is not None
            and chapters_read is not None
            and chapters_read > total_chapters
        ):
            self.add_error(
                "chapters_read",
                "Okunan bölüm sayısı toplam bölüm sayısından fazla olamaz.",
            )
        return cleaned_data

# --- Manga Formu ---
class MangaForm(MediaItemBaseForm):
    class Meta(MediaItemBaseForm.Meta):
        model = Manga
        fields = MediaItemBaseForm.Meta.fields + [
            "author",
            "artist",
            "chapters_read",
            "volumes_read",
            "total_chapters",
            "total_volumes",
        ]
        widgets = {
            **MediaItemBaseForm.Meta.widgets,
            "author": forms.TextInput(
                attrs={
                    "class": "form-control mb-2",
                    "placeholder": "Yazar (Mangaka)",
                }
            ),
            "artist": forms.TextInput(
                attrs={"class": "form-control mb-2", "placeholder": "Çizer"}
            ),
            "chapters_read": forms.NumberInput(
                attrs={
                    "class": "form-control mb-2",
                    "min": "0",
                    "placeholder": "Okunan Bölüm",
                }
            ),
            "volumes_read": forms.NumberInput(
                attrs={
                    "class": "form-control mb-2",
                    "min": "0",
                    "placeholder": "Okunan Cilt",
                }
            ),
            "total_chapters": forms.NumberInput(
                attrs={
                    "class": "form-control mb-2",
                    "min": "0",
                    "placeholder": "Toplam Bölüm (Bilinmiyorsa boş bırakın)",
                }
            ),
            "total_volumes": forms.NumberInput(
                attrs={
                    "class": "form-control mb-2",
                    "min": "0",
                    "placeholder": "Toplam Cilt (Bilinmiyorsa boş bırakın)",
                }
            ),
        }

    def clean(self):
        cleaned_data = super().clean()
        chapters_read = cleaned_data.get("chapters_read")
        total_chapters = cleaned_data.get("total_chapters")
        volumes_read = cleaned_data.get("volumes_read")
        total_volumes = cleaned_data.get("total_volumes")

        errors = {} # Hataları toplamak için bir sözlük
        if (
            total_chapters is not None
            and chapters_read is not None
            and chapters_read > total_chapters
        ):
            errors["chapters_read"] = ( # Sözlüğe hata mesajını ekle
                "Okunan bölüm sayısı toplam bölüm sayısından fazla olamaz."
            )
        if (
            total_volumes is not None
            and volumes_read is not None
            and volumes_read > total_volumes
        ):
            errors["volumes_read"] = ( # Sözlüğe hata mesajını ekle
                "Okunan cilt sayısı toplam cilt sayısından fazla olamaz."
            )

        # Eğer hata varsa, toplu olarak ValidationError fırlat
        if errors:
            raise ValidationError(errors)

        return cleaned_data

# --- Novel Formu ---
class NovelForm(MediaItemBaseForm):
    class Meta(MediaItemBaseForm.Meta):
        model = Novel
        fields = MediaItemBaseForm.Meta.fields + [
            "author",
            "chapters_read",
            "volumes_read",
            "total_chapters",
            "total_volumes",
        ]
        widgets = {
            **MediaItemBaseForm.Meta.widgets,
            "author": forms.TextInput(
                attrs={"class": "form-control mb-2", "placeholder": "Yazar"}
            ),
            "chapters_read": forms.NumberInput(
                attrs={
                    "class": "form-control mb-2",
                    "min": "0",
                    "placeholder": "Okunan Bölüm",
                }
            ),
            "volumes_read": forms.NumberInput(
                attrs={
                    "class": "form-control mb-2",
                    "min": "0",
                    "placeholder": "Okunan Cilt",
                }
            ),
            "total_chapters": forms.NumberInput(
                attrs={
                    "class": "form-control mb-2",
                    "min": "0",
                    "placeholder": "Toplam Bölüm (Bilinmiyorsa boş bırakın)",
                }
            ),
            "total_volumes": forms.NumberInput(
                attrs={
                    "class": "form-control mb-2",
                    "min": "0",
                    "placeholder": "Toplam Cilt (Bilinmiyorsa boş bırakın)",
                }
            ),
        }

    # MangaForm ile aynı clean mantığı
    def clean(self):
        cleaned_data = super().clean()
        chapters_read = cleaned_data.get("chapters_read")
        total_chapters = cleaned_data.get("total_chapters")
        volumes_read = cleaned_data.get("volumes_read")
        total_volumes = cleaned_data.get("total_volumes")

        errors = {}
        if (
            total_chapters is not None
            and chapters_read is not None
            and chapters_read > total_chapters
        ):
            errors["chapters_read"] = (
                "Okunan bölüm sayısı toplam bölüm sayısından fazla olamaz."
            )
        if (
            total_volumes is not None
            and volumes_read is not None
            and volumes_read > total_volumes
        ):
            errors["volumes_read"] = (
                "Okunan cilt sayısı toplam cilt sayısından fazla olamaz."
            )
        if errors:
            raise ValidationError(errors)
        return cleaned_data