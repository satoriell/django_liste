// tracker/static/tracker/js/favorites_ajax.js

/**
 * CSRF token'ını cookie'lerden almak için yardımcı fonksiyon.
 * Django'nun CSRF korumasıyla POST istekleri göndermek için gereklidir.
 * @param {string} name Cookie adı (genellikle 'csrftoken')
 * @returns {string|null} CSRF token değeri veya bulunamazsa null.
 */
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            // Cookie string'i isim=değer şeklinde başlıyor mu?
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

/**
 * Favori ekleme/çıkarma butonlarına tıklamaları dinler ve AJAX isteği gönderir.
 */
document.addEventListener('click', function(event) {
    // Tıklanan element veya üst elementlerinden biri favori butonu mu?
    const favoriteButton = event.target.closest('.js-toggle-favorite');

    if (favoriteButton) {
        event.preventDefault(); // Eğer buton bir link olsaydı varsayılan davranışı engellerdik

        const itemId = favoriteButton.dataset.itemId;
        const itemType = favoriteButton.dataset.itemType;
        // DÜZELTME: URL'yi Django template yerine doğrudan yazmak daha güvenli olabilir
        // Ancak önceki kodda /favorite/toggle/ olarak sabit yazılmıştı, öyle bırakalım.
        // Daha iyisi: URL'yi bir data attribute'dan almak (örn: data-toggle-url)
        const toggleUrl = '/favorite/toggle/';
        const csrftoken = getCookie('csrftoken');

        if (!itemId || !itemType || !csrftoken) {
            console.error('Hata: Gerekli veri (item-id, item-type veya CSRF token) eksik.');
            return;
        }

        // Fetch API kullanarak POST isteği gönderme
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
                 return response.json().then(err => { throw new Error(err.message || 'Bilinmeyen sunucu hatası'); });
            }
            return response.json();
        })
        .then(data => {
            if (data.status === 'ok') {
                // Butonun stilini güncelle
                favoriteButton.classList.remove('btn-warning', 'btn-outline-warning');
                if (data.is_favorite) {
                    favoriteButton.classList.add('btn-warning');
                    favoriteButton.setAttribute('title', 'Favorilerden Çıkar');
                } else {
                    favoriteButton.classList.add('btn-outline-warning');
                     favoriteButton.setAttribute('title', 'Favoriye Ekle');
                }
                 console.log('Favori durumu güncellendi:', data.is_favorite);

                // --- YENİ: Pulse efekti ekle ve kaldır ---
                favoriteButton.classList.add('pulse-effect');
                // Animasyon süresi (0.5s = 500ms) bittikten sonra sınıfı kaldır
                setTimeout(() => {
                    favoriteButton.classList.remove('pulse-effect');
                }, 500);
                // --- Pulse efekti sonu ---

            } else {
                console.error('Favori işlemi başarısız:', data.message);
            }
        })
        .catch(error => {
            console.error('AJAX Hatası:', error);
        });
    }
});