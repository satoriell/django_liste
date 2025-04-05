// tracker/static/tracker/js/theme_toggle.js

document.addEventListener('DOMContentLoaded', function() {
    const themeToggleButton = document.getElementById('theme-toggle-button');
    const htmlElement = document.documentElement; // <html> elementi
    const storageKey = 'theme'; // localStorage anahtarı

    // Kayıtlı temayı al veya varsayılanı ('light') kullan
    const currentTheme = localStorage.getItem(storageKey) || 'light';
    // Sayfa yüklendiğinde temayı uygula
    htmlElement.setAttribute('data-theme', currentTheme);
    // console.log(`Başlangıç teması: ${currentTheme}`); // Test için

    // Tema değiştirme fonksiyonu
    function switchTheme() {
        const oldTheme = htmlElement.getAttribute('data-theme');
        const newTheme = oldTheme === 'light' ? 'dark' : 'light';
        htmlElement.setAttribute('data-theme', newTheme);
        localStorage.setItem(storageKey, newTheme); // Yeni seçimi kaydet
        // console.log(`Tema değiştirildi: ${newTheme}`); // Test için
    }

    // Butona tıklama olayını ekle
    if (themeToggleButton) {
        themeToggleButton.addEventListener('click', switchTheme);
        // console.log("Tema değiştirme butonu eventi eklendi."); // Test için
    } else {
        // console.warn("Tema değiştirme butonu (#theme-toggle-button) bulunamadı.");
    }
});