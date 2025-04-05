// tracker/static/tracker/js/logout_handler.js

document.addEventListener('DOMContentLoaded', function() {
    const logoutLink = document.getElementById('logout-link');
    const logoutForm = document.getElementById('logout-form');

    if (logoutLink && logoutForm) {
        logoutLink.addEventListener('click', function(event) {
            event.preventDefault(); // Linkin varsayılan davranışını engelle
            logoutForm.submit(); // Gizli formu gönder
        });
        // console.log("Logout handler eklendi."); // Test için
    } else {
        // Eğer link veya form bulunamazsa (örn. kullanıcı giriş yapmamışsa)
        // konsola uyarı yazılabilir ama genelde gereksiz.
        // console.warn("Logout link veya form bulunamadı.");
    }
});