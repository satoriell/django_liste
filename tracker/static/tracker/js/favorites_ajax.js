// tracker/static/tracker/js/favorites_ajax.js

document.addEventListener('DOMContentLoaded', () => {
    // --- CSRF Token Alma Fonksiyonu ---
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
    const csrftoken = getCookie('csrftoken');

    // --- Navbar Favori Sayısını Güncelleme Fonksiyonu ---
    function updateNavbarFavoriteCount(change) {
        const countElement = document.getElementById('navbar-favorite-count');
        if (countElement) {
            try {
                let currentCount = parseInt(countElement.textContent || '0', 10);
                if (isNaN(currentCount)) {
                    currentCount = 0;
                }
                const newCount = Math.max(0, currentCount + change);
                countElement.textContent = newCount;
                countElement.style.display = newCount > 0 ? 'inline-block' : 'none';
            } catch (e) {
                console.error("Navbar favori sayısı güncellenirken hata:", e);
            }
        }
    }

    // --- Favori Butonlarına Tıklama Olayını Dinleme ---
    // '.js-toggle-favorite' sınıfına sahip tüm butonları DİNAMİK OLARAK ele al
    // Sayfa içeriği AJAX ile değişebileceği için, event delegation kullanmak daha sağlamdır.
    // document.body yerine daha spesifik bir üst konteyner seçilebilir (performans için).
    document.body.addEventListener('click', function(event) {
        // Tıklanan element veya onun üst elementlerinden biri buton mu?
        const button = event.target.closest('.js-toggle-favorite');

        if (button) { // Eğer favori butonu tıklandıysa
            const itemId = button.dataset.itemId;
            const itemType = button.dataset.itemType;
            const url = '/favorite/toggle/'; // Bu URL'in doğru olduğundan emin olun veya dinamik alın

            // Gerekli veriler eksikse işlemi durdur
            if (!itemId || !itemType || !csrftoken) {
                 console.error("Favori toggle için gerekli veri eksik:", {itemId, itemType, csrftoken});
                 alert("Favori işlemi gerçekleştirilemiyor (eksik bilgi).");
                 return; // Fonksiyondan çık
            }

            // Butonu geçici olarak devre dışı bırak ve ikon değiştir
            button.disabled = true;
            const iconElement = button.querySelector('i'); // İkon elementini bul
            let originalIconClass = 'fas fa-star'; // Varsayılan veya mevcut ikon
            if(iconElement) {
                originalIconClass = iconElement.className;
                iconElement.className = 'fas fa-spinner fa-spin'; // Dönen ikon
            } else {
                 // Eğer ikon bulunamazsa, butona metin ekleyebiliriz
                 button.textContent = "..."; // Geçici metin
            }


            fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrftoken,
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({
                    item_id: itemId,
                    item_type: itemType
                })
            })
            .then(response => {
                if (!response.ok) {
                    return response.json().then(errData => {
                         throw new Error(errData.message || `HTTP error! status: ${response.status}`);
                    }).catch(() => {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    });
                 }
                return response.json();
            })
            .then(data => {
                if (data.status === 'ok') {
                    const isFavorite = data.is_favorite;
                    // Buton sınıflarını güncelle
                    button.classList.toggle('btn-warning', isFavorite);
                    button.classList.toggle('btn-outline-warning', !isFavorite);
                    // İkonu güncelle
                    if(iconElement) {
                        iconElement.className = isFavorite ? 'fas fa-star' : 'far fa-star'; // Dolu veya boş yıldız (regular stil gerekir)
                         // Alternatif (sadece solid varsa): iconElement.className = 'fas fa-star';
                    } else {
                         // İkon yoksa metni geri getir (veya ikonu dinamik ekle)
                         button.textContent = isFavorite ? 'Favoriden Çıkar' : 'Favoriye Ekle'; // Örnek metin
                    }
                    // Title ve aria-label güncelle
                    button.title = isFavorite ? 'Favorilerden Çıkar' : 'Favoriye Ekle';
                    button.setAttribute('aria-label', isFavorite ? `${itemType} ${itemId} favorilerden çıkar` : `${itemType} ${itemId} favoriye ekle`);

                    // Navbar sayacını güncelle
                    updateNavbarFavoriteCount(isFavorite ? 1 : -1);
                } else {
                    console.error('Favori işlemi başarısız:', data.message || 'Bilinmeyen sunucu hatası');
                    alert('Favori güncellenirken bir hata oluştu: ' + (data.message || 'Bilinmeyen sunucu hatası'));
                     // Başarısızlık durumunda ikonu eski haline getir
                     if(iconElement) { iconElement.className = originalIconClass; }
                }
            })
            .catch(error => {
                console.error('Favori toggle hatası:', error);
                alert('Favori durumu güncellenirken bir ağ hatası veya istemci hatası oluştu: ' + error.message);
                // Hata durumunda ikonu eski haline getir
                 if(iconElement) { iconElement.className = originalIconClass; }
                 else {
                    // İkon yoksa ve hata oluştuysa, metni eski haline getirebiliriz
                    const wasFavorite = button.classList.contains('btn-warning'); // Hata öncesi durumu tahmin et
                    button.textContent = wasFavorite ? 'Favoriden Çıkar' : 'Favoriye Ekle';
                 }
            })
            .finally(() => {
                // İşlem bitince butonu tekrar aktif et
                button.disabled = false;
                 // Eğer ikon hala spinner ise (örn. then bloğu çalışmadıysa) eski haline getir
                 if (iconElement && iconElement.classList.contains('fa-spinner')) {
                    iconElement.className = originalIconClass;
                 }
            });
        } // if (button) sonu
    }); // document.body event listener sonu

}); // DOMContentLoaded sonu