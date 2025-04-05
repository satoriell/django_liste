// tracker/static/tracker/js/favorites_ajax.js
// İyileştirmeler: Spinner, Sayı Güncelleme (Navbar & Sayfa), Kart Kaldırma, Hata Yönetimi.

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

/**
 * Navbar ve (varsa) favoriler sayfasındaki favori sayılarını günceller.
 * @param {number} change Sayıdaki değişim (+1 favoriye eklenince, -1 çıkarılınca).
 */
function updateFavoriteCounts(change) {
    // 1. Navbar Rozetini Güncelle
    const navbarBadge = document.getElementById('navbar-favorite-count');
    if (navbarBadge) {
        let currentCount = parseInt(navbarBadge.textContent || '0', 10);
        let newCount = Math.max(0, currentCount + change); // Negatif olamaz
        navbarBadge.textContent = newCount;
        // Sayı 0'dan büyükse göster, değilse gizle
        navbarBadge.style.display = newCount > 0 ? 'inline-block' : 'none';
    } else {
         // Geliştirme sırasında uyarı vermek faydalı olabilir
         // console.warn('Navbar favori sayısı rozeti bulunamadı (ID: navbar-favorite-count)');
    }

    // 2. Favoriler Sayfasındaki Toplam Sayıyı Güncelle (eğer o sayfadaysak)
    const pageTotalElement = document.getElementById('favorites-page-total-count');
    // Sadece favoriler sayfasındaysak ve element varsa güncelle
    if (window.location.pathname.startsWith('/favorites') && pageTotalElement) {
        let currentPageCount = parseInt(pageTotalElement.textContent || '0', 10);
        let newPageCount = Math.max(0, currentPageCount + change); // Negatif olamaz
        pageTotalElement.textContent = newPageCount;
         // İsteğe bağlı: Eğer sayı 0 olursa "Listeniz boş" mesajı gösterilebilir
         // const favoritesContainer = document.querySelector('.row.g-4.mb-4'); // Veya daha spesifik bir seçici
         // if (newPageCount === 0 && favoritesContainer) {
         //     favoritesContainer.innerHTML = '<div class="col-12"><div class="alert alert-info text-center">Favori listeniz boşaldı.</div></div>';
         // }
    }
}

/**
 * Favori ekleme/çıkarma butonlarına tıklamaları dinler ve AJAX isteği gönderir.
 */
document.addEventListener('click', function(event) {
    // Tıklanan element veya üst elementlerinden .js-toggle-favorite sınıfına sahip olanı bul
    const favoriteButton = event.target.closest('.js-toggle-favorite');

    if (favoriteButton) {
        event.preventDefault(); // Linkin varsayılan davranışını engelle (eğer a etiketi ise)
        // Eğer buton zaten işleniyorsa (spinner gösteriliyorsa) tekrar tıklamayı engelle
        if (favoriteButton.classList.contains('processing')) return;

        favoriteButton.classList.add('processing'); // İşlemde olduğunu işaretle
        favoriteButton.disabled = true; // Butonu geçici olarak devre dışı bırak

        // --- Spinner ekleme ---
        const originalIconHTML = favoriteButton.innerHTML; // Orijinal ikonu (örn: <i class="fas fa-star"></i>) sakla
        // Bootstrap spinner ekle (küçük boyutlu - sm)
        favoriteButton.innerHTML = `
            <span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
            <span class="visually-hidden">Yükleniyor...</span>
        `;
        // --- Spinner ekleme sonu ---

        const itemId = favoriteButton.dataset.itemId;
        const itemType = favoriteButton.dataset.itemType;
        const toggleUrl = '/favorite/toggle/'; // Bu URL tracker.urls.py içinde tanımlı olmalı
        const csrftoken = getCookie('csrftoken'); // CSRF token'ı al

        // Gerekli bilgiler eksikse işlemi durdur ve hata ver
        if (!itemId || !itemType || !csrftoken) {
            console.error('Favori Toggle Hatası: Gerekli veri eksik (itemId, itemType veya CSRFToken).');
            alert('Favori işlemi sırasında bir hata oluştu. Lütfen sayfayı yenileyip tekrar deneyin.');
            favoriteButton.innerHTML = originalIconHTML; // Orijinal ikonu geri yükle
            favoriteButton.classList.remove('processing');
            favoriteButton.disabled = false;
            return;
        }

        // AJAX isteğini gönder
        fetch(toggleUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrftoken // CSRF token'ı header'a ekle
            },
            body: JSON.stringify({ item_id: itemId, item_type: itemType }) // Veriyi JSON olarak gönder
        })
        .then(response => {
            // HTTP yanıtı başarılı değilse (4xx, 5xx) hata fırlat
            if (!response.ok) {
                 // Sunucudan gelen JSON hata mesajını almaya çalış
                 return response.json().then(err => { throw new Error(err.message || `Sunucu hatası: ${response.status}`); });
            }
            // Başarılı yanıtı JSON olarak parse et
            return response.json();
        })
        .then(data => {
            // Sunucudan gelen yanıtı işle
            if (data.status === 'ok') {
                // Başarılı: Buton stilini ve sayıyı güncelle
                favoriteButton.classList.remove('btn-warning', 'btn-outline-warning', 'pulse-effect');
                if (data.is_favorite) { // Eğer favoriye eklendiyse
                    favoriteButton.classList.add('btn-warning'); // Dolu yıldız stili
                    favoriteButton.setAttribute('title', 'Favorilerden Çıkar');
                    updateFavoriteCounts(1); // Sayıyı 1 artır
                    // Pulse efekti (opsiyonel)
                    favoriteButton.classList.add('pulse-effect');
                    // Efektin bitmesi için kısa bir süre sonra sınıfı kaldır
                    setTimeout(() => favoriteButton.classList.remove('pulse-effect'), 600);
                } else { // Eğer favoriden çıkarıldıysa
                    favoriteButton.classList.add('btn-outline-warning'); // Boş yıldız stili
                    favoriteButton.setAttribute('title', 'Favoriye Ekle');
                    updateFavoriteCounts(-1); // Sayıyı 1 azalt

                    // --- Favoriler sayfasındaysak kartı kaldır ---
                    if (window.location.pathname.startsWith('/favorites/')) {
                        const cardColumn = favoriteButton.closest('.col'); // Kartın bulunduğu sütunu bul
                        if (cardColumn) {
                            // Animasyonlu kaldırma
                            cardColumn.style.transition = 'opacity 0.4s ease-out, transform 0.4s ease-out';
                            cardColumn.style.opacity = '0';
                            cardColumn.style.transform = 'scale(0.95)';
                            // Animasyon bittikten sonra DOM'dan kaldır
                            setTimeout(() => cardColumn.remove(), 400);
                        }
                    }
                    // --- Kart kaldırma sonu ---
                }
                 // İşlem başarılı olduğu için spinner yerine orijinal ikonu geri yükle
                 // Eğer favoriler sayfasında kart kaldırılmadıysa (yani favoriye eklendiyse veya başka sayfadaysa)
                 if (!(window.location.pathname.startsWith('/favorites/') && !data.is_favorite)) {
                      favoriteButton.innerHTML = originalIconHTML;
                 }

            } else {
                // Sunucu 'ok' durumu döndürmediyse hata göster
                console.error('Favori işlemi sunucu tarafında başarısız:', data.message);
                alert(`Favori işlemi başarısız oldu: ${data.message || 'Bilinmeyen bir hata oluştu.'}`);
                 favoriteButton.innerHTML = originalIconHTML; // Hata durumunda ikonu geri yükle
            }
        })
        .catch(error => {
            // AJAX isteği sırasında (network vb.) veya .then() içinde bir hata oluşursa
            console.error('Favori Toggle AJAX Hatası:', error);
            alert(`İşlem sırasında bir hata oluştu: ${error.message}`);
            favoriteButton.innerHTML = originalIconHTML; // Hata durumunda ikonu geri yükle
        })
        .finally(() => {
            // İşlem başarılı da olsa hatalı da olsa çalışacak kısım
            // Eğer favoriler sayfasında kart kaldırıldıysa butona dokunma
             if (!(window.location.pathname.startsWith('/favorites/') && favoriteButton.classList.contains('btn-outline-warning'))) {
                 // Hata durumunda veya favoriye ekleme durumunda spinner'ın kaldırıldığından emin ol
                  if (favoriteButton.querySelector('.spinner-border')) {
                     favoriteButton.innerHTML = originalIconHTML;
                 }
             }
             favoriteButton.classList.remove('processing'); // İşlemde işaretini kaldır
             favoriteButton.disabled = false; // Butonu tekrar aktif et
        });
    }
});