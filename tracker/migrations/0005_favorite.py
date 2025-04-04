# Generated by Django 5.2 on 2025-04-04 12:46

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        ('tracker', '0004_alter_anime_options_alter_manga_options_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Favorite',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('object_id', models.PositiveIntegerField(verbose_name='Obje ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Eklenme Zamanı')),
                ('content_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='contenttypes.contenttype', verbose_name='İçerik Türü')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='favorites', to=settings.AUTH_USER_MODEL, verbose_name='Kullanıcı')),
            ],
            options={
                'verbose_name': 'Favori',
                'verbose_name_plural': 'Favoriler',
                'ordering': ['-created_at'],
                'constraints': [models.UniqueConstraint(fields=('user', 'content_type', 'object_id'), name='unique_user_content_favorite')],
            },
        ),
    ]
