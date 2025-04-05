// tracker/static/tracker/js/preloader.js

// Sayfanın tüm kaynakları (resimler vb.) yüklendiğinde çalışır
window.addEventListener('load', function() {
    const preloader = document.getElementById('preloader');
    if (preloader) {
        // Kısa bir gecikme ekleyerek ani geçişi engelle (isteğe bağlı)
        setTimeout(function() {
            preloader.classList.add('loaded');
            // console.log("Preloader gizlendi."); // Test için
        }, 250); // 250ms gecikme
    } else {
        // console.warn("Preloader elementi (#preloader) bulunamadı.");
    }
});