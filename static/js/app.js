/**
 * TrenKuliner.id - Frontend Dashboard Engine
 * Handles user input, API requests, chart rendering, and advice population.
 */

document.addEventListener("DOMContentLoaded", () => {
    // DOM Elements
    const form = document.getElementById("analyze-form");
    const keywordInput = document.getElementById("keyword-input");
    const geoSelect = document.getElementById("geo-select");
    const timeframeSelect = document.getElementById("timeframe-select");
    
    const btnSubmit = document.getElementById("btn-submit");
    const btnText = document.getElementById("btn-text");
    const btnIcon = document.getElementById("btn-icon");
    const btnSpinner = document.getElementById("btn-spinner");
    
    const warningBanner = document.getElementById("warning-banner");
    const warningText = document.getElementById("warning-text");
    
    const chartTimeLabel = document.getElementById("chart-time-label");
    const dataSourceBadge = document.getElementById("data-source-badge");
    const apiSourceInfo = document.getElementById("api-source-info");
    
    // Table Elements
    const topQueriesTable = document.getElementById("top-queries-table");
    const topQueriesEmpty = document.getElementById("top-queries-empty");
    const risingQueriesTable = document.getElementById("rising-queries-table");
    const risingQueriesEmpty = document.getElementById("rising-queries-empty");
    
    // Region Elements
    const regionCardWrapper = document.getElementById("region-card-wrapper");
    const regionList = document.getElementById("region-list");
    const regionEmpty = document.getElementById("region-empty");
    
    // Consultant Elements
    const trendStatusBadge = document.getElementById("trend-status-badge");
    const consultantSummary = document.getElementById("consultant-summary");
    const consultantRegional = document.getElementById("consultant-regional");
    const consultantRecs = document.getElementById("consultant-recs");

    // Global Chart Instance
    let interestChart = null;

    // Initialize Lucide Icons
    lucide.createIcons();

    // Form Submit Event
    form.addEventListener("submit", (e) => {
        e.preventDefault();
        performAnalysis();
    });

    /**
     * Set loading state
     */
    function setLoading(isLoading) {
        if (isLoading) {
            btnSubmit.disabled = true;
            btnText.textContent = "Menganalisis...";
            btnIcon.style.display = "none";
            btnSpinner.style.display = "block";
            
            // Add slight opacity to panels
            document.querySelectorAll(".dashboard-grid .card").forEach(card => {
                card.style.opacity = "0.75";
            });
        } else {
            btnSubmit.disabled = false;
            btnText.textContent = "Analisis Tren";
            btnIcon.style.display = "block";
            btnSpinner.style.display = "none";
            
            document.querySelectorAll(".dashboard-grid .card").forEach(card => {
                card.style.opacity = "1";
            });
        }
    }

    /**
     * Map timeframe code to descriptive text
     */
    function getTimeframeText(timeframeCode) {
        const mapping = {
            "today 12-m": "12 Bulan Terakhir",
            "today 3-m": "3 Bulan Terakhir",
            "today 1-m": "30 Hari Terakhir",
            "now 7-d": "7 Hari Terakhir"
        };
        return mapping[timeframeCode] || timeframeCode;
    }

    /**
     * Call the backend API to fetch and render trend analysis
     */
    async function performAnalysis() {
        const keyword = keywordInput.value.trim();
        const geo = geoSelect.value;
        const timeframe = timeframeSelect.value;

        if (!keyword) return;

        setLoading(true);
        chartTimeLabel.textContent = getTimeframeText(timeframe);

        try {
            const response = await fetch(`/api/analyze?keyword=${encodeURIComponent(keyword)}&geo=${geo}&timeframe=${timeframe}`);
            if (!response.ok) {
                throw new Error("Gagal mengambil data tren dari server.");
            }
            
            const data = await response.json();
            renderDashboard(data, keyword, geo);
        } catch (error) {
            console.error("Analysis error:", error);
            alert("Terjadi kesalahan sistem saat menganalisis tren. Silakan coba sesaat lagi.");
        } finally {
            setLoading(false);
        }
    }

    /**
     * Populate dashboard elements with fetched data
     */
    function renderDashboard(data, keyword, geo) {
        // 1. Source Badges & Warnings
        if (data.warning) {
            dataSourceBadge.textContent = "Simulated Fallback Mode";
            dataSourceBadge.style.color = "#ef4444";
            apiSourceInfo.innerHTML = `<strong>Pemberitahuan:</strong> ${data.warning} | ${data.source}`;
        } else {
            dataSourceBadge.textContent = "Terhubung ke Live Google Trends";
            dataSourceBadge.style.color = "#10b981";
            apiSourceInfo.textContent = `Sumber Data: ${data.source}`;
        }

        // Show/Hide Warning Alert Banner (downward trend warning)
        if (data.advice && data.advice.warning_alert) {
            warningBanner.style.display = "flex";
            warningText.innerHTML = `Tren pencarian <strong>"${keyword}"</strong> sedang mengalami penurunan tajam. Disarankan untuk berhati-hati dan tidak memusatkan seluruh modal bisnis pada produk ini.`;
        } else {
            warningBanner.style.display = "none";
        }

        // 2. Render Chart (Interest Over Time)
        renderChart(data.time_data, keyword);

        // 3. Render Tables (Top & Rising Queries)
        renderTables(data.top_queries, data.rising_queries);

        // 4. Render Region progress bars (only if geo is 'ID')
        renderRegions(data.region_data, geo);

        // 5. Render AI Consultant insights
        renderConsultant(data.advice, keyword);
    }

    /**
     * Initialize/Update ChartJS line graph
     */
    function renderChart(timeData, keyword) {
        const ctx = document.getElementById("interestChart").getContext("2d");
        
        if (!timeData || timeData.length === 0) {
            ctx.clearRect(0, 0, 400, 400);
            return;
        }

        const labels = timeData.map(d => {
            // Format date format slightly nicer depending on length
            if (d.date.length === 10) {
                // YYYY-MM-DD -> convert to readable Day Month
                const parts = d.date.split('-');
                return `${parts[2]}/${parts[1]}`;
            }
            return d.date;
        });
        const values = timeData.map(d => d.value);

        // Destroy previous chart to avoid hover overlay bug
        if (interestChart) {
            interestChart.destroy();
        }

        // Blue-Cyan Gradient fill
        const gradient = ctx.createLinearGradient(0, 0, 0, 300);
        gradient.addColorStop(0, 'rgba(14, 165, 233, 0.3)');
        gradient.addColorStop(1, 'rgba(14, 165, 233, 0.0)');

        interestChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: `Minat Penelusuran "${keyword}"`,
                    data: values,
                    borderColor: '#0ea5e9', // Electric blue arrow
                    borderWidth: 3,
                    backgroundColor: gradient,
                    fill: true,
                    tension: 0.35,
                    pointBackgroundColor: '#ecc94b', // Gold bars
                    pointBorderColor: '#0a0b10',
                    pointBorderWidth: 2,
                    pointRadius: 4,
                    pointHoverRadius: 6,
                    pointHoverBackgroundColor: '#f59e0b',
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        backgroundColor: '#161825',
                        titleColor: '#f3f4f6',
                        bodyColor: '#f3f4f6',
                        borderColor: 'rgba(255,255,255,0.08)',
                        borderWidth: 1,
                        padding: 10,
                        displayColors: false,
                        callbacks: {
                            label: function(context) {
                                return `Tingkat Minat: ${context.parsed.y}`;
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        grid: {
                            color: 'rgba(255, 255, 255, 0.05)',
                        },
                        ticks: {
                            color: '#9ca3af',
                            font: {
                                family: 'Plus Jakarta Sans',
                                size: 11
                            }
                        },
                        min: 0,
                        max: 100
                    },
                    x: {
                        grid: {
                            display: false
                        },
                        ticks: {
                            color: '#9ca3af',
                            font: {
                                family: 'Plus Jakarta Sans',
                                size: 10
                            },
                            maxTicksLimit: 12
                        }
                    }
                }
            }
        });
    }

    /**
     * Populates the Top and Rising Related Queries tables
     */
    function renderTables(topQueries, risingQueries) {
        const topBody = topQueriesTable.querySelector("tbody");
        const risingBody = risingQueriesTable.querySelector("tbody");
        
        // Clear previous entries
        topBody.innerHTML = "";
        risingBody.innerHTML = "";

        // Render Top Queries
        if (topQueries && topQueries.length > 0) {
            topQueriesTable.style.display = "table";
            topQueriesEmpty.style.display = "none";
            
            topQueries.forEach(item => {
                const tr = document.createElement("tr");
                tr.innerHTML = `
                    <td>${item.query}</td>
                    <td class="table-score score-high">${item.value}</td>
                `;
                topBody.appendChild(tr);
            });
        } else {
            topQueriesTable.style.display = "none";
            topQueriesEmpty.style.display = "block";
        }

        // Render Rising Queries
        if (risingQueries && risingQueries.length > 0) {
            risingQueriesTable.style.display = "table";
            risingQueriesEmpty.style.display = "none";
            
            risingQueries.forEach(item => {
                const tr = document.createElement("tr");
                // Check if value indicates breakout (+200% or standard breakout value representation)
                let badgeHtml = "";
                if (item.value >= 200) {
                    badgeHtml = `<span class="score-breakout">Breakout</span>`;
                } else {
                    badgeHtml = `<span class="table-score" style="color: #34d399;">+${item.value}%</span>`;
                }
                
                tr.innerHTML = `
                    <td>${item.query}</td>
                    <td class="table-score">${badgeHtml}</td>
                `;
                risingBody.appendChild(tr);
            });
        } else {
            risingQueriesTable.style.display = "none";
            risingQueriesEmpty.style.display = "block";
        }
    }

    /**
     * Render regional metrics (progress bars for provinces)
     */
    function renderRegions(regionData, geo) {
        regionList.innerHTML = "";
        
        // Sub-national queries do not return regional lists
        if (geo !== 'ID' || !regionData || regionData.length === 0) {
            regionList.style.display = "none";
            regionEmpty.style.display = "block";
            return;
        }

        regionList.style.display = "flex";
        regionEmpty.style.display = "none";

        regionData.forEach(item => {
            const div = document.createElement("div");
            div.className = "region-item animate-fade-in";
            div.innerHTML = `
                <div class="region-info">
                    <span class="region-name">${item.region}</span>
                    <span class="region-value">${item.value}</span>
                </div>
                <div class="region-bar-track">
                    <div class="region-bar-fill" id="bar-${item.region.replace(/\s+/g, '-')}"></div>
                </div>
            `;
            regionList.appendChild(div);
            
            // Trigger animation on progress bar width
            setTimeout(() => {
                const bar = document.getElementById(`bar-${item.region.replace(/\s+/g, '-')}`);
                if (bar) {
                    bar.style.width = `${item.value}%`;
                }
            }, 100);
        });
    }

    /**
     * Renders advice column and populates all 4 consultant tabs
     */
    function renderConsultant(advice, keyword) {
        if (!advice) return;

        // Status Badge Style
        trendStatusBadge.textContent = advice.status;
        trendStatusBadge.className = "status-badge"; // reset classes
        trendStatusBadge.classList.add(advice.status.toLowerCase());

        // Fill descriptions
        consultantSummary.textContent = advice.summary;
        consultantRegional.innerHTML = advice.regional_insight;

        // Tab 1: Recommendations List (Aksi)
        consultantRecs.innerHTML = "";
        advice.recommendations.forEach(rec => {
            const li = document.createElement("li");
            li.innerHTML = rec;
            consultantRecs.appendChild(li);
        });

        // Tab 2: Business Strategy (Bisnis)
        const businessList = document.getElementById("consultant-business");
        if (businessList) {
            businessList.innerHTML = "";
            if (advice.business_strategy && advice.business_strategy.length > 0) {
                advice.business_strategy.forEach(item => {
                    const li = document.createElement("li");
                    li.innerHTML = item;
                    businessList.appendChild(li);
                });
            } else {
                businessList.innerHTML = '<li class="empty-advice">Masukkan kata kunci dan analisis tren untuk mendapatkan strategi bisnis.</li>';
            }
        }

        // Tab 3: Content Ideas (Konten)
        const contentList = document.getElementById("consultant-content");
        if (contentList) {
            contentList.innerHTML = "";
            if (advice.content_ideas && advice.content_ideas.length > 0) {
                advice.content_ideas.forEach(item => {
                    const li = document.createElement("li");
                    li.innerHTML = item;
                    contentList.appendChild(li);
                });
            } else {
                contentList.innerHTML = '<li class="empty-advice">Masukkan kata kunci dan analisis tren untuk mendapatkan ide konten.</li>';
            }
        }

        // Tab 4: Marketing Strategy (Marketing)
        const marketingList = document.getElementById("consultant-marketing");
        if (marketingList) {
            marketingList.innerHTML = "";
            if (advice.marketing_strategy && advice.marketing_strategy.length > 0) {
                advice.marketing_strategy.forEach(item => {
                    const li = document.createElement("li");
                    li.innerHTML = item;
                    marketingList.appendChild(li);
                });
            } else {
                marketingList.innerHTML = '<li class="empty-advice">Masukkan kata kunci dan analisis tren untuk mendapatkan strategi marketing.</li>';
            }
        }

        // Re-initialize Lucide icons for any new content
        lucide.createIcons();
    }

    /**
     * Initialize interactive tab switching for the Consultant card
     */
    function initTabs() {
        const tabButtons = document.querySelectorAll(".tab-btn");
        const tabContents = document.querySelectorAll(".tab-content");

        tabButtons.forEach(btn => {
            btn.addEventListener("click", () => {
                const targetTabId = btn.getAttribute("data-tab");

                // Remove active from all buttons and content panes
                tabButtons.forEach(b => b.classList.remove("active"));
                tabContents.forEach(tc => tc.classList.remove("active"));

                // Activate clicked button and corresponding content
                btn.classList.add("active");
                const targetPane = document.getElementById(targetTabId);
                if (targetPane) {
                    targetPane.classList.add("active");

                    // Add a subtle entrance animation
                    targetPane.style.animation = "none";
                    targetPane.offsetHeight; // trigger reflow
                    targetPane.style.animation = "fadeInTab 0.35s ease forwards";
                }
            });
        });
    }

    // Initialize tabs on load
    initTabs();

    // Trigger initial analysis automatically on load
    performAnalysis();
});

