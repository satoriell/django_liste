// tracker/static/tracker/js/dashboard_charts.js

document.addEventListener('DOMContentLoaded', function() {
    const chartDataElement = document.getElementById('chartDataJson');
    const typeChartCanvas = document.getElementById('typeDistributionChart');
    const statusChartCanvas = document.getElementById('statusDistributionChart');

    // Grafik instance'larını saklamak için değişkenler
    let typeChartInstance = null;
    let statusChartInstance = null;

    // Gerekli HTML elementleri veya veri yoksa fonksiyondan çık
    if (!chartDataElement || typeof Chart === 'undefined' || (!typeChartCanvas && !statusChartCanvas)) {
        if (typeof Chart === 'undefined') console.warn("Chart.js kütüphanesi yüklenemedi.");
        if (!chartDataElement) console.warn("Grafik veri elementi (#chartDataJson) bulunamadı.");
        if (!typeChartCanvas && !statusChartCanvas) console.warn("Grafik canvas elementleri bulunamadı.");
        return;
    }

    let chartData;
    try {
        chartData = JSON.parse(chartDataElement.textContent);
    } catch (e) {
        console.error("Grafik verisi JSON formatında ayrıştırılamadı:", e);
        return;
    }

    // --- Yardımcı Fonksiyon: CSS Değişkeninden Renk Alma ---
    function getCssVariableValue(variableName) {
        // Değişken adının başında '--' olduğundan emin ol
        const formattedVarName = variableName.startsWith('--') ? variableName : `--${variableName}`;
        // Değeri al ve boşlukları temizle
        return getComputedStyle(document.documentElement).getPropertyValue(formattedVarName).trim();
    }

    // --- Grafik Renklerini CSS Değişkenlerinden Alma Fonksiyonu ---
    function getChartColors() {
        // CSS'deki renk değişkenlerini oku (base.css ve dark_mode.css ile uyumlu olmalı)
        // Not: color-mix gibi karmaşık CSS fonksiyonları burada doğrudan okunamaz,
        // bu yüzden ana renkleri kullanıyoruz. Gerekirse renkleri JS içinde üretebiliriz.
        const primaryColor = getCssVariableValue('--primary-color') || '#6C63FF';
        const successColor = getCssVariableValue('--success-color') || '#198754';
        const dangerColor = getCssVariableValue('--danger-color') || '#dc3545';
        const infoColor = getCssVariableValue('--info-color') || '#0dcaf0';
        const warningColor = getCssVariableValue('--warning-color') || '#ffc107';
        // const secondaryColor = getCssVariableValue('--secondary-color') || '#6c757d';
        // const darkColor = getCssVariableValue('--dark-color') || '#212529'; // Açık temadaki --dark-color
        const bodyBg = getCssVariableValue('--body-bg-start') || '#f8f9fa'; // Arkaplan rengi (örn: border için)
        const headingColor = getCssVariableValue('--heading-color') || '#212529'; // Eksen/legend rengi
        const textColor = getCssVariableValue('--text-color') || '#495057'; // Eksen/legend rengi
        const borderColor = getCssVariableValue('--border-color') || '#dee2e6'; // Grid çizgileri

        return {
            typeColors: [
                primaryColor,   // Anime
                successColor,   // Webtoon
                dangerColor,    // Manga
                primaryColor    // Novel (Anime ile aynı veya farklı seçilebilir)
            ],
            statusColors: [
                successColor,   // Watching
                primaryColor,   // Completed
                warningColor,   // On Hold
                dangerColor,    // Dropped
                infoColor       // Plan to Watch
            ],
            commonBorderColor: bodyBg, // Dilimler arası veya çubuk kenarlığı için
            gridColor: borderColor, // Eksen çizgileri
            fontColor: textColor, // Eksen yazı renkleri
            legendFontColor: headingColor // Legend yazı rengi
        };
    }

    // --- Ortak Grafik Ayarları Fonksiyonu ---
    function getCommonChartOptions() {
        const colors = getChartColors(); // Mevcut tema renklerini al
        return {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        color: colors.legendFontColor, // Tema uyumlu renk
                        padding: 15,
                        boxWidth: 12,
                        font: { size: 11 }
                    }
                },
                tooltip: {
                    // Tooltip stilini CSS sınıfı ile yönetmek daha iyi olabilir,
                    // ancak şimdilik temel renkleri ayarlayalım
                    backgroundColor: 'rgba(0, 0, 0, 0.8)', // Genellikle koyu kalır
                    titleColor: '#ffffff',
                    bodyColor: '#ffffff',
                    titleFont: { weight: 'bold' },
                    bodyFont: { size: 12 },
                    padding: 10,
                    cornerRadius: 4,
                }
            },
            // Eksen renkleri
            scales: {
                 x: { // Sadece bar grafikte kullanılır
                    ticks: { color: colors.fontColor },
                    grid: { color: colors.gridColor }
                 },
                 y: { // Sadece bar grafikte kullanılır
                    ticks: { color: colors.fontColor },
                    grid: { color: colors.gridColor }
                 }
            }
        };
    }

    // --- Tür Dağılımı Grafiği (Doughnut) Oluşturma ---
    if (typeChartCanvas && chartData.typeLabels && chartData.typeCounts) {
        const ctx = typeChartCanvas.getContext('2d');
        const initialColors = getChartColors(); // Başlangıç renkleri
        const commonOptions = getCommonChartOptions(); // Başlangıç seçenekleri
        try {
            typeChartInstance = new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: chartData.typeLabels,
                    datasets: [{
                        label: 'Tür Dağılımı',
                        data: chartData.typeCounts,
                        backgroundColor: initialColors.typeColors,
                        borderColor: initialColors.commonBorderColor, // Temaya uygun kenarlık
                        borderWidth: 2,
                        hoverOffset: 8
                    }]
                },
                options: {
                    ...commonOptions, // Ortak ayarları devral
                     cutout: '60%',
                    plugins: { // Legend ve tooltip'i override et/ekle
                         ...commonOptions.plugins, // Ortak plugin ayarlarını devral
                        tooltip: {
                            ...commonOptions.plugins.tooltip,
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
        } catch (e) { console.error("Tür dağılımı grafiği oluşturulurken hata:", e); }
    }

    // --- Durum Dağılımı Grafiği (Bar) Oluşturma ---
    if (statusChartCanvas && chartData.statusLabels && chartData.statusData) {
        const ctx = statusChartCanvas.getContext('2d');
        const initialColors = getChartColors(); // Başlangıç renkleri
        const commonOptions = getCommonChartOptions(); // Başlangıç seçenekleri
        try {
            statusChartInstance = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: chartData.statusLabels,
                    datasets: [{
                        label: 'Sayı',
                        data: chartData.statusData,
                        backgroundColor: initialColors.statusColors,
                        borderColor: initialColors.statusColors, // Kenarlık aynı renk
                        borderWidth: 1,
                        borderRadius: 4,
                        barPercentage: 0.7,
                        categoryPercentage: 0.8
                    }]
                },
                options: {
                    ...commonOptions,
                    indexAxis: 'y', // Yatay çubuk grafik
                    scales: { // Eksen ayarlarını override et/ekle
                        x: {
                            ...commonOptions.scales.x, // Ortak renkleri al
                            beginAtZero: true,
                            ticks: {
                                ...commonOptions.scales.x.ticks, // Ortak rengi al
                                precision: 0
                             },
                            grid: {
                                ...commonOptions.scales.x.grid, // Ortak rengi al
                                // display: false // İsteğe bağlı: çizgileri gizle
                            }
                        },
                        y: {
                            ...commonOptions.scales.y, // Ortak renkleri al
                             grid: {
                                 ...commonOptions.scales.y.grid, // Ortak rengi al
                                display: false
                            }
                        }
                    },
                    plugins: {
                        ...commonOptions.plugins,
                         legend: { display: false } // Legend gereksiz
                        // Tooltip ortak ayarlardan gelir
                    }
                }
            });
        } catch (e) { console.error("Durum dağılımı grafiği oluşturulurken hata:", e); }
    }

    // --- Grafik Renklerini Güncelleme Fonksiyonu ---
    function updateChartColors() {
        if (!typeChartInstance && !statusChartInstance) return; // Güncellenecek grafik yoksa çık

        const newColors = getChartColors();
        const newOptions = getCommonChartOptions(); // Seçenekleri de güncelle (eksen renkleri vb.)

        // Tür Grafiğini Güncelle
        if (typeChartInstance) {
            const typeDataset = typeChartInstance.data.datasets[0];
            typeDataset.backgroundColor = newColors.typeColors;
            typeDataset.borderColor = newColors.commonBorderColor;
            // Legend ve eksen renkleri options ile güncellenir
            typeChartInstance.options.plugins.legend.labels.color = newOptions.plugins.legend.labels.color;
            // Doughnut'ta eksen yok
            typeChartInstance.update();
            // console.log("Tür grafiği renkleri güncellendi.");
        }

        // Durum Grafiğini Güncelle
        if (statusChartInstance) {
            const statusDataset = statusChartInstance.data.datasets[0];
            statusDataset.backgroundColor = newColors.statusColors;
            statusDataset.borderColor = newColors.statusColors;
            // Legend, eksen ve grid renkleri options ile güncellenir
            statusChartInstance.options.plugins.legend.labels.color = newOptions.plugins.legend.labels.color;
            statusChartInstance.options.scales.x.ticks.color = newOptions.scales.x.ticks.color;
            statusChartInstance.options.scales.x.grid.color = newOptions.scales.x.grid.color;
            statusChartInstance.options.scales.y.ticks.color = newOptions.scales.y.ticks.color;
            statusChartInstance.options.scales.y.grid.color = newOptions.scales.y.grid.color;
            statusChartInstance.update();
            // console.log("Durum grafiği renkleri güncellendi.");
        }
    }

    // --- Koyu Tema Değişikliğini Dinleme ---
    const htmlElement = document.documentElement;
    const observer = new MutationObserver(mutations => {
        mutations.forEach(mutation => {
            if (mutation.type === 'attributes' && mutation.attributeName === 'data-theme') {
                // Tema değişti, grafik renklerini güncelle
                 console.log("Tema değişti, grafikler güncelleniyor...");
                 // Kısa bir gecikme vermek CSS değişkenlerinin güncellenmesini garantileyebilir
                 setTimeout(updateChartColors, 50);
            }
        });
    });
    observer.observe(htmlElement, { attributes: true }); // data-theme değişikliğini izle

}); // DOMContentLoaded sonu