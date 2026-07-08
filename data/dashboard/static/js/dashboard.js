/**
 * 5000 Dashboard — Chart.js visualization
 * Auto-refresh every 30 seconds via page-level interval.
 */

const API_BASE = '/api';
let charts = {};

async function fetchJSON(url) {
    const resp = await fetch(url);
    if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`);
    return resp.json();
}

// ── Chart Helper Functions ──

function destroyChart(name) {
    if (charts[name]) {
        charts[name].destroy();
        delete charts[name];
    }
}

function createLineChart(canvasId, labels, datasets, options = {}) {
    const ctx = document.getElementById(canvasId)?.getContext('2d');
    if (!ctx) return null;

    destroyChart(canvasId);

    const defaultOptions = {
        responsive: true,
        plugins: { legend: { labels: { color: '#adb5bd', boxWidth: 12 } } },
        scales: {
            x: { ticks: { maxTicksLimit: 10, color: '#adb5bd' } },
            y: { beginAtZero: true, ticks: { color: '#adb5bd' } }
        }
    };

    charts[canvasId] = new Chart(ctx, {
        type: 'line',
        data: { labels, datasets },
        options: { ...defaultOptions, ...options }
    });
    return charts[canvasId];
}

function createBarChart(canvasId, labels, data, options = {}) {
    const ctx = document.getElementById(canvasId)?.getContext('2d');
    if (!ctx) return null;

    destroyChart(canvasId);

    const defaultOptions = {
        indexAxis: 'y',
        responsive: true,
        plugins: { legend: { display: false } },
        scales: {
            x: { beginAtZero: true, ticks: { color: '#adb5bd' } },
            y: { ticks: { color: '#adb5bd', font: { size: 10 } } }
        }
    };

    charts[canvasId] = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: options.label || 'Value',
                data: data,
                backgroundColor: options.backgroundColor || 'rgba(13,110,253,0.7)',
                borderColor: options.borderColor || '#0d6efd',
                borderWidth: 1,
            }]
        },
        options: { ...defaultOptions, ...options }
    });
    return charts[canvasId];
}

function createDualLineChart(canvasId, labels, datasets, options = {}) {
    const ctx = document.getElementById(canvasId)?.getContext('2d');
    if (!ctx) return null;

    destroyChart(canvasId);

    const defaultOptions = {
        responsive: true,
        plugins: { legend: { labels: { color: '#adb5bd', boxWidth: 12 } } },
        scales: {
            x: { ticks: { maxTicksLimit: 10, color: '#adb5bd' } },
            y: { beginAtZero: true, position: 'left', ticks: { color: '#adb5bd' } },
            y1: { beginAtZero: true, position: 'right', grid: { display: false }, ticks: { color: '#adb5bd' } }
        }
    };

    charts[canvasId] = new Chart(ctx, {
        type: 'line',
        data: { labels, datasets },
        options: { ...defaultOptions, ...options }
    });
    return charts[canvasId];
}

// ── Stat Cards ──

async function loadSummary() {
    try {
        const data = await fetchJSON(`${API_BASE}/summary`);
        document.getElementById('statTotalPosts').textContent =
            data.total_posts?.toLocaleString() ?? '—';
        document.getElementById('statTodayPosts').textContent =
            data.today_posts?.toLocaleString() ?? '—';
        document.getElementById('statRevenue').textContent =
            data.month_revenue != null ? '$' + data.month_revenue.toLocaleString() : '—';
        document.getElementById('statSessions').textContent =
            data.month_sessions?.toLocaleString() ?? '—';
    } catch (e) {
        console.error('Failed to load summary:', e);
    }
}

// ── Posts Trend Chart ──

async function loadPostsChart() {
    const group = document.getElementById('postsGroup')?.value || 'daily';
    const endpoint = group === 'weekly' ? '/posts/weekly?weeks=12' : '/posts/daily?days=30';

    try {
        const rows = await fetchJSON(`${API_BASE}${endpoint}`);

        const map = {};
        for (const r of rows) {
            const key = r.date || r.week;
            map[key] = (map[key] || 0) + r.count;
        }
        const labels = Object.keys(map).sort();
        const values = labels.map(k => map[k]);

        createLineChart('postsChart', labels, [{
            label: 'Posts',
            data: values,
            borderColor: '#0d6efd',
            backgroundColor: 'rgba(13,110,253,0.1)',
            fill: true,
            tension: 0.3,
        }], {
            plugins: { legend: { display: false } },
            scales: {
                x: { ticks: { maxTicksLimit: 15, color: '#adb5bd' } },
                y: { beginAtZero: true, ticks: { color: '#adb5bd' } }
            }
        });
    } catch (e) {
        console.error('Failed to load posts chart:', e);
    }
}

// ── Revenue Trend Chart ──

async function loadRevenueChart() {
    try {
        const rows = await fetchJSON(`${API_BASE}/revenue/daily?days=30`);
        const labels = rows.map(r => r.date);
        const revenue = rows.map(r => r.revenue);
        const rpm = rows.map(r => r.rpm);

        createDualLineChart('revenueChart', labels, [
            {
                label: 'Revenue ($)',
                data: revenue,
                borderColor: '#ffc107',
                backgroundColor: 'rgba(255,193,7,0.1)',
                fill: true,
                tension: 0.3,
                yAxisID: 'y',
            },
            {
                label: 'RPM ($)',
                data: rpm,
                borderColor: '#dc3545',
                borderDash: [5, 5],
                fill: false,
                tension: 0.3,
                yAxisID: 'y1',
            }
        ]);
    } catch (e) {
        console.error('Failed to load revenue chart:', e);
    }
}

// ── Top Blogs Bar Chart ──

async function loadTopPosts() {
    try {
        const rows = await fetchJSON(`${API_BASE}/posts/total`);
        const top = rows.slice(0, 15).reverse();

        createBarChart('topPostsChart', top.map(r => r.blog_id), top.map(r => r.count), {
            label: 'Total Posts',
            backgroundColor: 'rgba(13,110,253,0.7)',
            borderColor: '#0d6efd',
        });
    } catch (e) {
        console.error('Failed to load top posts:', e);
    }
}

// ── Health Grid ──

let healthFilter = localStorage.getItem('healthFilter') || 'all';
let healthSort = localStorage.getItem('healthSort') || 'status';

async function loadHealth() {
    try {
        const data = await fetchJSON(`${API_BASE}/health`);
        const grid = document.getElementById('healthGrid');
        if (!grid) return;

        let sites = data.sites || [];
        
        if (healthFilter === 'online') {
            sites = sites.filter(s => s.status === 200);
        } else if (healthFilter === 'offline') {
            sites = sites.filter(s => s.status !== 200);
        }

        if (healthSort === 'response') {
            sites.sort((a, b) => (a.response_ms || 0) - (b.response_ms || 0));
        } else if (healthSort === 'blog_id') {
            sites.sort((a, b) => a.blog_id.localeCompare(b.blog_id));
        }

        const online = data.sites.filter(s => s.status === 200).length;
        const offline = data.sites.filter(s => s.status !== 200).length;

        let html = `<div class="mb-2 small">
            <span class="text-success">● ${online} online</span>
            <span class="text-danger ms-3">● ${offline} offline</span>
            <span class="text-muted ms-3">${data.total} total</span>
        </div><div class="d-flex flex-wrap gap-1">`;

        for (const site of sites) {
            const cls = site.status === 200 ? 'bg-success' :
                        site.status === 0 ? 'bg-danger' : 'bg-warning';
            html += `<span class="${cls} rounded" style="width:12px;height:12px;"
                      title="${site.blog_id}: ${site.status} (${site.response_ms}ms)"></span>`;
        }
        html += '</div>';
        grid.innerHTML = html;
    } catch (e) {
        console.error('Failed to load health:', e);
    }
}

function setHealthFilter(filter) {
    healthFilter = filter;
    localStorage.setItem('healthFilter', filter);
    loadHealth();
}

function setHealthSort(sort) {
    healthSort = sort;
    localStorage.setItem('healthSort', sort);
    loadHealth();
}

// ── Page-specific Loaders ──

function loadRevenuePage() {
    loadRevenueChart();
    loadRevenueByDomain();
    loadRpmTrend();
    loadWeeklyComparison();
}

async function loadRevenueByDomain() {
    try {
        const rows = await fetchJSON(`${API_BASE}/revenue/by-domain?days=30`);
        const top = rows.slice(0, 15).reverse();

        createBarChart('revenueDomainChart', top.map(r => r.domain), top.map(r => r.revenue), {
            label: 'Revenue ($)',
            backgroundColor: 'rgba(255,193,7,0.7)',
            borderColor: '#ffc107',
        });
    } catch (e) {
        console.error('Failed to load revenue by domain:', e);
    }
}

async function loadRpmTrend() {
    try {
        const rows = await fetchJSON(`${API_BASE}/revenue/rpm?days=90`);

        createDualLineChart('rpmTrendChart', rows.map(r => r.date), [
            {
                label: 'RPM ($)',
                data: rows.map(r => r.rpm),
                borderColor: '#0dcaf0',
                tension: 0.3,
            },
            {
                label: 'CTR',
                data: rows.map(r => r.ctr * 100),
                borderColor: '#6f42c1',
                borderDash: [5, 5],
                tension: 0.3,
                yAxisID: 'y1',
            }
        ], {
            scales: {
                x: { ticks: { maxTicksLimit: 12, color: '#adb5bd' } },
                y: { beginAtZero: true, ticks: { color: '#adb5bd' } },
                y1: { beginAtZero: true, position: 'right', grid: { display: false }, ticks: { color: '#adb5bd', callback: v => v.toFixed(2) + '%' } }
            }
        });
    } catch (e) {
        console.error('Failed to load RPM trend:', e);
    }
}

async function loadWeeklyComparison() {
    try {
        const rows = await fetchJSON(`${API_BASE}/revenue/daily?days=14`);
        
        const thisWeek = rows.slice(-7);
        const lastWeek = rows.slice(0, 7);
        
        const thisWeekRevenue = thisWeek.reduce((sum, r) => sum + (r.revenue || 0), 0);
        const lastWeekRevenue = lastWeek.reduce((sum, r) => sum + (r.revenue || 0), 0);
        const thisWeekRpm = thisWeek.length ? thisWeek.reduce((sum, r) => sum + (r.rpm || 0), 0) / thisWeek.length : 0;
        const lastWeekRpm = lastWeek.length ? lastWeek.reduce((sum, r) => sum + (r.rpm || 0), 0) / lastWeek.length : 0;

        const ctx = document.getElementById('weeklyComparisonChart')?.getContext('2d');
        if (!ctx) return;

        destroyChart('weeklyComparison');

        charts.weeklyComparison = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: ['Revenue ($)', 'RPM ($)'],
                datasets: [
                    {
                        label: 'This Week',
                        data: [thisWeekRevenue, thisWeekRpm],
                        backgroundColor: 'rgba(13,110,253,0.7)',
                    },
                    {
                        label: 'Last Week',
                        data: [lastWeekRevenue, lastWeekRpm],
                        backgroundColor: 'rgba(108,117,125,0.5)',
                    }
                ]
            },
            options: {
                responsive: true,
                plugins: { legend: { labels: { color: '#adb5bd' } } },
                scales: {
                    x: { ticks: { color: '#adb5bd' } },
                    y: { beginAtZero: true, ticks: { color: '#adb5bd' } }
                }
            }
        });
    } catch (e) {
        console.error('Failed to load weekly comparison:', e);
    }
}

function loadTrafficPage() {
    loadTrafficChart();
    loadTrafficByBlog();
    loadAdRevenueTrafficScatter();
}

async function loadTrafficChart() {
    try {
        const rows = await fetchJSON(`${API_BASE}/traffic/daily?days=30`);

        createLineChart('trafficChart', rows.map(r => r.date), [
            {
                label: 'Sessions',
                data: rows.map(r => r.sessions),
                borderColor: '#0d6efd',
                tension: 0.3,
            },
            {
                label: 'Users',
                data: rows.map(r => r.users),
                borderColor: '#198754',
                tension: 0.3,
            },
            {
                label: 'Page Views',
                data: rows.map(r => r.page_views),
                borderColor: '#ffc107',
                borderDash: [5, 5],
                tension: 0.3,
            }
        ]);
    } catch (e) {
        console.error('Failed to load traffic chart:', e);
    }
}

async function loadTrafficByBlog() {
    try {
        const rows = await fetchJSON(`${API_BASE}/traffic/by-blog?days=30`);
        const top = rows.slice(0, 15).reverse();

        createBarChart('trafficBlogChart', top.map(r => r.blog_id), top.map(r => r.sessions), {
            label: 'Sessions',
        });
    } catch (e) {
        console.error('Failed to load traffic by blog:', e);
    }
}

async function loadAdRevenueTrafficScatter() {
    try {
        const [trafficRows, revenueRows] = await Promise.all([
            fetchJSON(`${API_BASE}/traffic/daily?days=30`),
            fetchJSON(`${API_BASE}/revenue/daily?days=30`)
        ]);

        const revenueMap = new Map(revenueRows.map(r => [r.date, r]));
        const data = trafficRows.map(t => {
            const r = revenueMap.get(t.date) || {};
            return {
                x: t.sessions || 0,
                y: r.revenue || 0,
                r: Math.min(Math.sqrt((t.page_views || 0) / 100), 20)
            };
        }).filter(d => d.x > 0 || d.y > 0);

        const ctx = document.getElementById('adRevenueScatterChart')?.getContext('2d');
        if (!ctx) return;

        destroyChart('adRevenueScatter');

        charts.adRevenueScatter = new Chart(ctx, {
            type: 'scatter',
            data: {
                datasets: [{
                    label: 'Sessions vs Revenue',
                    data: data,
                    backgroundColor: 'rgba(13,110,253,0.6)',
                    borderColor: '#0d6efd',
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => {
                                const d = ctx.raw;
                                return `Sessions: ${d.x.toLocaleString()}, Revenue: $${d.y.toFixed(2)}`;
                            }
                        }
                    }
                },
                scales: {
                    x: { title: { display: true, text: 'Sessions', color: '#adb5bd' }, ticks: { color: '#adb5bd' } },
                    y: { title: { display: true, text: 'Revenue ($)', color: '#adb5bd' }, ticks: { color: '#adb5bd' } }
                }
            }
        });
    } catch (e) {
        console.error('Failed to load ad revenue scatter:', e);
    }
}

function loadSearchPage() {
    loadGscChart();
    loadBingChart();
    loadEfficiencyChart();
    loadGscBingComparison();
}

async function loadGscChart() {
    try {
        const rows = await fetchJSON(`${API_BASE}/search/gsc/daily?days=30`);

        createDualLineChart('gscChart', rows.map(r => r.date), [
            {
                label: 'Clicks',
                data: rows.map(r => r.clicks),
                borderColor: '#198754',
                tension: 0.3,
                yAxisID: 'y',
            },
            {
                label: 'Impressions',
                data: rows.map(r => r.impressions),
                borderColor: '#0d6efd',
                tension: 0.3,
                yAxisID: 'y1',
            },
            {
                label: 'Position (inv)',
                data: rows.map(r => 11 - r.position),
                borderColor: '#dc3545',
                borderDash: [3, 3],
                tension: 0.3,
                yAxisID: 'y2',
            }
        ], {
            scales: {
                x: { ticks: { maxTicksLimit: 10, color: '#adb5bd' } },
                y: { beginAtZero: true, position: 'left', ticks: { color: '#adb5bd' } },
                y1: { beginAtZero: true, position: 'right', grid: { display: false }, ticks: { color: '#adb5bd' } },
                y2: { display: false }
            }
        });
    } catch (e) {
        console.error('Failed to load GSC chart:', e);
    }
}

async function loadBingChart() {
    try {
        const rows = await fetchJSON(`${API_BASE}/search/bing/daily?days=30`);

        createDualLineChart('bingChart', rows.map(r => r.date), [
            {
                label: 'Bing Clicks',
                data: rows.map(r => r.clicks),
                borderColor: '#0d6efd',
                tension: 0.3,
            },
            {
                label: 'Bing Impressions',
                data: rows.map(r => r.impressions),
                borderColor: '#6f42c1',
                borderDash: [5, 5],
                tension: 0.3,
            }
        ]);
    } catch (e) {
        console.error('Failed to load Bing chart:', e);
    }
}

async function loadEfficiencyChart() {
    try {
        const rows = await fetchJSON(`${API_BASE}/search/efficiency?days=30`);
        const top = rows.slice(0, 20).reverse();

        createBarChart('efficiencyChart', top.map(r => r.blog_id), top.map(r => r.efficiency), {
            label: 'Efficiency Score',
            backgroundColor: top.map(r =>
                r.efficiency > 80 ? 'rgba(25,135,84,0.7)' :
                r.efficiency > 50 ? 'rgba(255,193,7,0.7)' :
                'rgba(220,53,69,0.7)'),
        });
    } catch (e) {
        console.error('Failed to load efficiency chart:', e);
    }
}

async function loadGscBingComparison() {
    try {
        const [gscRows, bingRows] = await Promise.all([
            fetchJSON(`${API_BASE}/search/gsc/daily?days=30`),
            fetchJSON(`${API_BASE}/search/bing/daily?days=30`)
        ]);

        const bingMap = new Map(bingRows.map(r => [r.date, r]));
        const dates = gscRows.map(r => r.date);
        const gscClicks = gscRows.map(r => r.clicks || 0);
        const bingClicks = dates.map(d => bingMap.get(d)?.clicks || 0);

        createBarChart('gscBingComparisonChart', dates, [
            { label: 'GSC', data: gscClicks, backgroundColor: 'rgba(13,110,253,0.7)' },
            { label: 'Bing', data: bingClicks, backgroundColor: 'rgba(111,66,193,0.7)' }
        ], {
            indexAxis: 'x',
            plugins: { legend: { labels: { color: '#adb5bd' } } },
            scales: {
                x: { ticks: { color: '#adb5bd', maxTicksLimit: 10 } },
                y: { beginAtZero: true, ticks: { color: '#adb5bd' } }
            }
        });
    } catch (e) {
        console.error('Failed to load GSC vs Bing comparison:', e);
    }
}

async function loadQualityPage() {
    try {
        const summary = await fetchJSON(`${API_BASE}/quality/summary`);
        document.getElementById('avgReadability').textContent = (summary.avg_readability || 0).toFixed(3);
        document.getElementById('avgKeywordCoverage').textContent = (summary.avg_keyword_coverage || 0).toFixed(1) + '%';
        document.getElementById('pctCta').textContent = (summary.pct_has_cta || 0).toFixed(1) + '%';
        document.getElementById('pctOgImage').textContent = (summary.pct_has_og_image || 0).toFixed(1) + '%';
        document.getElementById('qualityTimestamp').textContent = 'Updated: ' + new Date().toLocaleString('ko-KR');
    } catch (e) {
        console.error('Failed to load quality summary:', e);
    }

    try {
        const rows = await fetchJSON(`${API_BASE}/quality/markdown-issues?days=30`);
        createLineChart('markdownIssuesChart', rows.map(r => r.date), [
            { label: 'Bold', data: rows.map(r => r.bold), borderColor: '#0d6efd', tension: 0.3 },
            { label: 'Italic', data: rows.map(r => r.italic), borderColor: '#ffc107', tension: 0.3 },
            { label: 'Strike', data: rows.map(r => r.strike), borderColor: '#dc3545', tension: 0.3 },
        ]);
    } catch (e) {
        console.error('Failed to load markdown issues:', e);
    }

    try {
        const rows = await fetchJSON(`${API_BASE}/quality/hugo-build`);
        createLineChart('buildHealthChart', rows.map(r => r.date), [
            { label: 'Success Rate %', data: rows.map(r => r.success_rate), borderColor: '#198754', tension: 0.3 },
        ]);
    } catch (e) {
        console.error('Failed to load build health:', e);
    }

    try {
        const rows = await fetchJSON(`${API_BASE}/quality/by-blog`);
        const tbody = document.getElementById('qualityTable');
        tbody.innerHTML = rows.map(r => `<tr>
            <td><strong>${r.blog_id}</strong></td>
            <td>${r.total}</td>
            <td>${(r.avg_readability || 0).toFixed(3)}</td>
            <td>${(r.avg_keyword_coverage || 0).toFixed(1)}%</td>
            <td>${(r.pct_cta || 0).toFixed(1)}%</td>
            <td>${(r.pct_og_image || 0).toFixed(1)}%</td>
        </tr>`).join('');
    } catch (e) {
        console.error('Failed to load quality by blog:', e);
    }
}

// ── Auto-refresh (30s on overview) ──
let refreshTimer = null;

function startAutoRefresh() {
    if (refreshTimer) clearInterval(refreshTimer);
    refreshTimer = setInterval(() => {
        loadSummary();
        // Only refresh health automatically (charts are expensive)
        loadHealth();
    }, 30000);
}

// ── Init ──
document.addEventListener('DOMContentLoaded', () => {
    const path = window.location.pathname;

    if (path === '/' || path === '') {
        loadSummary();
        loadPostsChart();
        loadRevenueChart();
        loadTopPosts();
        loadHealth();
        startAutoRefresh();
    } else if (path === '/revenue') {
        loadRevenuePage();
    } else if (path === '/traffic') {
        loadTrafficPage();
    } else if (path === '/search') {
        loadSearchPage();
    } else if (path === '/health') {
        loadHealth();
        setInterval(loadHealth, 30000);
    } else if (path === '/quality') {
        loadQualityPage();
    }
});
