// tracker/static/tracker/js/dashboard_charts.js

document.addEventListener('DOMContentLoaded', function() {
    const chartDataElement = document.getElementById('chartDataJson');

    // Gerekli HTML elementleri veya veri yoksa fonksiyondan çık
    if (!chartDataElement || typeof Chart === 'undefined') {
        if (typeof Chart === 'undefined') {
            console.warn("Chart.js kütüphanesi yüklenemedi.");
        }
        if (!chartDataElement) {
            console.warn("Grafik veri elementi (#chartDataJson) bulunamadı.");
        }
        // Grafiğe ihtiyaç duymayan sayfalarda hata vermemesi için sessizce çık
        return;
    }

    let chartData;
    try {
        chartData = JSON.parse(chartDataElement.textContent);
    } catch (e) {
        console.error("Grafik verisi JSON formatında ayrıştırılamadı:", e);
        return; // Veri yoksa devam etme
    }

    // --- Grafik Renklerini Tanımla (Açık/Koyu Tema Uyumlu olabilir) ---
    // Bu renkleri CSS değişkenlerinden almak daha dinamik olurdu ama şimdilik sabit tanımlayalım
    // CSS değişkenlerini JS ile okumak: getComputedStyle(document.documentElement).getPropertyValue('--primary-color').trim();
    const primaryColor = '#6C63FF'; // Anime, Novel
    const successColor = '#198754'; // Webtoon
    const dangerColor = '#dc3545';  // Manga
    const infoColor = '#0dcaf0';   // Plan to Watch
    const warningColor = '#ffc107'; // On Hold
    const secondaryColor = '#6c757d'; // Dropped vb.
    const darkColor = '#212529'; // Completed (açık tema)

    const statusColors = [
        successColor, // Watching ('İzliyorum/Okuyorum') -> Yeşil
        primaryColor, // Completed ('Tamamladım') -> Mor (veya Mavi?)
        warningColor, // On Hold ('Beklemede') -> Sarı
        dangerColor,  // Dropped ('Bıraktım') -> Kırmızı
        infoColor,    // Plan to Watch ('İzleyeceğim/Okuyacağım') -> Açık Mavi
    ];

    const typeColors = [
        primaryColor,   // Anime
        successColor,   // Webtoon
        dangerColor,    // Manga
        primaryColor    // Novel (Anime ile aynı renk veya farklı bir renk seçilebilir, örn: secondaryColor)
    ];

    // --- Ortak Grafik Ayarları ---
    const commonChartOptions = {
        responsive: true, // Konteynere göre boyutlan
        maintainAspectRatio: false, // Yüksekliği konteyner belirlesin
        plugins: {
            legend: {
                position: 'bottom', // Göstergeyi alta al
                labels: {
                    // padding: 15,
                    boxWidth: 12,
                    font: {
                        size: 11 // Daha küçük font
                    }
                }
            },
            tooltip: {
                backgroundColor: 'rgba(0, 0, 0, 0.8)', // Tooltip arkaplanı (tema ile değişebilir)
                titleFont: { weight: 'bold' },
                bodyFont: { size: 12 },
                padding: 10,
                cornerRadius: 4,
                // callbacks: { // İsteğe bağlı: Tooltip içeriğini özelleştir
                //     label: function(context) {
                //         let label = context.label || '';
                //         if (label) {
                //             label += ': ';
                //         }
                //         if (context.parsed !== null) {
                //             label += context.parsed;
                //         }
                //         return label;
                //     }
                // }
            }
        }
    };

    // --- Tür Dağılımı Grafiği (Doughnut) ---
    const typeCtx = document.getElementById('typeDistributionChart')?.getContext('2d');
    if (typeCtx && chartData.typeLabels && chartData.typeCounts) {
        try {
            new Chart(typeCtx, {
                type: 'doughnut',
                data: {
                    labels: chartData.typeLabels,
                    datasets: [{
                        label: 'Tür Dağılımı',
                        data: chartData.typeCounts,
                        backgroundColor: typeColors,
                        borderColor: '#ffffff', // Dilimler arası beyaz çizgi (tema ile değişebilir)
                        borderWidth: 2,
                        hoverOffset: 8 // Üzerine gelince dilimi büyüt
                    }]
                },
                options: {
                    ...commonChartOptions, // Ortak ayarları devral
                     cutout: '60%', // Ortadaki boşluk oranı
                    plugins: { // Legend ve tooltip'i override et/ekle
                         ...commonChartOptions.plugins, // Ortak plugin ayarlarını devral
                        tooltip: {
                            ...commonChartOptions.plugins.tooltip,
                            callbacks: { // Yüzdeyi göster
                                label: function(context) {
                                    let label = context.label || '';
                                    let value = context.parsed || 0;
                                    let total = context.dataset.data.reduce((acc, val) => acc + val, 0);
                                    let percentage = total > 0 ? ((value / total) * 100).toFixed(1) + '%' : '0%';
                                    return `${label}: ${value} (${percentage})`;
                                }
                            }
                        }
                    }
                }
            });
        } catch (e) {
            console.error("Tür dağılımı grafiği oluşturulurken hata:", e);
        }
    } else if (document.getElementById('typeDistributionChart')) {
        console.warn("Tür dağılımı grafiği için canvas veya veri bulunamadı.");
    }


    // --- Durum Dağılımı Grafiği (Bar) ---
    const statusCtx = document.getElementById('statusDistributionChart')?.getContext('2d');
    if (statusCtx && chartData.statusLabels && chartData.statusData) {
       try {
            new Chart(statusCtx, {
                type: 'bar',
                data: {
                    labels: chartData.statusLabels,
                    datasets: [{
                        label: 'Sayı',
                        data: chartData.statusData,
                        backgroundColor: statusColors, // Her çubuk için farklı renk
                        borderColor: statusColors, // Kenarlık rengi aynı olsun
                        borderWidth: 1,
                        borderRadius: 4, // Köşeleri hafif yuvarlat
                        barPercentage: 0.7, // Çubuk genişliği
                        categoryPercentage: 0.8 // Kategori alanı genişliği
                    }]
                },
                options: {
                    ...commonChartOptions,
                    indexAxis: 'y', // Yatay çubuk grafik için 'y'
                    scales: {
                        x: { // Sayısal eksen (alt)
                            beginAtZero: true, // 0'dan başla
                            ticks: {
                                precision: 0 // Tam sayıları göster
                            },
                            grid: {
                                // display: false // Arka plan çizgilerini gizle (isteğe bağlı)
                                color: 'rgba(0, 0, 0, 0.05)' // Çizgi rengini soluklaştır (tema ile değişebilir)
                            }
                        },
                        y: { // Kategori ekseni (sol)
                             grid: {
                                display: false // Kategori çizgilerini gizle
                            }
                        }
                    },
                    plugins: {
                        ...commonChartOptions.plugins,
                         legend: {
                            display: false // Tek dataset olduğu için gösterge gereksiz
                        }
                        // Tooltip ayarları ortak ayarlardan gelir
                    }
                }
            });
       } catch (e) {
            console.error("Durum dağılımı grafiği oluşturulurken hata:", e);
       }
    } else if (document.getElementById('statusDistributionChart')) {
        console.warn("Durum dağılımı grafiği için canvas veya veri bulunamadı.");
    }

    // --- Koyu Tema Değişikliğini Dinleme (Opsiyonel - Grafik Renklerini Güncelleme) ---
    // Eğer tema değişiminde grafik renklerinin de değişmesini isterseniz:
    // const htmlElement = document.documentElement;
    // const observer = new MutationObserver(mutations => {
    //     mutations.forEach(mutation => {
    //         if (mutation.type === 'attributes' && mutation.attributeName === 'data-theme') {
    //             // Tema değişti, grafik renklerini güncelle ve yeniden çiz
    //             // updateChartColorsAndRedraw(typeChartInstance, statusChartInstance);
    //             console.log("Tema değişti, grafikler güncellenmeli (fonksiyon implemente edilmedi).");
    //         }
    //     });
    // });
    // observer.observe(htmlElement, { attributes: true });
    // function updateChartColorsAndRedraw(typeChart, statusChart) {
         // CSS değişkenlerinden yeni renkleri al
         // const newPrimaryColor = getComputedStyle(document.documentElement).getPropertyValue('--primary-color').trim();
         // ... diğer renkler ...
         // Chart instance'larının data.datasets[...].backgroundColor vb. güncelle
         // typeChart.data.datasets[0].backgroundColor = [...];
         // statusChart.data.datasets[0].backgroundColor = [...];
         // typeChart.update();
         // statusChart.update();
    // }

}); // DOMContentLoaded sonu