// tracker/static/tracker/js/navbar_scroll.js

document.addEventListener('DOMContentLoaded', function() {
    const mainNavbar = document.getElementById('mainNavbar');
    const scrollThreshold = 50; // Sınıfın ekleneceği kaydırma mesafesi (piksel)

    if (mainNavbar) {
        // Navbar'ın scroll durumunu kontrol eden fonksiyon
        function handleNavbarScroll() {
            if (window.scrollY > scrollThreshold) {
                mainNavbar.classList.add('navbar-scrolled');
            } else {
                mainNavbar.classList.remove('navbar-scrolled');
            }
        }

        // Sayfa ilk yüklendiğinde durumu kontrol et
        handleNavbarScroll();

        // Scroll olayını dinle
        window.addEventListener('scroll', handleNavbarScroll);

        // console.log("Navbar scroll handler eklendi."); // Test için
    } else {
        // console.warn("Navbar elementi (#mainNavbar) bulunamadı.");
    }
});