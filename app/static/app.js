console.log('InsightIQ app.js loaded');

let currentDataset = null;

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initApp);
} else {
  initApp();
}

function initApp() {
  const form = document.getElementById('uploadForm');
  if (form) form.addEventListener('submit', handleFormSubmit);
  const fileInput = document.getElementById('fileInput');
  if (fileInput) {
    fileInput.addEventListener('change', function () {
      const dz = this.closest('.drop-zone');
      if (this.files.length > 0) {
        const file = this.files[0];
        const ext = file.name.split('.').pop().toLowerCase();

        // Validation
        if (file.size > 10 * 1024 * 1024) {
          alert('File too large. Maximum size is 10MB.');
          this.value = ''; // Reset input
          dz.querySelector('h3').textContent = 'Upload Your Dataset';
          dz.querySelector('p').textContent = 'Supported formats: CSV, XLSX, XLS';
          return;
        }

        if (!['csv', 'xlsx', 'xls'].includes(ext)) {
          alert('Invalid file format. Please upload a CSV or Excel file.');
          this.value = '';
          dz.querySelector('h3').textContent = 'Upload Your Dataset';
          dz.querySelector('p').textContent = 'Supported formats: CSV, XLSX, XLS';
          return;
        }

        dz.querySelector('h3').textContent = file.name;
        dz.querySelector('p').textContent = (file.size / 1024).toFixed(1) + ' KB';
      }
    });
  }
  console.log('initApp complete');
}

/* ========== FORMATTING ========== */
function formatNumber(n) {
  if (n == null) return '—';
  if (Math.abs(n) >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
  if (Math.abs(n) >= 1_000) return (n / 1_000).toFixed(1) + 'K';
  return n.toLocaleString();
}
function getCurrencySymbol() {
  const map = { 'USD': '$', 'EUR': '€', 'GBP': '£', 'INR': '₹', 'JPY': '¥' };
  if (currentDataset && currentDataset.schema && currentDataset.schema.currency) {
    return map[currentDataset.schema.currency] || '$';
  }
  return '$';
}

function formatCurrency(n) {
  if (n == null) return '—';
  return getCurrencySymbol() + formatNumber(n);
}
function formatUnits(n) {
  if (n == null) return '—';
  return formatNumber(n) + ' units';
}
function fmtPct(n) {
  if (n == null) return '—';
  return n.toFixed(1) + '%';
}
function fmtMetric(m) {
  const fmt = m.format;
  if (fmt === 'currency') return formatCurrency(m.value);
  if (fmt === 'integer') return formatUnits(m.value);
  if (fmt === 'percent') return fmtPct(m.value);
  return formatNumber(m.value);  // no default to currency
}
function show(id) { const el = document.getElementById(id); if (el) el.classList.remove('hidden'); }
function switchToSection(sectionId, clickedLink) {
  console.log('[SPA] Switching to:', sectionId);

  // 1. Reset all sections aggressively
  const container = document.getElementById('spa-container');
  if (container) {
    const children = container.children;
    for (let i = 0; i < children.length; i++) {
      const child = children[i];
      child.classList.remove('active');
      child.style.setProperty('display', 'none', 'important');
      child.style.setProperty('visibility', 'hidden', 'important');
      child.style.setProperty('opacity', '0', 'important');
      child.style.setProperty('position', 'absolute', 'important');
    }
  }

  // 2. Show the intended section
  const target = document.getElementById(sectionId);
  if (target) {
    target.classList.add('active');
    target.style.setProperty('display', 'block', 'important');
    target.style.setProperty('visibility', 'visible', 'important');
    target.style.setProperty('opacity', '1', 'important');
    target.style.setProperty('position', 'relative', 'important');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  } else {
    console.error('[SPA] Section NOT FOUND:', sectionId);
    return;
  }

  // 3. Update Sidebar links
  document.querySelectorAll('.sidebar-link').forEach(l => l.classList.remove('active'));
  if (clickedLink) {
    clickedLink.classList.add('active');
  } else {
    const fallbackLink = document.querySelector(`.sidebar-link[onclick*="${sectionId}"]`);
    if (fallbackLink) fallbackLink.classList.add('active');
  }
  // 4. Handle specific section logic
  if (sectionId === 'visualizations-section' && window._lastAnalyticsData) {
    populateVisualizationsSection(window._lastAnalyticsData);
  }
}
async function safe(fn) { try { await fn(); } catch (e) { console.error(fn.name + ':', e); } }

/* ========== UPLOAD ========== */
async function handleFormSubmit(e) {
  e.preventDefault();
  const btn = document.getElementById('uploadBtn');
  const status = document.getElementById('uploadStatus');
  btn.disabled = true;
  btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Analyzing...';
  status.style.display = 'none';

  try {
    const fd = new FormData(this);
    const res = await fetch('/api/upload', { method: 'POST', body: fd });
    if (!res.ok) {
      const errorData = await res.json();
      console.log('Error Data:', errorData);
      const errorMessage = errorData.detail || 'Upload failed: ' + res.status;
      alert('Upload failed. Please ensure the file is a valid CSV or Excel document.');
      throw new Error(errorMessage);
    }
    const data = await res.json();
    currentDataset = data.metadata;
    document.getElementById('landingPage').style.display = 'none';
    document.getElementById('dashboard').style.display = 'block';
    await loadDashboard();
  } catch (err) {
    status.textContent = 'Upload encountered an issue. Please try again.';
    status.style.display = 'block';
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<i class="fa-solid fa-bolt"></i> Analyze Now';
  }
}

/* ========== DASHBOARD ========== */
async function loadDashboard() {
  try {
    const res = await fetch(`/api/analytics/${currentDataset.table_name}`);
    if (!res.ok) throw new Error('Analytics failed');
    const data = await res.json();

    document.getElementById('topBarTitle').textContent = currentDataset.name;
    document.getElementById('topBarSub').textContent =
      `Analysing ${data.total_rows.toLocaleString()} rows across ${data.total_columns} columns`;

    // Store for visualizations section
    window._lastAnalyticsData = data;

    renderMetrics(data);
    renderStats(data);
    renderInsights(data);
    generateCharts(data);

    // Reset to dashboard section
    switchToSection('dashboard-section');

    setTimeout(() => loadAllAIFeatures(), 300);
  } catch (err) {
    console.error('Dashboard:', err);
  }
}

/* ========== SMART METRIC CARDS ========== */
function renderMetrics(data) {
  const grid = document.getElementById('metricsSection');
  grid.innerHTML = '';

  const iconMap = {
    'dollar': { cls: 'green', icon: 'fa-dollar-sign' },
    'chart': { cls: 'purple', icon: 'fa-chart-line' },
    'users': { cls: 'cyan', icon: 'fa-users' },
    'box': { cls: 'amber', icon: 'fa-boxes-stacked' },
    'cost': { cls: 'purple', icon: 'fa-receipt' },
    'returns': { cls: 'purple', icon: 'fa-rotate-left' }
  };

  // Find Total Revenue and Units Sold from computed_metrics
  let revenueMetric = null;
  let unitsSoldMetric = null;
  let otherMetrics = [];

  if (data.computed_metrics && data.computed_metrics.length > 0) {
    console.log('computed_metrics from API:', JSON.stringify(data.computed_metrics.map(m => ({ label: m.label, value: m.value, format: m.format }))));
    data.computed_metrics.forEach(m => {
      const lbl = (m.label || '').toLowerCase();
      if ((lbl.includes('revenue') || lbl === 'total revenue') && !revenueMetric) {
        revenueMetric = m;
      } else if ((lbl.includes('unit') || lbl.includes('quantity') || lbl === 'units sold') && !unitsSoldMetric) {
        unitsSoldMetric = m;
      } else {
        otherMetrics.push(m);
      }
    });
  } else {
    console.log('No computed_metrics in API response');
  }
  console.log('revenueMetric:', revenueMetric ? revenueMetric.label : 'NONE');
  console.log('unitsSoldMetric:', unitsSoldMetric ? unitsSoldMetric.label : 'NONE');

  // Fallback: if no Units Sold found in computed_metrics, look in numeric_summary
  if (!unitsSoldMetric && data.numeric_summary && data.numeric_summary.length > 0) {
    const qtyStat = data.numeric_summary.find(s =>
      /quantity|qty|units/i.test(s.name)
    );
    if (qtyStat) {
      unitsSoldMetric = { label: 'Units Sold', value: qtyStat.sum, format: 'integer', icon: 'box', change_pct: null };
      console.log('Units Sold found in numeric_summary:', qtyStat.name, qtyStat.sum);
    }
  }

  // Card 1: Total Revenue
  if (revenueMetric) {
    grid.innerHTML += _buildMetricCard(revenueMetric, iconMap);
  } else {
    // Fallback: Total Rows
    grid.innerHTML += `
      <div class="metric-card">
        <div class="metric-top"><div>
          <div class="metric-label">Total Rows</div>
          <div class="metric-value">${formatNumber(data.total_rows)}</div>
        </div><div class="metric-icon green"><i class="fa-solid fa-database"></i></div></div>
      </div>`;
  }

  // Card 2: Total Units Sold (force integer format — never show $)
  if (unitsSoldMetric) {
    const unitsValue = formatNumber(unitsSoldMetric.value);
    let changeHtml = '';
    if (unitsSoldMetric.change_pct != null) {
      const dir = unitsSoldMetric.change_pct >= 0 ? 'up' : 'down';
      changeHtml = `<div class="metric-change ${dir}">
        <i class="fa-solid fa-caret-${dir}"></i>
        ${Math.abs(unitsSoldMetric.change_pct)}% <span>vs last period</span>
      </div>`;
    }
    grid.innerHTML += `
      <div class="metric-card">
        <div class="metric-top">
          <div>
            <div class="metric-label">Total Units Sold</div>
            <div class="metric-value">${unitsValue}</div>
          </div>
          <div class="metric-icon amber"><i class="fa-solid fa-boxes-stacked"></i></div>
        </div>
        ${changeHtml}
      </div>`;
  } else {
    // Fallback: Columns count
    grid.innerHTML += `
      <div class="metric-card">
        <div class="metric-top"><div>
          <div class="metric-label">Columns</div>
          <div class="metric-value">${data.total_columns}</div>
        </div><div class="metric-icon amber"><i class="fa-solid fa-table-columns"></i></div></div>
      </div>`;
  }

  // Card 3: Confidence Score
  grid.innerHTML += `
    <div class="metric-card highlight" id="confidenceCard" style="cursor:pointer;" onclick="openTrustModal()" title="View Analytical Confidence Breakdown">
      <div class="metric-top"><div>
        <div class="metric-label">Confidence Score</div>
        <div class="metric-value" id="confidenceScore" style="font-size:2.2rem;">—</div>
      </div><div class="metric-icon" style="background:rgba(255,255,255,0.15); color:#fff;"><i class="fa-solid fa-shield-check"></i></div></div>
      <small id="confidenceLabel">Loading breakdown...</small>
    </div>`;
}

function _buildMetricCard(m, iconMap) {
  const ico = iconMap[m.icon] || iconMap.dollar;
  const formatted = fmtMetric(m);
  let changeHtml = '';
  if (m.change_pct != null) {
    const dir = m.change_pct >= 0 ? 'up' : 'down';
    changeHtml = `<div class="metric-change ${dir}">
      <i class="fa-solid fa-caret-${dir}"></i>
      ${Math.abs(m.change_pct)}% <span>vs last period</span>
    </div>`;
  }
  return `
    <div class="metric-card">
      <div class="metric-top">
        <div>
          <div class="metric-label">${m.label}</div>
          <div class="metric-value">${formatted}</div>
        </div>
        <div class="metric-icon ${ico.cls}"><i class="fa-solid ${ico.icon}"></i></div>
      </div>
      ${changeHtml}
    </div>`;
}

/* ========== STATS TABLE ========== */
function renderStats(data) {
  if (!data.column_stats) return;
  const body = document.getElementById('statsBody');
  body.innerHTML = Object.entries(data.column_stats).map(([col, s]) => {
    const isId = s.is_id ? ' <span style="color:var(--amber);font-size:0.7rem;">ID</span>' : '';
    return `<tr><td><strong>${col}</strong>${isId}</td><td>${s.dtype}</td><td>${s.non_null_count || '—'}</td><td>${s.missing_percent.toFixed(1)}%</td></tr>`;
  }).join('');
}

/* ========== INSIGHTS ========== */
function renderInsights(data) {
  const box = document.getElementById('insights');
  const items = [];
  items.push({ icon: '📊', title: 'Dataset Overview', desc: `${data.total_rows.toLocaleString()} rows × ${data.total_columns} columns loaded` });

  // ID exclusion info
  const idCols = Object.entries(data.column_stats).filter(([, s]) => s.is_id);
  if (idCols.length > 0) {
    items.push({ icon: '🔑', title: 'ID Columns Excluded', desc: `${idCols.map(([n]) => n).join(', ')} excluded from numeric analysis` });
  }

  const missing = Object.values(data.column_stats).filter(s => s.missing_percent > 0);
  if (missing.length > 0) {
    const worst = missing.sort((a, b) => b.missing_percent - a.missing_percent)[0];
    items.push({ icon: '⚠️', title: 'Data Quality Alert', desc: `${missing.length} column(s) with missing data. Worst: ${worst.missing_percent.toFixed(1)}%` });
  } else {
    items.push({ icon: '✅', title: 'Perfect Data Quality', desc: 'No missing values detected' });
  }

  items.push({ icon: '🤖', title: 'AI Ready', desc: 'Root Cause, Forecasting, and Chat active below' });

  box.innerHTML = items.map(i => `
    <div class="insight-item">
      <div class="insight-icon">${i.icon}</div>
      <div class="insight-text"><strong>${i.title}</strong><span>${i.desc}</span></div>
    </div>`).join('');
}

/* ========== CHARTS ========== */
function generateCharts(data) {
  const row1 = document.getElementById('chartsSection');
  const row2 = document.getElementById('chartsRow2');
  row1.innerHTML = '';
  row2.innerHTML = '';

  Chart.defaults.color = '#94a3b8';
  Chart.defaults.borderColor = 'rgba(148,163,184,0.08)';
  Chart.defaults.font.family = "'Inter', sans-serif";

  // 1. Monthly Revenue Trend
  if (data.time_series && data.time_series.dates.length > 0) {
    const ts = data.time_series;
    const canvas = makeChartBox(row1, 'Revenue Trend', 'Monthly revenue aggregation');
    const ctx = canvas.getContext('2d');
    const grad = ctx.createLinearGradient(0, 0, 0, 280);
    grad.addColorStop(0, 'rgba(99,102,241,0.25)');
    grad.addColorStop(1, 'rgba(99,102,241,0)');

    new Chart(canvas, {
      type: 'line',
      data: {
        labels: ts.dates,
        datasets: [{
          label: ts.value_column,
          data: ts.values,
          borderColor: '#6366f1', backgroundColor: grad,
          fill: true, tension: 0.35, borderWidth: 2,
          pointRadius: 3, pointHoverRadius: 6,
          pointBackgroundColor: '#6366f1', pointBorderColor: '#0f172a', pointBorderWidth: 2
        }]
      },
      options: timeChartOpts(getCurrencySymbol())
    });
  }

  // 2. Top 5 Countries by Revenue (bar chart)
  if (data.top_countries && data.top_countries.labels.length > 0) {
    const tc = data.top_countries;
    const canvas = makeChartBox(row1, `Top ${tc.labels.length} by Revenue`, tc.column);
    new Chart(canvas, {
      type: 'bar',
      data: {
        labels: tc.labels,
        datasets: [{
          label: 'Revenue',
          data: tc.values,
          backgroundColor: ['#6366f1', '#22d3ee', '#10b981', '#f59e0b', '#a855f7'],
          borderRadius: 6, barThickness: 30
        }]
      },
      options: {
        responsive: true, maintainAspectRatio: true, indexAxis: 'y',
        plugins: {
          legend: { display: false },
          tooltip: { ...tooltipStyle(), callbacks: { label: ctx => formatCurrency(ctx.parsed.x) } }
        },
        scales: {
          x: { grid: { color: 'rgba(148,163,184,0.06)' }, ticks: { font: { size: 10 }, callback: v => formatCurrency(v) } },
          y: { grid: { display: false }, ticks: { font: { size: 11 } } }
        }
      }
    });
  } else {
    // Fallback: Regional Distribution doughnut
    const catKeys = data.category_distributions ? Object.keys(data.category_distributions) : [];
    if (catKeys.length > 0) {
      let catCol = catKeys.find(k => /region|area|zone|territory|state|country/i.test(k)) || catKeys[0];
      const dist = data.category_distributions[catCol];
      const canvas = makeChartBox(row1, catCol + ' Distribution', '');
      const COLORS = ['#6366f1', '#22d3ee', '#10b981', '#f59e0b', '#f43f5e', '#a855f7', '#ec4899', '#14b8a6'];
      new Chart(canvas, {
        type: 'doughnut',
        data: {
          labels: dist.labels,
          datasets: [{ data: dist.values, backgroundColor: COLORS, borderColor: '#111827', borderWidth: 3 }]
        },
        options: {
          responsive: true, maintainAspectRatio: true, cutout: '60%',
          plugins: {
            legend: { position: 'right', labels: { boxWidth: 12, padding: 10, font: { size: 11 } } },
            tooltip: tooltipStyle()
          }
        }
      });
    }
  }

  // 3. Revenue vs Quantity correlation
  if (data.correlation_pairs && data.correlation_pairs.length > 0) {
    const cp = data.correlation_pairs[0];
    const canvas = makeChartBox(row2, cp.col1 + ' vs ' + cp.col2, 'Monthly correlation');
    new Chart(canvas, {
      type: 'line',
      data: {
        labels: cp.dates,
        datasets: [
          { label: cp.col1, data: cp.values1, borderColor: '#6366f1', borderWidth: 2, tension: 0.3, pointRadius: 2, yAxisID: 'y' },
          { label: cp.col2, data: cp.values2, borderColor: '#f43f5e', borderDash: [4, 3], borderWidth: 2, tension: 0.3, pointRadius: 2, yAxisID: 'y1' }
        ]
      },
      options: {
        responsive: true, maintainAspectRatio: true, interaction: { mode: 'index', intersect: false },
        plugins: { legend: { labels: { boxWidth: 10, font: { size: 11 } } }, tooltip: tooltipStyle() },
        scales: {
          x: { grid: { display: false }, ticks: { font: { size: 9 }, maxTicksLimit: 12 } },
          y: { position: 'left', grid: { color: 'rgba(148,163,184,0.06)' }, ticks: { font: { size: 10 }, callback: v => formatCurrency(v) } },
          y1: { position: 'right', grid: { display: false }, ticks: { font: { size: 10 } } }
        }
      }
    });
  }

  // 4. Data Completeness
  if (data.column_stats) {
    const cols = Object.entries(data.column_stats);
    const canvas = makeChartBox(row2, 'Data Completeness', 'Column-level data quality');
    new Chart(canvas, {
      type: 'bar',
      data: {
        labels: cols.map(([name]) => name),
        datasets: [{
          label: 'Complete %',
          data: cols.map(([, s]) => 100 - s.missing_percent),
          backgroundColor: cols.map(([, s]) => (100 - s.missing_percent) === 100 ? '#10b981' : '#f59e0b'),
          borderRadius: 4, barThickness: 18
        }]
      },
      options: {
        responsive: true, maintainAspectRatio: true, indexAxis: 'y',
        plugins: {
          legend: { display: false },
          tooltip: { ...tooltipStyle(), callbacks: { label: ctx => ctx.parsed.x.toFixed(1) + '% complete' } }
        },
        scales: {
          x: { max: 100, grid: { color: 'rgba(148,163,184,0.06)' }, ticks: { font: { size: 10 }, callback: v => v + '%' } },
          y: { grid: { display: false }, ticks: { font: { size: 10 } } }
        }
      }
    });
  }
}

function makeChartBox(parent, title, subtitle) {
  const sec = document.createElement('div');
  sec.className = 'section';
  const h3 = document.createElement('h3');
  h3.className = 'section-title';
  h3.textContent = title;
  sec.appendChild(h3);
  if (subtitle) {
    const sub = document.createElement('p');
    sub.className = 'section-subtitle';
    sub.textContent = subtitle;
    sec.appendChild(sub);
  }
  const canvas = document.createElement('canvas');
  sec.appendChild(canvas);
  parent.appendChild(sec);
  return canvas;
}

function tooltipStyle() {
  return { backgroundColor: '#1e293b', titleColor: '#f1f5f9', bodyColor: '#94a3b8', borderColor: 'rgba(148,163,184,0.15)', borderWidth: 1, padding: 10, cornerRadius: 8 };
}

function timeChartOpts(prefix) {
  return {
    responsive: true, maintainAspectRatio: true,
    plugins: { legend: { display: false }, tooltip: tooltipStyle() },
    scales: {
      x: { grid: { display: false }, ticks: { font: { size: 9 }, maxTicksLimit: 12 } },
      y: { grid: { color: 'rgba(148,163,184,0.06)' }, ticks: { font: { size: 10 }, callback: v => prefix + formatNumber(v) } }
    }
  };
}

/* ========== AI FEATURES ========== */
async function loadAllAIFeatures() {
  // Sections are now always present in the DOM (inside their content-sections)
  // No need to show/hide them — navigation controls visibility

  const qi = document.getElementById('questionInput');
  if (qi) qi.addEventListener('keypress', e => { if (e.key === 'Enter') { e.preventDefault(); askQuestion(); } });

  await safe(loadConfidenceScore);
  await safe(loadIndustryDetection);
  await safe(loadRootCauses);
  await safe(loadCohortRetention);
  await safe(loadForecasts);
  await safe(loadExecutiveSummary);
}

/* ---- Confidence Score & Trust Transparency ---- */
let lastTrustData = null;

async function loadConfidenceScore() {
  const res = await fetch(`/api/confidence/${currentDataset.table_name}`);
  if (!res.ok) return;
  const d = await res.json();
  lastTrustData = d;
  const displayScore = d.trust_score !== undefined ? (d.trust_score * 100).toFixed(0) : (d.confidence_score || 0);
  const displayLabel = d.trust_label || d.confidence_score_quality || 'Unknown';
  document.getElementById('confidenceScore').textContent = displayScore + '%';
  document.getElementById('confidenceLabel').textContent = displayLabel;
}

function openTrustModal() {
  const modal = document.getElementById('trustModal');
  const body = document.getElementById('trustModalBody');

  if (!lastTrustData) {
    body.innerHTML = '<div style="padding:2rem; text-align:center; color:var(--text-muted);"><i class="fa-solid fa-circle-notch fa-spin"></i> Loading breakdown...</div>';
    modal.style.display = 'flex';
    return;
  }

  const d = lastTrustData;
  let html = `
    <div style="text-align:center; margin-bottom:2rem;">
      <div style="font-size:3.5rem; font-weight:800; color:var(--text-main); line-height:1; letter-spacing:-0.03em;">${(d.trust_score * 100).toFixed(0)}%</div>
      <div style="font-weight:700; color:var(--text-muted); margin-top:0.75rem; font-size:1rem;">${d.trust_label}</div>
    </div>
    
    <table class="trust-table">
      <thead>
        <tr>
          <th>Analytical Factor</th>
          <th>Score</th>
          <th>Weight</th>
          <th>Impact</th>
        </tr>
      </thead>
      <tbody>
  `;

  (d.components || []).forEach(c => {
    const scorePct = (c.score * 100).toFixed(0);
    const weightPct = (c.weight * 100).toFixed(0);
    let impactLabel = 'Moderate';
    let impactClass = 'impact-moderate';

    if (c.score >= 0.85) { impactLabel = 'Strong'; impactClass = 'impact-strong'; }
    else if (c.score < 0.50) { impactLabel = 'Weak'; impactClass = 'impact-weak'; }

    html += `
      <tr>
        <td style="font-weight:600; color:var(--text-main);">${c.name}</td>
        <td style="font-family:monospace; font-weight:700;">${scorePct}%</td>
        <td style="color:var(--text-muted); font-size:0.8rem;">${weightPct}%</td>
        <td><span class="trust-impact-pill ${impactClass}">${impactLabel}</span></td>
      </tr>
    `;
  });

  html += `
      </tbody>
    </table>
    
    <div style="margin-top:2rem; padding:1.25rem; border-radius:14px; border:1px solid rgba(245,158,11,0.2); background:#fffbeb;">
      <div style="display:flex; align-items:center; gap:10px; margin-bottom:0.75rem;">
        <i class="fa-solid fa-circle-info" style="color:var(--amber); font-size:1rem;"></i>
        <strong style="font-size:0.9rem; color:var(--text-main);">Factor Analysis: ${d.limiting_factor}</strong>
      </div>
      <p style="font-size:0.9rem; color:var(--text-gray); margin:0; line-height:1.6;">${d.explanation}</p>
    </div>
    
    <div style="margin-top:2rem;">
      <h4 style="font-size:0.9rem; font-weight:700; color:var(--text-main); margin-bottom:0.75rem; display:flex; align-items:center; gap:8px;">
        <i class="fa-solid fa-wrench" style="color:var(--text-muted);"></i>
        Improvement Signal
      </h4>
      <ul style="margin:0; padding-left:1.5rem; font-size:0.85rem; color:var(--text-gray); line-height:1.8;">
        <li>Increase historical data range to improve seasonal model fit.</li>
        <li>Review data for outlier transactions that may skew volatility.</li>
        <li>Segment data into more homogeneous dimensions (e.g., Region, Product Category).</li>
      </ul>
    </div>
  `;

  body.innerHTML = html;
  modal.style.display = 'flex';
}

function closeTrustModal() {
  document.getElementById('trustModal').style.display = 'none';
}

// Global modal handlers
window.addEventListener('click', (e) => {
  const modal = document.getElementById('trustModal');
  if (e.target === modal) closeTrustModal();
});

window.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') closeTrustModal();
});

/* ---- Industry Detection ---- */
async function loadIndustryDetection() {
  const res = await fetch(`/api/industry/${currentDataset.table_name}`);
  if (!res.ok) return;
  const d = await res.json();
  document.getElementById('industryType').textContent = d.detected_industry;
  const badge = document.getElementById('industryBadge');
  if (badge) badge.style.display = 'inline-flex';
  const sub = document.getElementById('topBarSub');
  if (sub && d.detected_industry) {
    sub.textContent += ` · ${d.detected_industry}`;
  }
}

/* ---- Root Cause Analysis ---- */
async function loadRootCauses() {
  const schema = currentDataset.schema || {};
  let numCols = [];
  let groupCols = [];

  if (schema.numeric_columns && Array.isArray(schema.numeric_columns)) {
    numCols = schema.numeric_columns;
  } else if (schema.columns && Array.isArray(schema.columns)) {
    numCols = schema.columns.filter(c => typeof c.dtype === 'string' && (c.dtype.includes('int') || c.dtype.includes('float'))).map(c => c.name);
  } else {
    numCols = Object.keys(schema).filter(c => typeof schema[c] === 'string' && (schema[c].includes('int') || schema[c].includes('float')));
  }

  if (schema.categorical_columns && Array.isArray(schema.categorical_columns)) {
    groupCols = schema.categorical_columns.filter(c => !(/id|no|code/i.test(c))).slice(0, 2);
  } else if (schema.columns && Array.isArray(schema.columns)) {
    groupCols = schema.columns.filter(c => typeof c.dtype === 'string' && !c.dtype.includes('int') && !c.dtype.includes('float')).map(c => c.name).filter(c => !(/id|no|code/i.test(c))).slice(0, 2);
  } else {
    groupCols = Object.keys(schema).filter(c => typeof schema[c] === 'string' && !schema[c].includes('int') && !schema[c].includes('float')).filter(c => !(/id|no|code/i.test(c))).slice(0, 2);
  }

  const body = { table_name: currentDataset.table_name };
  if (numCols.length > 0) body.metric_column = numCols[0];
  if (groupCols.length > 0) body.group_by = groupCols;

  const res = await fetch('/api/root-cause', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
  if (!res.ok) {
    document.getElementById('rootCauseContent').innerHTML = '<p style="color:var(--text-muted);">Root cause analysis unavailable.</p>';
    return;
  }
  const d = await res.json();

  let html = '';

  // Show insight summary
  if (d.insight_summary) {
    const isAi = d.ai_generated;
    const change = d.change_percent ?? d.kpi_change_percent ?? 0;
    const direction = change >= 0 ? 'Increase' : 'Decrease';
    const color = change >= 0 ? 'var(--green)' : 'var(--red)';
    const prevPeriod = d.previous_period || 'Previous Month';
    const currPeriod = d.current_period || 'Current Month';
    const prevVal = d.previous_value != null ? (d.previous_value >= 1e6 ? (d.previous_value / 1e6).toFixed(2) + 'M' : d.previous_value >= 1e3 ? (d.previous_value / 1e3).toFixed(1) + 'K' : d.previous_value.toFixed(0)) : null;
    const currVal = d.current_value != null ? (d.current_value >= 1e6 ? (d.current_value / 1e6).toFixed(2) + 'M' : d.current_value >= 1e3 ? (d.current_value / 1e3).toFixed(1) + 'K' : d.current_value.toFixed(0)) : null;

    html += `<div style="margin-bottom:1.5rem;">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.8rem;">
        <p style="color:var(--text-gray); font-size:0.88rem; margin:0;">Comparing: <strong>${prevPeriod}</strong> → <strong>${currPeriod}</strong>${prevVal && currVal ? ` &nbsp;·&nbsp; ${prevVal} → ${currVal}` : ''}</p>
        ${isAi ? '<span class="ai-badge" title="Insights generated by AI"><i class="fa-solid fa-sparkles"></i> AI Narrative</span>' : ''}
      </div>
      <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:1rem;">
        <div style="display:flex; align-items:baseline; gap:12px; flex-wrap:wrap;">
            <div style="font-size:2.4rem; font-weight:800; color:${color};">${change >= 0 ? '+' : ''}${change.toFixed(2)}%</div>
            <div style="font-size:1rem; font-weight:600; color:var(--text-gray); margin-right: 8px;">${direction} in revenue (month-over-month)</div>
            ${d.is_significant !== undefined ?
        `<div style="font-size:0.85rem; font-weight:500; color:${d.is_significant ? 'var(--indigo)' : 'var(--text-muted)'}; padding: 4px 8px; border-radius: 4px; border: 1px solid ${d.is_significant ? 'rgba(99,102,241,0.2)' : 'var(--border)'}; background: ${d.is_significant ? 'rgba(99,102,241,0.05)' : '#f8fafc'};">
                 <i class="${d.is_significant ? 'fa-solid fa-chart-pie' : 'fa-solid fa-circle-minus'}"></i> ` +
        (d.is_significant ? 'Statistically significant change detected.' : 'Change observed but not statistically significant.') +
        `</div>`
        : ''}
        </div>
        ${d.anomaly_detected ? `<div style="padding: 6px 12px; background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.2); border-radius: 6px; color: var(--red); font-size: 0.85rem; font-weight: 600; text-align: right;"><i class="fa-solid fa-triangle-exclamation"></i> Anomaly Signal Detected<br><span style="font-size: 0.75rem; font-weight: 500;">High Confidence</span></div>` : ''}
      </div>
      <p style="color:var(--text-main); font-size:0.9rem; line-height:1.6; margin:0; font-weight:500;">${d.insight_summary}</p>
    </div>`;
  }

  // Show Waterfall
  if (d.waterfall && d.waterfall.components && d.waterfall.components.length > 0) {
    html += `
      <div style="margin-top:2rem; padding:1.5rem; background:#fff; border-radius:12px; border:1px solid var(--border);">
        <h3 style="margin:0 0 4px 0; font-size:1.1rem; color:var(--text-main);">Month-over-Month Revenue Bridge</h3>
        <p style="margin:0 0 1.5rem 0; font-size:0.85rem; color:var(--text-gray);">Breakdown of drivers contributing to revenue change</p>
        <div id="waterfall-chart-root" style="height:350px;"></div>
      </div>
    `;
  }

  // Show Drivers Grid
  html += '<div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap:12px; margin-top:1.5rem;">';
  if (d.top_drivers && d.top_drivers.length > 0) {
    d.top_drivers.forEach(dr => {
      const name = dr.value || dr.name || 'Unknown';
      const dim = dr.dimension || 'Factor';
      const pct = dr.normalized_percent != null ? dr.normalized_percent.toFixed(1) : '–';
      const dir = dr.direction || 'positive';
      const deltaRaw = dr.delta_value ?? dr.impact_value ?? null;
      const impactStr = deltaRaw != null ? formatCurrency(deltaRaw) : '—';

      const iconClass = dir === 'negative' ? 'fa-arrow-trend-down' : 'fa-chart-line';
      const badgeStyle = dir === 'negative' ? 'background:var(--red-bg); color:var(--red);' : 'background:var(--green-bg); color:var(--green);';
      const iconStyle = dir === 'negative' ? 'background:var(--red-bg); color:var(--red);' : 'background:rgba(99,102,241,0.08); color:var(--accent);';

      html += `
          <div class="driver-card" style="display:flex; align-items:center; padding:12px; border:1px solid var(--border); border-radius:var(--radius-sm); background:white; position:relative;">
            <div class="driver-icon" style="width:40px; height:40px; border-radius:50%; display:flex; align-items:center; justify-content:center; margin-right:12px; ${iconStyle}">
              <i class="fa-solid ${iconClass}"></i>
            </div>
            <div class="driver-info" style="flex:1;">
              <div style="display:flex; justify-content:space-between; align-items:start;">
                <strong style="font-size:0.9rem; color:var(--text-main);">${name}</strong>
                <span class="driver-badge" style="font-size:0.7rem; padding:2px 6px; border-radius:4px; font-weight:700; ${badgeStyle}">${dir === 'negative' ? '-' : '+'}${pct}%</span>
              </div>
              <div style="display:flex; justify-content:space-between; align-items:center; margin-top:4px;">
                <small style="color:var(--text-muted); font-size:0.75rem;">${dim}</small>
                <span style="font-size:0.8rem; font-weight:600; color:var(--text-main);" title="Highest contribution to month-over-month change">${impactStr}</span>
              </div>
              ${dr.contribution !== undefined ? `<div style="margin-top:8px; font-size:0.75rem; color:var(--text-gray); border-top: 1px dotted var(--border); padding-top: 8px;">Driver Strength: <strong style="color:var(--text-main);">${(dr.contribution * 100).toFixed(1)}%</strong> of total change</div>` : ''}
            </div>
          </div>`;
    });
  } else {
    html += '<p style="color:var(--text-muted); grid-column: 1/-1;">No major business drivers identified for this period change.</p>';
  }
  html += '</div>';

  // Show recommendations
  if (d.recommendations && d.recommendations.length > 0) {
    html += `<div style="margin-top:2rem; padding:1.25rem; background:#f8fafc; border-radius:12px; border:1px solid #e2e8f0;">
      <strong style="color:var(--text-main); font-size:0.95rem; display:block; margin-bottom:0.75rem;"><i class="fa-solid fa-lightbulb" style="color:var(--amber);"></i> Recommendations</strong>
      <ul style="margin:0; padding-left:1.2rem; color:var(--text-gray); font-size:0.88rem; line-height:1.7;">
        ${d.recommendations.slice(0, 4).map(r => `<li>${r}</li>`).join('')}
      </ul></div>`;
  }

  document.getElementById('rootCauseContent').innerHTML = html;

  // Render React Waterfall if available
  if (d.waterfall && d.waterfall.components && d.waterfall.components.length > 0) {
    renderWaterfall(d.waterfall);
  }
}

function renderWaterfall(w) {
  const container = document.getElementById('waterfall-chart-root');
  if (!container) return;
  const { React, ReactDOM, Recharts } = window;
  if (!React || !ReactDOM || !Recharts) return;
  const { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } = Recharts;

  let currentVal = w.previous_value;
  const data = [{ name: 'Previous', value: [0, currentVal], color: '#94a3b8' }];

  w.components.forEach(c => {
    const nextVal = currentVal + c.value;
    const start = Math.min(currentVal, nextVal);
    const end = Math.max(currentVal, nextVal);
    let labelParts = (c.label || '').split(':');
    let shortName = labelParts.length > 1 ? labelParts[1].trim() : c.label;
    if (shortName.length > 12) shortName = shortName.substring(0, 10) + '..';

    data.push({
      name: shortName,
      value: [start, end],
      color: c.direction === 'positive' ? '#10b981' : '#ef4444',
      raw: c.value
    });
    currentVal = nextVal;
  });
  data.push({ name: 'Current', value: [0, w.current_value], color: '#6366f1' });

  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      const p = payload[0].payload;
      return React.createElement('div', { style: { background: '#fff', padding: '8px 12px', border: '1px solid #e2e8f0', borderRadius: '6px', fontSize: '12px' } },
        React.createElement('strong', { style: { display: 'block', marginBottom: '4px' } }, label),
        React.createElement('span', { style: { color: p.color, fontWeight: 'bold' } },
          p.raw !== undefined ? (p.raw > 0 ? '+' : '') + formatCurrency(p.raw) : formatCurrency(p.value[1])
        )
      );
    }
    return null;
  };

  const chart = React.createElement(ResponsiveContainer, { width: '100%', height: '100%' },
    React.createElement(BarChart, { data: data, margin: { top: 20, right: 30, left: 0, bottom: 5 } },
      React.createElement(CartesianGrid, { strokeDasharray: '3 3', vertical: false, stroke: '#e2e8f0' }),
      React.createElement(XAxis, { dataKey: 'name', tick: { fontSize: 11, fill: '#64748b' }, axisLine: false, tickLine: false }),
      React.createElement(YAxis, { tickFormatter: v => formatCurrency(v), tick: { fontSize: 11, fill: '#64748b' }, axisLine: false, tickLine: false }),
      React.createElement(Tooltip, { content: React.createElement(CustomTooltip, null), cursor: { fill: 'transparent' } }),
      React.createElement(Bar, { dataKey: 'value', radius: 4 },
        data.map((entry, index) => React.createElement(Cell, { key: `cell-${index}`, fill: entry.color }))
      )
    )
  );

  ReactDOM.render(chart, container);
}

/* ---- Forecasting ---- */
async function loadForecasts() {
  const res = await fetch('/api/forecast', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ table_name: currentDataset.table_name, periods: 3 })
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    document.getElementById('forecastTable').innerHTML = `
      <div style="padding:14px; background:rgba(245,158,11,0.08); border-radius:10px; border:1px solid rgba(245,158,11,0.15); margin-top:10px;">
        <p style="color:var(--amber); font-size:0.88rem; margin:0;"><i class="fa-solid fa-triangle-exclamation"></i> ${errData.detail || 'Forecast temporarily unavailable. Please try again.'}</p>
      </div>`;
    return;
  }
  const d = await res.json();

  // Utility: format using API-provided currency code
  const apiCurrency = d.currency || 'UNSPECIFIED';
  const formatWithCurrency = (val) => {
    const absVal = Math.abs(val);
    let num;
    if (absVal >= 1_000_000) num = (val / 1_000_000).toFixed(1) + 'M';
    else if (absVal >= 1_000) num = (val / 1_000).toFixed(1) + 'K';
    else num = val.toFixed(2);
    const sym = { INR: '\u20b9', USD: '$', GBP: '\u00a3', EUR: '\u20ac', UNSPECIFIED: '' }[apiCurrency] || '';
    return sym ? sym + num : num + (apiCurrency && apiCurrency !== 'UNSPECIFIED' ? ' ' + apiCurrency : '');
  };

  // Handle invalid or unreliable forecasts
  if (!d.success || d.status === 'invalid_forecast' || d.status === 'invalid') {
    if (d.historical && d.historical.length > 0) renderForecastChart(d);
    document.getElementById('forecastTable').innerHTML = `
      <div style="padding:14px; background:rgba(245,158,11,0.08); border-radius:10px; border:1px solid rgba(245,158,11,0.15); margin-top:10px;">
        <p style="color:var(--amber); font-size:0.88rem; margin:0;"><i class="fa-solid fa-triangle-exclamation"></i> ${d.error || d.message || 'Forecast not reliable due to high volatility.'}</p>
      </div>`;
    return;
  }

  // Handle Reliability Badge
  const metrics = d.metrics || {};
  const reliability = metrics.reliability || 'medium';
  const badgeColors = {
    'high': 'background:var(--green-bg); color:var(--green);',
    'medium': 'background:rgba(245,158,11,0.12); color:var(--amber);',
    'low': 'background:var(--red-bg); color:var(--red);'
  };

  const titleArea = document.querySelector('#forecastSection .section-title');
  if (titleArea && !document.getElementById('reliabilityBadge')) {
    const badge = document.createElement('span');
    badge.id = 'reliabilityBadge';
    badge.className = 'badge';
    badge.style = `margin-left:12px; font-size:0.7rem; text-transform:uppercase; ${badgeColors[reliability]}`;
    badge.innerHTML = `<i class="fa-solid fa-shield-check"></i> ${reliability} reliability`;
    titleArea.appendChild(badge);
  }

  if (d.forecast && d.forecast.length > 0) {
    renderForecastChart(d);

    // Helper for reference-style currency formatting
    const formatRefCurrency = (val) => {
      const sym = getCurrencySymbol();
      if (Math.abs(val) >= 1000000) return sym + (val / 1000000).toFixed(1) + 'M';
      if (Math.abs(val) >= 1000) return sym + (val / 1000).toFixed(1) + 'K';
      return formatCurrency(val);
    };

    const forecastRows = (d.forecast || []).map((f, index) => {
      const periodLabel = f.period || f.date || 'TBD';

      let conf = '—';
      const ciLines = d.confidence_intervals || {};
      const lower = ciLines.lower ? ciLines.lower[index] : null;
      const upper = ciLines.upper ? ciLines.upper[index] : null;

      if (lower !== null && lower !== undefined && upper !== null && upper !== undefined) {
        conf = `${formatWithCurrency(lower)} — ${formatWithCurrency(upper)}`;
      }
      return `<tr><td><strong>${periodLabel}</strong></td><td>${formatWithCurrency(f.value)}</td><td style="font-size:0.8rem;color:var(--text-muted)">${conf}</td></tr>`;
    }).join('');

    const sub = document.querySelector('#forecast-section .section-subtitle');
    if (sub) {
      sub.textContent = 'Projected trend with confidence band';
    }

    const vol = d.volatility || {};
    const volScore = vol.cv != null ? vol.cv.toFixed(2) : '—';
    const volLabel = vol.stability_label || 'Unknown';
    let volColor = 'var(--text-main)';
    let volBg = 'rgba(0,0,0,0.03)';
    if (volLabel.includes('High Stability')) { volColor = 'var(--green)'; volBg = 'var(--green-bg)'; }
    if (volLabel.includes('Moderate')) { volColor = 'var(--amber)'; volBg = 'rgba(245,158,11,0.12)'; }
    if (volLabel.includes('Volatility')) { volColor = 'var(--red)'; volBg = 'var(--red-bg)'; }

    document.getElementById('forecastTable').innerHTML = `
      <div class="forecast-card-wrapper">
        <table class="forecast-table">
          <thead><tr><th>PERIOD</th><th>PREDICTED REVENUE</th><th>CONFIDENCE</th></tr></thead>
          <tbody>${forecastRows}</tbody>
        </table>
        <div style="padding: 12px 16px; border-top: 1px solid var(--border); background: #ffffff;">
            <p style="color:var(--text-muted);font-size:0.75rem;margin:0;">Model R²: <span style="color:var(--text-main); font-weight:600;">${metrics.r2 || '—'}</span> · Method: <span style="color:var(--text-main); font-weight:600;">${metrics.model_used || 'SARIMAX'}</span></p>
        </div>
      </div>
      
      <!-- Volatility Indicator -->
      <div style="margin-top:16px; padding:16px; background:#fff; border-radius:12px; border:1px solid var(--border); display:flex; justify-content:space-between; align-items:center;">
        <div>
          <h4 style="margin:0; font-size:0.8rem; color:var(--text-gray); font-weight:600; text-transform:uppercase;">Revenue Stability</h4>
          <div style="display:flex; align-items:baseline; gap:8px;">
            <p style="margin:4px 0 0 0; font-size:1.15rem; font-weight:700; color:var(--text-main);">CV: ${volScore}</p>
          </div>
        </div>
        <div style="padding:6px 12px; border-radius:6px; background:${volBg}; color:${volColor}; font-weight:600; font-size:0.85rem;">
          <i class="fa-solid fa-chart-line"></i> ${volLabel}
        </div>
      </div>`;
  }
}

/* ---- Customer Retention (Cohorts) ---- */
async function loadCohortRetention() {
  const container = document.getElementById('cohortHeatmapContainer');
  const summaryBox = document.getElementById('cohortSummaryCards');
  if (!container) return;

  const res = await fetch(`/api/cohort/${currentDataset.table_name}`);
  if (!res.ok) {
    container.innerHTML = '<p style="color:var(--amber); text-align:center;"><i class="fa-solid fa-triangle-exclamation"></i> Cohort retention unavailable.</p>';
    summaryBox.innerHTML = '';
    return;
  }
  const d = await res.json();

  if (!d || d.status !== 'ok') {
    container.innerHTML = `<p style="color:var(--amber); text-align:center;">
        <i class="fa-solid fa-info-circle"></i> 
        ${d.message || 'Dataset does not support customer-level cohort tracking (requires user ID and sequential dates).'}
      </p>`;
    summaryBox.innerHTML = '';
    return;
  }

  // Display Confidence Badge
  const badgeColors = {
    'High Stability': 'background:var(--green-bg); color:var(--green);',
    'Moderate Stability': 'background:rgba(245,158,11,0.12); color:var(--amber);',
    'Low Sample Confidence': 'background:var(--red-bg); color:var(--red);'
  };
  const badgeColor = badgeColors[d.confidence] || 'background:rgba(0,0,0,0.05); color:var(--text-main);';
  const badgeHTML = `<span class="badge" style="font-size:0.75rem; font-weight:700; padding:4px 8px; border-radius:6px; ${badgeColor}">
    <i class="fa-solid fa-shield-check"></i> &nbsp;${d.confidence}
  </span>`;
  const badgeContainer = document.getElementById('cohortConfidenceBadge');
  if (badgeContainer) badgeContainer.innerHTML = badgeHTML;

  // Build Summaries
  const sm = d.summary_metrics || {};
  summaryBox.innerHTML = `
    <div style="flex:1; background:#f8fafc; border:1px solid var(--border); border-radius:10px; padding:1.2rem;">
      <h4 style="margin:0; font-size:0.8rem; color:var(--text-gray); font-weight:600; text-transform:uppercase;">Month 1 Retention</h4>
      <div style="font-size:1.8rem; font-weight:800; color:var(--text-main); margin-top:8px;">${sm.avg_month_1_retention || 0}%</div>
      <p style="margin:4px 0 0 0; font-size:0.8rem; color:var(--text-muted);">Avg return rate in Month 1</p>
    </div>
    <div style="flex:1; background:#f8fafc; border:1px solid var(--border); border-radius:10px; padding:1.2rem;">
      <h4 style="margin:0; font-size:0.8rem; color:var(--text-gray); font-weight:600; text-transform:uppercase;">Month 3 Retention</h4>
      <div style="font-size:1.8rem; font-weight:800; color:var(--text-main); margin-top:8px;">${sm.avg_month_3_retention || 0}%</div>
      <p style="margin:4px 0 0 0; font-size:0.8rem; color:var(--text-muted);">Avg return rate in Month 3</p>
    </div>
    <div style="flex:1; background:#f8fafc; border:1px solid var(--border); border-radius:10px; padding:1.2rem;">
      <h4 style="margin:0; font-size:0.8rem; color:var(--text-gray); font-weight:600; text-transform:uppercase;">Est Customer Lifetime</h4>
      <div style="font-size:1.8rem; font-weight:800; color:var(--text-main); margin-top:8px;">${sm.avg_lifetime_months || 0} mo</div>
      <p style="margin:4px 0 0 0; font-size:0.8rem; color:var(--text-muted);">Approximate lifespan</p>
    </div>
  `;

  // Draw Heatmap inside container
  drawCohortHeatmap(d.retention_matrix, d.cohort_sizes, container);
}

function drawCohortHeatmap(matrix, cohortSizes, container) {
  if (!matrix || matrix.length === 0) {
    container.innerHTML = '<p style="color:var(--text-muted);">No cohort retention data to render.</p>';
    return;
  }

  // Find max columns
  let maxColsInd = 0;
  matrix.forEach(row => {
    Object.keys(row).forEach(k => {
      if (k.startsWith('month_')) {
        let n = parseInt(k.split('_')[1], 10);
        if (n > maxColsInd) maxColsInd = n;
      }
    });
  });

  let html = '<div style="overflow-x:auto;"><table style="width:100%; border-collapse:separate; border-spacing:3px; font-size:0.85rem; text-align:center;">';

  // Headers
  html += '<thead><tr>';
  html += '<th style="text-align:left; color:var(--text-muted); font-weight:600; padding:8px 6px;">Cohort</th>';
  html += '<th style="text-align:center; color:var(--text-muted); font-weight:600; padding:8px 6px;">Size</th>';
  for (let i = 0; i <= maxColsInd; i++) {
    html += `<th style="color:var(--text-muted); font-weight:600; padding:8px 6px;">M${i}</th>`;
  }
  html += '</tr></thead><tbody>';

  // Rows
  matrix.forEach(row => {
    const size = cohortSizes[row.cohort] || 0;
    html += `<tr>`;
    html += `<td style="text-align:left; font-weight:700; color:var(--text-main); padding:8px 6px; white-space:nowrap;">${row.cohort}</td>`;
    html += `<td style="font-weight:600; color:var(--text-muted); padding:8px 6px; background:#f8fafc; border-radius:4px;">${size}</td>`;

    for (let i = 0; i <= maxColsInd; i++) {
      const val = row[`month_${i}`];
      if (val == null) {
        html += `<td style="padding:8px 6px;"></td>`;
      } else {
        // Calculate Background Color based on Percentage
        // Map 0 to 100 into White to Deep Primary (#4f46e5 / var(--primary) or deep green)
        // Let's use a nice Indigo scaling gradient:
        const intensity = val / 100.0;
        const alpha = Math.max(0.05, intensity * 0.9); // prevent completely white
        const bg = `rgba(99, 102, 241, ${alpha})`;
        const color = intensity > 0.5 ? '#ffffff' : 'var(--text-main)';
        html += `<td style="background:${bg}; color:${color}; font-weight:600; padding:8px 6px; border-radius:4px;">${val.toFixed(1)}%</td>`;
      }
    }
    html += `</tr>`;
  });

  html += '</tbody></table></div>';
  container.innerHTML = html;
}

function renderForecastChart(d) {
  const ctx = document.getElementById('forecastChart');
  if (window._fcChart) window._fcChart.destroy();

  const datasets = [];

  // Theme Constants
  const colors = {
    historical: '#94a3b8', // Solid Grey
    forecast: '#818cf8',   // Indigo
    upper: '#818cf8',      // Indigo dotted/dashed
    lower: '#818cf8',      // Indigo dotted/dashed
    bg: '#0f172a',         // Deep Navy
    grid: 'rgba(255,255,255,0.05)',
    text: '#94a3b8'
  };

  // Set chart area background
  ctx.style.backgroundColor = colors.bg;
  ctx.parentElement.style.backgroundColor = colors.bg;
  ctx.parentElement.style.boxShadow = '0 10px 40px rgba(0,0,0,0.2)';
  ctx.parentElement.style.border = '1px solid rgba(255,255,255,0.05)';
  ctx.parentElement.style.borderRadius = '16px';
  ctx.parentElement.style.padding = '25px';

  // 1. Prepare Labels (Historical + Forecast)
  const histDates = (d.historical || []).map(h => h.date);
  const foreDates = (d.forecast || []).map(f => f.period || f.date);
  // Dedup and Sort
  const allLabels = [...new Set([...histDates, ...foreDates])].sort();

  // Helper to map data to labels
  const mapData = (source, dateKey, valKey) => {
    return allLabels.map(label => {
      const item = source.find(s => (s[dateKey] || s.date) === label);
      return item ? item[valKey] : null;
    });
  };

  // 2. Historical Data
  if (d.historical && d.historical.length > 0) {
    datasets.push({
      label: 'Historical',
      data: mapData(d.historical, 'date', 'value'),
      borderColor: colors.historical,
      backgroundColor: 'transparent',
      fill: false,
      tension: 0.4,
      cubicInterpolationMode: 'monotone',
      borderWidth: 2,
      pointRadius: 3,
      pointHoverRadius: 6,
      pointBackgroundColor: '#fff',
      pointBorderColor: colors.historical,
      pointBorderWidth: 2
    });
  }

  // 3. Forecast Data
  if (d.forecast && d.forecast.length > 0) {
    // We want to connect the last historical point to the first forecast point
    // So we create a merged dataset logic or just add the point to the forecast data map

    const forecastMap = new Map();
    d.forecast.forEach(f => forecastMap.set(f.period || f.date, f.value));

    // Add last historical point to bridge the gap
    if (d.historical && d.historical.length > 0) {
      const last = d.historical[d.historical.length - 1];
      forecastMap.set(last.date, last.value);
    }

    datasets.push({
      label: 'Forecast',
      data: allLabels.map(l => forecastMap.get(l) ?? null),
      borderColor: colors.forecast,
      backgroundColor: 'transparent',
      fill: false,
      borderDash: [6, 4],
      tension: 0.4,
      cubicInterpolationMode: 'monotone',
      borderWidth: 2,
      pointRadius: 4,
      pointBackgroundColor: colors.forecast,
      pointBorderColor: colors.bg,
      pointBorderWidth: 2,
      zIndex: 10
    });
  }

  // 4. Confidence Intervals
  const ciLower = d.confidence_intervals && d.confidence_intervals.lower ? d.confidence_intervals.lower : [];
  const ciUpper = d.confidence_intervals && d.confidence_intervals.upper ? d.confidence_intervals.upper : [];
  if (ciLower.length > 0 && ciUpper.length > 0) {
    // Map CI to labels
    const ciMap = new Map();
    // Reconstruct into periods from forecast
    if (d.forecast) {
      d.forecast.forEach((f, i) => {
        ciMap.set(f.period || f.date, { upper: ciUpper[i], lower: ciLower[i] });
      });
    }

    // Also add last historical point as a "zero width" CI to start the band smoothly
    if (d.historical && d.historical.length > 0) {
      const last = d.historical[d.historical.length - 1];
      ciMap.set(last.date, { upper: last.value, lower: last.value });
    }

    const upperData = allLabels.map(l => ciMap.has(l) ? ciMap.get(l).upper : null);
    const lowerData = allLabels.map(l => ciMap.has(l) ? ciMap.get(l).lower : null);

    datasets.push({
      label: 'Upper Bound',
      data: upperData,
      borderColor: colors.upper,
      borderDash: [2, 2],
      borderWidth: 1,
      fill: false,
      pointRadius: 0,
      tension: 0.4,
      cubicInterpolationMode: 'monotone'
    });
    datasets.push({
      label: 'Lower Bound',
      data: lowerData,
      borderColor: colors.lower,
      borderDash: [2, 2],
      borderWidth: 1,
      fill: false,
      pointRadius: 0,
      tension: 0.4,
      cubicInterpolationMode: 'monotone'
    });
    // The Shaded Area
    datasets.push({
      label: 'Confidence Band Area',
      data: upperData,
      fill: '-1', // Fill to Lower Bound (index - 1)
      backgroundColor: 'rgba(129, 140, 248, 0.12)',
      borderColor: 'transparent',
      pointRadius: 0,
      tension: 0.4,
      cubicInterpolationMode: 'monotone'
    });
  }

  window._fcChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: allLabels,
      datasets: datasets.filter(ds => ds.label !== 'Lower Bound' && ds.label !== 'Upper Bound') // Hide bounds from legend if desired, but keep for fill
        .map(ds => {
          // Adjust fill index if we filtered out datasets? 
          // Chart.js fill: '-1' refers to dataset index in the chart, not the source array.
          // If we filter, we break the index reference.
          // So we MUST NOT filter internal helper datasets if we want fill to work.
          // We can hide them from LEGEND instead.
          return ds;
        })
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      layout: { padding: 25 },
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: {
          display: true,
          position: 'top',
          align: 'end',
          labels: {
            boxWidth: 12,
            boxHeight: 12,
            usePointStyle: false,
            font: { size: 11, weight: '500' },
            color: colors.text,
            padding: 20,
            filter: (item) => !item.text.includes('Bound') && !item.text.includes('Area')
          }
        },
        tooltip: {
          backgroundColor: '#1e293b',
          titleColor: '#f8fafc',
          bodyColor: '#94a3b8',
          borderColor: 'rgba(255,255,255,0.1)',
          borderWidth: 1,
          padding: 10,
          cornerRadius: 8,
          callbacks: {
            label: (ctx) => `${ctx.dataset.label}: ${formatCurrency(ctx.parsed.y)} `
          }
        }
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: {
            color: colors.text,
            font: { size: 10 },
            maxRotation: 45,
            minRotation: 45,
            autoSkip: true,
            maxTicksLimit: 12
          }
        },
        y: {
          grid: { color: colors.grid, drawBorder: false, drawTicks: false },
          ticks: {
            color: '#94a3b8',
            font: { size: 10 },
            callback: v => formatCurrency(v),
            padding: 10
          },
          beginAtZero: false
        }
      }
    }
  });
}

/* ---- Executive Summary ---- */
async function loadExecutiveSummary() {
  try {
    const res = await fetch(`/api/summary/${currentDataset.table_name}`);
    if (!res.ok) throw new Error('Summary failed');
    const d = await res.json();
    if (d.error || d.detail) throw new Error(d.error || d.detail);
    let html = `<p>${(d.summary || 'No summary available.').replace(/\n/g, '<br>')}</p>`;
    if (d.next_steps && d.next_steps.length > 0) {
      html += '<ul style="margin-top:10px; padding-left:18px;">';
      d.next_steps.forEach(s => { html += `<li style="color:var(--text-gray); margin-bottom:4px; font-size:0.85rem;">${s}</li>`; });
      html += '</ul>';
    }
    document.getElementById('summaryContent').innerHTML = html;
  } catch {
    document.getElementById('summaryContent').innerHTML =
      '<p style="color:var(--text-muted);"><i class="fa-solid fa-circle-info"></i> Executive summary is being generated. Please try again in a moment.</p>';
  }
}

/* ========== CHAT ========== */
async function askQuestion() {
  const input = document.getElementById('questionInput');
  const q = input.value.trim();
  if (!q) return;
  if (!currentDataset || !currentDataset.table_name) {
    alert('Please upload a dataset first!');
    return;
  }
  const chatBox = document.getElementById('chatBox');

  const uDiv = document.createElement('div');
  uDiv.className = 'message user';
  uDiv.textContent = q;
  chatBox.appendChild(uDiv);
  input.value = '';
  chatBox.scrollTop = chatBox.scrollHeight;

  const bDiv = document.createElement('div');
  bDiv.className = 'message bot';
  bDiv.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Analyzing your data...';
  chatBox.appendChild(bDiv);
  chatBox.scrollTop = chatBox.scrollHeight;

  try {
    const res = await fetch('/api/ask', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ table_name: currentDataset.table_name, question: q })
    });
    if (!res.ok) throw new Error('Question failed');
    const d = await res.json();

    let html = '';

    // Check if the backend returned an error
    if (d.success === false || d.error) {
      html = `<p style="color:var(--amber); margin:4px 0;"><i class="fa-solid fa-triangle-exclamation"></i> ${d.error || 'AI service temporarily unavailable.'}</p>`;
    } else {
      html = `<strong>Analysis:</strong><p style="margin:4px 0;">${d.explanation || 'Query executed successfully.'}</p>`;
      if (d.results && d.results.length > 0) {
        const cols = Object.keys(d.results[0]);
        html += `<table><thead><tr>${cols.map(c => `<th>${c}</th>`).join('')}</tr></thead>
          <tbody>${d.results.slice(0, 5).map(r => `<tr>${cols.map(c => `<td>${r[c] != null ? r[c] : ''}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
        if (d.results.length > 5) html += `<small style="color:var(--text-muted);">Showing 5 of ${d.results.length} rows</small>`;
      }
      if (d.sql) {
        html += `<details style="margin-top:8px;"><summary style="cursor:pointer; color:var(--accent); font-size:0.82rem;">View SQL</summary>
          <code style="display:block; margin-top:4px; padding:8px; background:rgba(15,23,42,0.5); border-radius:6px; font-size:0.8rem; color:#94a3b8; white-space:pre-wrap;">${d.sql}</code></details>`;
      }
    }
    bDiv.innerHTML = html;
    chatBox.appendChild(bDiv);
    chatBox.scrollTop = chatBox.scrollHeight;
  } catch (err) {
    const eDiv = document.createElement('div');
    eDiv.className = 'message bot';
    eDiv.innerHTML = `<span style="color:var(--red);">AI service temporarily unavailable.</span>`;
    chatBox.appendChild(eDiv);
  }
}

/* ========== PDF EXPORT ========== */
async function exportPDF() {
  const btn = document.getElementById('exportPdfBtn');
  btn.disabled = true;
  btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Generating...';
  try {
    const res = await fetch('/api/report/export-pdf', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ table_name: currentDataset.table_name, include_forecast: true })
    });
    if (!res.ok) throw new Error('PDF export failed');
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `InsightIQ_${currentDataset.table_name}_${new Date().toISOString().split('T')[0]}.pdf`;
    document.body.appendChild(a);
    a.click(); URL.revokeObjectURL(url); a.remove();
  } catch (err) {
    alert('PDF Export Failed: ' + err.message);
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<i class="fa-solid fa-file-pdf"></i> Export PDF';
  }
}

/* ========== NAV ========== */
function goBack() {
  currentDataset = null;
  window._lastAnalyticsData = null;
  _vizPopulated = false;
  document.getElementById('landingPage').style.display = 'flex';
  document.getElementById('dashboard').style.display = 'none';
  // Reset to dashboard section for next load
  switchToSection('dashboard-section');
}

/* ========== VISUALIZATIONS SECTION ========== */
let _vizPopulated = false;
function populateVisualizationsSection(data) {
  if (_vizPopulated) return;
  _vizPopulated = true;

  const area = document.getElementById('vizChartsArea');
  if (!area) return;
  area.innerHTML = '';

  // Create a 2-col grid wrapper
  const grid = document.createElement('div');
  grid.className = 'charts-grid';
  area.appendChild(grid);

  Chart.defaults.color = '#94a3b8';
  Chart.defaults.borderColor = 'rgba(148,163,184,0.08)';
  Chart.defaults.font.family = "'Inter', sans-serif";

  // Revenue Trend
  if (data.time_series && data.time_series.dates.length > 0) {
    const ts = data.time_series;
    const sec = _vizMakeSection(grid, 'Revenue Trend', 'Monthly revenue aggregation');
    const wrap = document.createElement('div');
    wrap.style.cssText = 'height:220px; position:relative;';
    sec.appendChild(wrap);
    const canvas = document.createElement('canvas');
    wrap.appendChild(canvas);
    const ctx = canvas.getContext('2d');
    const grad = ctx.createLinearGradient(0, 0, 0, 200);
    grad.addColorStop(0, 'rgba(99,102,241,0.25)');
    grad.addColorStop(1, 'rgba(99,102,241,0)');
    new Chart(canvas, {
      type: 'line',
      data: { labels: ts.dates, datasets: [{ label: ts.value_column, data: ts.values, borderColor: '#6366f1', backgroundColor: grad, fill: true, tension: 0.35, borderWidth: 2, pointRadius: 2, pointHoverRadius: 5, pointBackgroundColor: '#6366f1', pointBorderColor: '#0f172a', pointBorderWidth: 1 }] },
      options: { ...timeChartOpts('$'), maintainAspectRatio: false }
    });
  }

  // Top Countries / Region
  if (data.top_countries && data.top_countries.labels.length > 0) {
    const tc = data.top_countries;
    const sec = _vizMakeSection(grid, `Top ${tc.labels.length} by Revenue`, tc.column);
    const wrap = document.createElement('div');
    wrap.style.cssText = 'height:220px; position:relative;';
    sec.appendChild(wrap);
    const canvas = document.createElement('canvas');
    wrap.appendChild(canvas);
    new Chart(canvas, {
      type: 'bar',
      data: { labels: tc.labels, datasets: [{ label: 'Revenue', data: tc.values, backgroundColor: ['#6366f1', '#22d3ee', '#10b981', '#f59e0b', '#a855f7'], borderRadius: 6, barThickness: 20 }] },
      options: { responsive: true, maintainAspectRatio: false, indexAxis: 'y', plugins: { legend: { display: false }, tooltip: { ...tooltipStyle(), callbacks: { label: ctx => formatCurrency(ctx.parsed.x) } } }, scales: { x: { grid: { color: 'rgba(148,163,184,0.06)' }, ticks: { font: { size: 9 }, callback: v => formatCurrency(v) } }, y: { grid: { display: false }, ticks: { font: { size: 10 } } } } }
    });
  }

  // Second row grid
  const grid2 = document.createElement('div');
  grid2.className = 'charts-grid';
  area.appendChild(grid2);

  // Category distributions (only first 2)
  const catKeys = data.category_distributions ? Object.keys(data.category_distributions).slice(0, 2) : [];
  const COLORS = ['#6366f1', '#22d3ee', '#10b981', '#f59e0b', '#f43f5e', '#a855f7', '#ec4899', '#14b8a6'];
  catKeys.forEach(catCol => {
    const dist = data.category_distributions[catCol];
    const sec = _vizMakeSection(grid2, catCol + ' Distribution', '');
    const wrap = document.createElement('div');
    wrap.style.cssText = 'height:220px; position:relative;';
    sec.appendChild(wrap);
    const canvas = document.createElement('canvas');
    wrap.appendChild(canvas);
    new Chart(canvas, {
      type: 'doughnut',
      data: { labels: dist.labels, datasets: [{ data: dist.values, backgroundColor: COLORS, borderColor: '#111827', borderWidth: 2 }] },
      options: { responsive: true, maintainAspectRatio: false, cutout: '55%', plugins: { legend: { position: 'right', labels: { boxWidth: 10, padding: 6, font: { size: 10 } } }, tooltip: tooltipStyle() } }
    });
  });

  // Third row grid
  const grid3 = document.createElement('div');
  grid3.className = 'charts-grid';
  area.appendChild(grid3);

  // Correlation
  if (data.correlation_pairs && data.correlation_pairs.length > 0) {
    const cp = data.correlation_pairs[0];
    const sec = _vizMakeSection(grid3, cp.col1 + ' vs ' + cp.col2, 'Correlation analysis');
    const wrap = document.createElement('div');
    wrap.style.cssText = 'height:220px; position:relative;';
    sec.appendChild(wrap);
    const canvas = document.createElement('canvas');
    wrap.appendChild(canvas);
    new Chart(canvas, {
      type: 'line',
      data: { labels: cp.dates, datasets: [{ label: cp.col1, data: cp.values1, borderColor: '#6366f1', borderWidth: 2, tension: 0.3, pointRadius: 1, yAxisID: 'y' }, { label: cp.col2, data: cp.values2, borderColor: '#f43f5e', borderDash: [4, 3], borderWidth: 2, tension: 0.3, pointRadius: 1, yAxisID: 'y1' }] },
      options: { responsive: true, maintainAspectRatio: false, interaction: { mode: 'index', intersect: false }, plugins: { legend: { labels: { boxWidth: 8, font: { size: 10 } } }, tooltip: tooltipStyle() }, scales: { x: { grid: { display: false }, ticks: { font: { size: 8 }, maxTicksLimit: 10 } }, y: { position: 'left', grid: { color: 'rgba(148,163,184,0.06)' }, ticks: { font: { size: 9 }, callback: v => formatCurrency(v) } }, y1: { position: 'right', grid: { display: false }, ticks: { font: { size: 9 } } } } }
    });
  }

  // Data Completeness
  if (data.column_stats) {
    const cols = Object.entries(data.column_stats);
    const sec = _vizMakeSection(grid3, 'Data Completeness', 'Column-level data quality');
    const wrap = document.createElement('div');
    wrap.style.cssText = 'height:220px; position:relative;';
    sec.appendChild(wrap);
    const canvas = document.createElement('canvas');
    wrap.appendChild(canvas);
    new Chart(canvas, {
      type: 'bar',
      data: { labels: cols.map(([name]) => name), datasets: [{ label: 'Complete %', data: cols.map(([, s]) => 100 - s.missing_percent), backgroundColor: cols.map(([, s]) => (100 - s.missing_percent) === 100 ? '#10b981' : '#f59e0b'), borderRadius: 4, barThickness: 14 }] },
      options: { responsive: true, maintainAspectRatio: false, indexAxis: 'y', plugins: { legend: { display: false }, tooltip: { ...tooltipStyle(), callbacks: { label: ctx => ctx.parsed.x.toFixed(1) + '% complete' } } }, scales: { x: { max: 100, grid: { color: 'rgba(148,163,184,0.06)' }, ticks: { font: { size: 9 }, callback: v => v + '%' } }, y: { grid: { display: false }, ticks: { font: { size: 9 } } } } }
    });
  }

  if (area.querySelector('canvas') === null) {
    area.innerHTML = '<div class="section" style="text-align:center; padding:2rem;"><p style="color:var(--text-muted);">No visualizations available. Upload a dataset first.</p></div>';
  }
}

function _vizMakeSection(parent, title, subtitle) {
  const sec = document.createElement('div');
  sec.className = 'section';
  sec.style.marginBottom = '1rem';
  const h3 = document.createElement('h3');
  h3.className = 'section-title';
  h3.style.fontSize = '0.95rem';
  h3.textContent = title;
  sec.appendChild(h3);
  if (subtitle) {
    const sub = document.createElement('p');
    sub.className = 'section-subtitle';
    sub.style.fontSize = '0.78rem';
    sub.textContent = subtitle;
    sec.appendChild(sub);
  }
  parent.appendChild(sec);
  return sec;
}

console.log('InsightIQ App.js Loaded - Version 3.2 (Gemini AI)');
