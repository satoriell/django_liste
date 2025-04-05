// tracker/static/tracker/js/aos_init.js

// DOM yüklendikten sonra çalıştır
document.addEventListener('DOMContentLoaded', function() {
    // AOS kütüphanesinin global scope'ta var olup olmadığını kontrol et
    if (typeof AOS !== 'undefined') {
        AOS.init({
            duration: 600, // Animasyon süresi (ms)
            once: true,    // Animasyon sadece bir kez oynatılsın
            // offset: 50, // Animasyonun tetiklenme mesafesi (isteğe bağlı)
            // delay: 100, // Genel gecikme (isteğe bağlı)
            // disable: 'mobile' // Mobilde animasyonları kapat (isteğe bağlı)
        });
        // console.log("AOS başlatıldı."); // Test için
    } else {
        console.warn("AOS kütüphanesi bulunamadı veya yüklenemedi. Animasyonlar çalışmayabilir.");
    }
});