// tracker/static/tracker/js/dashboard_charts.js
// responsive: false. Canvas width kaldırıldı. Görünüm iyileştirmeleri.

document.addEventListener('DOMContentLoaded', () => {
    const chartDataElement = document.getElementById('chartDataJson');
    let chartData = null;

    // ... (JSON veri okuma ve hata kontrolü aynı) ...
    if (!chartDataElement) { /* ... */ return; }
    try { chartData = JSON.parse(chartDataElement.textContent || "{}"); if (!chartData || typeof chartData !== 'object' || !chartData.typeLabels || !chartData.typeCounts || !chartData.statusLabels || !chartData.statusData) { throw new Error("..."); } } catch (e) { /* ... */ return; }

    // Chart.js için genel seçenekler
    const commonChartOptions = {
        responsive: false, // Otomatik boyutlandırma kapalı
        maintainAspectRatio: false, // Canvas boyutlarına uymaya çalışır
        layout: {
            padding: 5
        },
        plugins: {
            legend: {
                position: 'bottom',
                align: 'center',
                labels: {
                    padding: 15, // Dikey boşluk artırıldı
                    boxWidth: 12,
                    font: { size: 12 }, // Font biraz büyütüldü
                    usePointStyle: true, // Nokta stili (daha şık olabilir)
                }
            },
            tooltip: {
                enabled: true,
                backgroundColor: 'rgba(0, 0, 0, 0.8)',
                titleFont: { weight: 'bold', size: 14 },
                bodyFont: { size: 13 },
                padding: 12, // Padding artırıldı
                cornerRadius: 4,
                displayColors: true,
                boxPadding: 4,
            }
        },
        // Animasyonlar
        animation: {
            duration: 1000, // Süre biraz artırıldı
            easing: 'easeOutBounce' // Farklı bir easing efekti
        },
        // Cihaz piksel oranını dikkate al (retina ekranlarda netlik için)
        // Bu genellikle responsive:true ile daha etkilidir ama deneyelim
        devicePixelRatio: window.devicePixelRatio || 1
    };

    // --- Tür Dağılım Grafiği (Doughnut) ---
    const typeCtx = document.getElementById('typeDistributionChart')?.getContext('2d');
    if (typeCtx && chartData.typeLabels && chartData.typeCounts) {
         try {
             new Chart(typeCtx, {
                 type: 'doughnut',
                 data: { labels: chartData.typeLabels, datasets: [{ label: 'Kayıt Sayısı', data: chartData.typeCounts, backgroundColor: ['rgba(108, 99, 255, 0.8)','rgba(25, 135, 84, 0.8)','rgba(220, 53, 69, 0.8)','rgba(147, 141, 255, 0.8)'], borderColor: ['rgba(108, 99, 255, 1)','rgba(25, 135, 84, 1)','rgba(220, 53, 69, 1)','rgba(147, 141, 255, 1)'], borderWidth: 2, hoverOffset: 10, hoverBorderColor: '#fff' }] }, // borderWidth, hoverOffset artırıldı
                 options: {
                     ...commonChartOptions,
                     cutout: '65%' // Ortadaki boşluk biraz artırıldı
                 }
             });
         } catch (e) { console.error("Tür dağılım grafiği hatası:", e); }
    } else { /* ... hata mesajı ... */ }

    // --- Durum Dağılım Grafiği (Pie) ---
    const statusCtx = document.getElementById('statusDistributionChart')?.getContext('2d');
    if (statusCtx && chartData.statusLabels && chartData.statusData) {
         try {
            const statusBackgroundColors = ['rgba(25, 135, 84, 0.8)','rgba(108, 99, 255, 0.8)','rgba(255, 193, 7, 0.8)','rgba(220, 53, 69, 0.8)','rgba(13, 202, 240, 0.8)'];
            const statusBorderColors = statusBackgroundColors.map(color => color.replace('0.8', '1'));
             new Chart(statusCtx, {
                 type: 'pie',
                 data: { labels: chartData.statusLabels, datasets: [{ label: ' Kayıt Sayısı', data: chartData.statusData, backgroundColor: statusBackgroundColors.slice(0, chartData.statusLabels.length), borderColor: statusBorderColors.slice(0, chartData.statusLabels.length), borderWidth: 2, hoverOffset: 10, hoverBorderColor: '#fff' }] }, // borderWidth, hoverOffset artırıldı
                 options: commonChartOptions
             });
         } catch (e) { console.error("Durum dağılım grafiği hatası:", e); }
    } else { /* ... hata mesajı ... */ }
});