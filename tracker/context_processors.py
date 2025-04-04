# tracker/context_processors.py

from .models import Favorite

def favorites_processor(request):
    """
    Giriş yapmış kullanıcı için favori sayısını context'e ekler.
    """
    favorite_count = 0
    if request.user.is_authenticated:
        favorite_count = Favorite.objects.filter(user=request.user).count()
    return {'favorite_count': favorite_count}