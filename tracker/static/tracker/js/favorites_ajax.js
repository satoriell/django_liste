// tracker/static/tracker/js/favorites_ajax.js

/**
 * CSRF token'ını cookie'lerden almak için yardımcı fonksiyon.
 */
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// --- YENİ: Favori Sayılarını Güncelleme Fonksiyonu ---
/**
 * Navbar ve (varsa) favoriler sayfasındaki favori sayılarını günceller.
 * @param {number} change Sayıdaki değişim (+1 favoriye eklenince, -1 çıkarılınca).
 */
function updateFavoriteCounts(change) {
    // Navbar Rozeti
    const navbarBadge = document.getElementById('navbar-favorite-count');
    if (navbarBadge) {
        let currentCount = parseInt(navbarBadge.textContent || '0', 10);
        let newCount = currentCount + change;
        newCount = Math.max(0, newCount); // Sayı negatif olamaz

        navbarBadge.textContent = newCount;

        // Sayı 0'dan büyükse rozeti göster, değilse gizle
        if (newCount > 0) {
            navbarBadge.style.display = 'inline-block'; // veya sadece 'inline' vs. Bootstrap stiline göre
        } else {
            navbarBadge.style.display = 'none';
        }
    } else {
         console.warn('Navbar favori sayısı rozeti bulunamadı (ID: navbar-favorite-count)');
    }

    // Favoriler Sayfası Toplam Sayısı (Sadece o sayfadaysa güncellenir)
    const pageTotalElement = document.getElementById('favorites-page-total-count');
     // Sadece favoriler sayfasındaysak ve element varsa güncelle
    if (window.location.pathname === '/favorites/' && pageTotalElement) {
        let currentPageCount = parseInt(pageTotalElement.textContent || '0', 10);
        let newPageCount = currentPageCount + change;
        newPageCount = Math.max(0, newPageCount); // Negatif olamaz

        pageTotalElement.textContent = newPageCount;
    }
}
// --- Sayı Güncelleme Fonksiyonu Sonu ---

/**
 * Favori ekleme/çıkarma butonlarına tıklamaları dinler ve AJAX isteği gönderir.
 */
document.addEventListener('click', function(event) {
    const favoriteButton = event.target.closest('.js-toggle-favorite');

    if (favoriteButton) {
        event.preventDefault();
        if (favoriteButton.classList.contains('processing')) {
             console.log('İstek zaten işleniyor...');
             return;
        }
        favoriteButton.classList.add('processing');
        favoriteButton.disabled = true;

        const itemId = favoriteButton.dataset.itemId;
        const itemType = favoriteButton.dataset.itemType;
        const toggleUrl = '/favorite/toggle/'; // Django URL name: tracker:toggle_favorite
        const csrftoken = getCookie('csrftoken');

        if (!itemId || !itemType || !csrftoken) {
            console.error('Hata: Gerekli veri eksik.');
            favoriteButton.classList.remove('processing');
            favoriteButton.disabled = false;
            return;
        }

        fetch(toggleUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrftoken
            },
            body: JSON.stringify({
                item_id: itemId,
                item_type: itemType
            })
        })
        .then(response => {
            if (!response.ok) {
                console.error('Sunucu Hatası:', response.status, response.statusText);
                 return response.json().then(err => { throw new Error(err.message || `Sunucu hatası: ${response.status}`); });
            }
            return response.json();
        })
        .then(data => {
            if (data.status === 'ok') {
                favoriteButton.classList.remove('btn-warning', 'btn-outline-warning', 'pulse-effect');

                if (data.is_favorite) {
                    // Favoriye Eklendi
                    favoriteButton.classList.add('btn-warning');
                    favoriteButton.setAttribute('title', 'Favorilerden Çıkar');
                    updateFavoriteCounts(1); // Sayıyı 1 artır
                    // Pulse efekti
                    favoriteButton.classList.add('pulse-effect');
                    setTimeout(() => {
                        favoriteButton.classList.remove('pulse-effect');
                    }, 600);

                } else {
                    // Favoriden Çıkarıldı
                    favoriteButton.classList.add('btn-outline-warning');
                    favoriteButton.setAttribute('title', 'Favoriye Ekle');
                    updateFavoriteCounts(-1); // Sayıyı 1 azalt

                    // Favoriler sayfasındaysak kartı kaldır
                    if (window.location.pathname === '/favorites/') {
                        const cardColumn = favoriteButton.closest('.col');
                        if (cardColumn) {
                             console.log('Favorilerden çıkarıldı, kart kaldırılıyor:', itemId);
                            cardColumn.style.transition = 'opacity 0.5s ease-out, transform 0.5s ease-out';
                            cardColumn.style.opacity = '0';
                            cardColumn.style.transform = 'scale(0.9)';
                            setTimeout(() => {
                                 cardColumn.remove();
                            }, 500);
                        } else {
                             console.warn('Kaldırılacak kart sütunu bulunamadı.');
                        }
                    }
                }
                 console.log('Favori durumu güncellendi:', data.is_favorite);

            } else {
                console.error('Favori işlemi başarısız:', data.message);
                 alert(`Favori işlemi başarısız oldu: ${data.message}`);
            }
        })
        .catch(error => {
            console.error('AJAX Hatası:', error);
             alert(`Bir hata oluştu: ${error.message}`);
        })
         .finally(() => {
             favoriteButton.classList.remove('processing');
             favoriteButton.disabled = false;
        });
    }
});