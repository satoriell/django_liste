# tracker/forms.py
# Konum: /home/admin/App/django_liste/tracker/forms.py

from django import forms
from django.core.exceptions import ValidationError

from .models import Anime, Manga, Novel, Webtoon


# --- Ortak Form Mantığı ---
class MediaItemBaseForm(forms.ModelForm):
    # Tarih alanları için widget tanımlamaları
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(
            # type="date" input'unun beklediği YYYY-MM-DD formatını belirtiyoruz
            format="%Y-%m-%d",
            attrs={"type": "date", "class": "form-control mb-2"},
        ),
        label="Başlama Tarihi",
    )
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(
            # type="date" input'unun beklediği YYYY-MM-DD formatını belirtiyoruz
            format="%Y-%m-%d",
            attrs={"type": "date", "class": "form-control mb-2"},
        ),
        label="Bitirme Tarihi",
    )

    class Meta:
        # Bu alanlar tüm alt formlar tarafından kullanılacak
        fields = [
            "title",
            "status",
            "rating",
            "start_date",
            "end_date",
            "cover_image_url",
            "notes",
        ]
        # Not: DateInput widget'ları yukarıda format ile tanımlandığı için
        # Meta.widgets içinde tekrar belirtmeye gerek yok.
        widgets = {
            "title": forms.TextInput(
                attrs={"class": "form-control mb-2", "placeholder": "Başlık"}
            ),
            "status": forms.Select(attrs={"class": "form-select mb-2"}),
            "rating": forms.NumberInput(
                attrs={
                    "class": "form-control mb-2",
                    "placeholder": "Puan (0-10)",
                }
            ),
            "cover_image_url": forms.URLInput(
                attrs={
                    "class": "form-control mb-2",
                    "placeholder": "Kapak Resmi URL (http://...)",
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "form-control mb-2",
                    "rows": 3,
                    "placeholder": "Notlar...",
                }
            ),
        }

    # Form seviyesinde genel doğrulama (Tarih kontrolü)
    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")

        if start_date and end_date and end_date < start_date:
            raise ValidationError(
                "Bitirme tarihi, başlama tarihinden önce olamaz."
            )

        return cleaned_data


# --- Anime Formu ---
class AnimeForm(MediaItemBaseForm):
    class Meta(MediaItemBaseForm.Meta):
        model = Anime
        fields = MediaItemBaseForm.Meta.fields + [
            "episodes_watched",
            "total_episodes",
            "studio",
        ]
        widgets = {
            **MediaItemBaseForm.Meta.widgets,
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
                    "placeholder": "Toplam Bölüm (Bilmiyorsan boş bırak)",
                }
            ),
            "studio": forms.TextInput(
                attrs={"class": "form-control mb-2", "placeholder": "Stüdyo"}
            ),
        }

    def clean(self):
        cleaned_data = super().clean()
        episodes_watched = cleaned_data.get("episodes_watched")
        total_episodes = cleaned_data.get("total_episodes")
        if (
            total_episodes is not None
            and episodes_watched is not None
            and episodes_watched > total_episodes
        ):
            self.add_error(
                "episodes_watched",
                "İzlenen bölüm sayısı toplam bölüm sayısından fazla olamaz.",
            )
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
                    "placeholder": "Toplam Bölüm (Bilmiyorsan boş bırak)",
                }
            ),
            "platform": forms.TextInput(
                attrs={
                    "class": "form-control mb-2",
                    "placeholder": "Yayınlandığı Platform",
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
                    "placeholder": "Toplam Bölüm (Bilmiyorsan boş bırak)",
                }
            ),
            "total_volumes": forms.NumberInput(
                attrs={
                    "class": "form-control mb-2",
                    "min": "0",
                    "placeholder": "Toplam Cilt (Bilmiyorsan boş bırak)",
                }
            ),
        }

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
                    "placeholder": "Toplam Bölüm (Bilmiyorsan boş bırak)",
                }
            ),
            "total_volumes": forms.NumberInput(
                attrs={
                    "class": "form-control mb-2",
                    "min": "0",
                    "placeholder": "Toplam Cilt (Bilmiyorsan boş bırak)",
                }
            ),
        }

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