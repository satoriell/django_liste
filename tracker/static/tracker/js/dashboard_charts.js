// tracker/static/tracker/js/dashboard_charts.js

document.addEventListener('DOMContentLoaded', () => {
    const chartDataElement = document.getElementById('chartDataJson');
    let chartData = null;

    // Güvenlik kontrolü: chartDataElement gerçekten var mı?
    if (!chartDataElement) {
         console.error("HATA: JSON script elementi ('chartDataJson') dashboard.html'de bulunamadı!");
         return; // Element yoksa devam etme
    }

    try {
        chartData = JSON.parse(chartDataElement.textContent || "{}");
    } catch (e) {
        console.error("JSON verisi ayrıştırılamadı! Hata:", e);
        console.error("Hatalı JSON Script İçeriği:", chartDataElement.textContent);
        return; // Parse hatası varsa devam etme
    }

    // --- Tür Dağılım Grafiği ---
    const typeCtx = document.getElementById('typeDistributionChart')?.getContext('2d');
    if (typeCtx && chartData?.typeLabels && chartData?.typeCounts) {
         try {
             new Chart(typeCtx, {
                 type: 'doughnut',
                 data: {
                     labels: chartData.typeLabels,
                     datasets: [{
                         label: 'Kayıt Sayısı',
                         data: chartData.typeCounts,
                         backgroundColor: [
                             'rgba(54, 162, 235, 0.8)', // Anime (Mavi)
                             'rgba(75, 192, 192, 0.8)', // Webtoon (Yeşil)
                             'rgba(255, 99, 132, 0.8)', // Manga (Kırmızı)
                             'rgba(153, 102, 255, 0.8)' // Novel (Mor)
                            ],
                         borderColor: [
                             'rgba(54, 162, 235, 1)',
                             'rgba(75, 192, 192, 1)',
                             'rgba(255, 99, 132, 1)',
                             'rgba(153, 102, 255, 1)'
                            ],
                         borderWidth: 1,
                         hoverOffset: 4
                     }]
                 },
                 options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                         legend: {
                             position: 'bottom',
                         },
                         tooltip: { // Tooltip'leri özelleştir (opsiyonel)
                            callbacks: {
                                label: function(context) {
                                    let label = context.label || '';
                                    if (label) {
                                        label += ': ';
                                    }
                                    if (context.parsed !== null) {
                                        label += context.parsed;
                                    }
                                    return label;
                                }
                            }
                         }
                    }
                 }
             });
         } catch (e) { console.error("Tür grafiği hatası:", e); }
    } else { console.error("Tür grafiği için Canvas veya veri bulunamadı/hatalı."); }

    // --- Durum Dağılım Grafiği ---
    const statusCtx = document.getElementById('statusDistributionChart')?.getContext('2d');
    if (statusCtx && chartData?.statusLabels && chartData?.statusData) {
         try {
            const statusBackgroundColors = [
                'rgba(25, 135, 84, 0.8)',  // Watching (Yeşil)
                'rgba(13, 110, 253, 0.8)', // Completed (Mavi)
                'rgba(255, 193, 7, 0.8)',   // On Hold (Sarı)
                'rgba(220, 53, 69, 0.8)',  // Dropped (Kırmızı)
                'rgba(13, 202, 240, 0.8)', // Plan to Watch (Açık Mavi)
            ];
            const statusBorderColors = statusBackgroundColors.map(color => color.replace('0.8', '1'));
             new Chart(statusCtx, {
                 type: 'pie',
                 data: {
                     labels: chartData.statusLabels,
                     datasets: [{
                         label: ' Kayıt Sayısı',
                         data: chartData.statusData,
                         backgroundColor: statusBackgroundColors.slice(0, chartData.statusLabels.length),
                         borderColor: statusBorderColors.slice(0, chartData.statusLabels.length),
                         borderWidth: 1,
                         hoverOffset: 4
                     }]
                 },
                 options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                         legend: {
                             position: 'bottom',
                         },
                         tooltip: { // Tooltip'leri özelleştir (opsiyonel)
                            callbacks: {
                                label: function(context) {
                                    let label = context.label || '';
                                    if (label) {
                                        label += ': ';
                                    }
                                    if (context.parsed !== null) {
                                        label += context.parsed;
                                    }
                                    return label;
                                }
                            }
                         }
                     }
                 }
             });
         } catch (e) { console.error("Durum grafiği hatası:", e); }
    } else { console.error("Durum grafiği için Canvas veya veri bulunamadı/hatalı."); }
});