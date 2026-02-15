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
        dz.querySelector('h3').textContent = this.files[0].name;
        dz.querySelector('p').textContent = (this.files[0].size / 1024).toFixed(1) + ' KB';
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
function formatCurrency(n) {
  if (n == null) return '—';
  return '$' + formatNumber(n);
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
  console.log('switchToSection called:', sectionId);
  // Hide all content sections
  document.querySelectorAll('.content-section').forEach(sec => sec.classList.remove('active'));
  // Show target section
  const target = document.getElementById(sectionId);
  if (target) {
    target.classList.add('active');
  } else {
    console.warn('Section not found:', sectionId);
    return;
  }
  // Update sidebar highlight
  document.querySelectorAll('.sidebar-link').forEach(l => l.classList.remove('active'));
  if (clickedLink) {
    clickedLink.classList.add('active');
  }
  // Populate visualizations on demand
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
    if (!res.ok) throw new Error('Upload failed: ' + res.status);
    const data = await res.json();
    currentDataset = data.metadata;
    document.getElementById('landingPage').style.display = 'none';
    document.getElementById('dashboard').style.display = 'block';
    await loadDashboard();
  } catch (err) {
    status.textContent = 'Error: ' + err.message;
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
    <div class="metric-card highlight" id="confidenceCard">
      <div class="metric-top"><div>
        <div class="metric-label">Confidence Score</div>
        <div class="metric-value" id="confidenceScore" style="font-size:2.2rem;">—</div>
      </div><div class="metric-icon" style="background:rgba(255,255,255,0.15); color:#fff;"><i class="fa-solid fa-shield-check"></i></div></div>
      <small id="confidenceLabel">Loading...</small>
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
      options: timeChartOpts('$')
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
  await safe(loadForecasts);
  await safe(loadExecutiveSummary);
}

/* ---- Confidence Score ---- */
async function loadConfidenceScore() {
  const res = await fetch(`/api/confidence/${currentDataset.table_name}`);
  if (!res.ok) return;
  const d = await res.json();
  document.getElementById('confidenceScore').textContent = d.confidence_score + '%';
  document.getElementById('confidenceLabel').textContent = d.confidence_score_quality;
}

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
  // Auto-detect columns from schema
  const schema = currentDataset.schema || {};
  const numCols = Object.keys(schema)
    .filter(c => schema[c].includes('int') || schema[c].includes('float'));
  const groupCols = Object.keys(schema)
    .filter(c => !schema[c].includes('int') && !schema[c].includes('float'))
    .filter(c => !(/id|no|code/i.test(c)))  // exclude IDs from grouping
    .slice(0, 2);

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
    html += `<div style="margin-bottom:12px; padding:12px 14px; background:rgba(99,102,241,0.06); border-radius:10px; border:1px solid rgba(99,102,241,0.12);">
      <p style="color:var(--text-gray); font-size:0.85rem; line-height:1.5; margin:0;">${d.insight_summary}</p>
    </div>`;
  }

  // Show period info
  if (d.period) {
    html += `<p style="color:var(--text-muted); font-size:0.78rem; margin-bottom:8px;">Comparing <strong style="color:var(--text-white);">${d.period.previous}</strong> → <strong style="color:var(--text-white);">${d.period.latest}</strong></p>`;
  }

  // Show drivers
  html += '<div style="display:grid; gap:8px;">';
  if (d.top_drivers && d.top_drivers.length > 0) {
    d.top_drivers.forEach(dr => {
      const name = dr.driver || 'Unknown driver';
      const pct = dr.contribution_percent != null ? dr.contribution_percent.toFixed(1) : '0.0';
      const dir = dr.direction || 'positive';
      const iconClass = dir === 'negative' ? 'fa-arrow-trend-down' : 'fa-chart-line';
      const badgeColor = dir === 'negative' ? 'background:var(--red-bg); color:var(--red);' : 'background:var(--green-bg); color:var(--green);';
      const desc = dr.group_name || `${pct}% impact`;

      html += `
        <div class="driver-card">
          <div class="driver-icon" style="${dir === 'negative' ? 'background:var(--red-bg); color:var(--red);' : ''}"><i class="fa-solid ${iconClass}"></i></div>
          <div class="driver-info">
            <strong>${name}</strong>
            <span class="driver-badge" style="${badgeColor}">${dir === 'negative' ? '-' : '+'}${pct}%</span>
            <small>${desc}</small>
          </div>
        </div>`;
    });
  } else {
    html += '<p style="color:var(--text-muted);">No significant drivers identified.</p>';
  }
  html += '</div>';

  // Show recommendations
  if (d.recommendations && d.recommendations.length > 0) {
    html += `<div style="margin-top:14px; padding:12px 14px; background:rgba(99,102,241,0.06); border-radius:10px; border:1px solid rgba(99,102,241,0.12);">
      <strong style="color:var(--accent-light);"><i class="fa-solid fa-lightbulb"></i> Recommendations</strong>
      <ul style="margin:6px 0 0 16px; color:var(--text-gray); font-size:0.82rem; line-height:1.6;">
        ${d.recommendations.slice(0, 4).map(r => `<li>${r}</li>`).join('')}
      </ul></div>`;
  }

  document.getElementById('rootCauseContent').innerHTML = html;
}

/* ---- Forecasting ---- */
async function loadForecasts() {
  const res = await fetch('/api/forecast', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ table_name: currentDataset.table_name, periods: 3, method: 'linear' })
  });
  if (!res.ok) {
    document.getElementById('forecastSection').classList.add('hidden');
    return;
  }
  const d = await res.json();

  // Show message if insufficient data
  if (d.message && (!d.forecast || d.forecast.length === 0)) {
    document.getElementById('forecastTable').innerHTML = `
      <div style="padding:14px; background:rgba(245,158,11,0.08); border-radius:10px; border:1px solid rgba(245,158,11,0.15); margin-top:10px;">
        <p style="color:var(--amber); font-size:0.88rem; margin:0;"><i class="fa-solid fa-info-circle"></i> ${d.message}</p>
      </div>`;
    // Still show historical if available
    if (d.historical && d.historical.length > 0) {
      renderForecastChart(d);
    }
    return;
  }

  if (d.forecast && d.forecast.length > 0) {
    renderForecastChart(d);

    // Forecast table
    document.getElementById('forecastTable').innerHTML = `
      <table class="forecast-table">
        <thead><tr><th>Period</th><th>Predicted Revenue</th><th>Confidence</th></tr></thead>
        <tbody>${d.forecast.map((f, i) => {
      const band = d.confidence_band && d.confidence_band[i] ? d.confidence_band[i] : null;
      const conf = band ? `${formatCurrency(band.lower)} — ${formatCurrency(band.upper)}` : '—';
      return `<tr><td>${f.period || f.date}</td><td>${formatCurrency(f.predicted_value)}</td><td style="font-size:0.8rem;color:var(--text-muted)">${conf}</td></tr>`;
    }).join('')}</tbody>
      </table>
      ${d.r_squared != null ? `<p style="margin-top:6px;color:var(--text-muted);font-size:0.78rem;">Model R²: ${d.r_squared} · Method: ${d.method || 'linear_regression'}</p>` : ''}`;
  } else {
    document.getElementById('forecastSection').classList.add('hidden');
  }
}

function renderForecastChart(d) {
  const ctx = document.getElementById('forecastChart');
  if (window._fcChart) window._fcChart.destroy();

  const datasets = [];

  // Historical data
  if (d.historical && d.historical.length > 0) {
    datasets.push({
      label: 'Historical',
      data: d.historical.map(h => ({ x: h.date, y: h.value })),
      borderColor: '#94a3b8', backgroundColor: 'rgba(148,163,184,0.08)',
      fill: true, tension: 0.3, borderWidth: 2,
      pointRadius: 3, pointBackgroundColor: '#94a3b8',
      pointBorderColor: '#0f172a', pointBorderWidth: 2
    });
  }

  // Forecast data
  if (d.forecast && d.forecast.length > 0) {
    // Connect the last historical point to the forecast
    const bridgeData = [];
    if (d.historical && d.historical.length > 0) {
      const lastHist = d.historical[d.historical.length - 1];
      bridgeData.push({ x: lastHist.date, y: lastHist.value });
    }
    d.forecast.forEach(f => bridgeData.push({ x: f.date || f.period, y: f.predicted_value }));

    const grad2 = ctx.getContext('2d').createLinearGradient(0, 0, 0, 350);
    grad2.addColorStop(0, 'rgba(99,102,241,0.25)');
    grad2.addColorStop(1, 'rgba(99,102,241,0)');

    datasets.push({
      label: 'Forecast',
      data: bridgeData,
      borderColor: '#6366f1', backgroundColor: grad2,
      fill: true, tension: 0.3, borderWidth: 2.5,
      borderDash: [6, 3],
      pointRadius: 4, pointBackgroundColor: '#6366f1',
      pointBorderColor: '#0f172a', pointBorderWidth: 2
    });
  }

  // Confidence band
  if (d.confidence_band && d.confidence_band.length > 0 && d.historical) {
    const lastHist = d.historical[d.historical.length - 1];
    const upperData = [{ x: lastHist.date, y: lastHist.value }];
    const lowerData = [{ x: lastHist.date, y: lastHist.value }];
    d.confidence_band.forEach(cb => {
      upperData.push({ x: cb.date, y: cb.upper });
      lowerData.push({ x: cb.date, y: cb.lower });
    });

    datasets.push({
      label: 'Upper Bound',
      data: upperData,
      borderColor: 'rgba(99,102,241,0.3)', backgroundColor: 'rgba(99,102,241,0.08)',
      fill: '+1', borderWidth: 1, borderDash: [2, 2],
      pointRadius: 0
    });
    datasets.push({
      label: 'Lower Bound',
      data: lowerData,
      borderColor: 'rgba(99,102,241,0.3)', backgroundColor: 'transparent',
      fill: false, borderWidth: 1, borderDash: [2, 2],
      pointRadius: 0
    });
  }

  const allLabels = [];
  if (d.historical) d.historical.forEach(h => { if (!allLabels.includes(h.date)) allLabels.push(h.date); });
  if (d.forecast) d.forecast.forEach(f => { const dt = f.date || f.period; if (!allLabels.includes(dt)) allLabels.push(dt); });

  window._fcChart = new Chart(ctx, {
    type: 'line',
    data: { labels: allLabels, datasets },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { labels: { boxWidth: 10, font: { size: 11 } } },
        tooltip: tooltipStyle()
      },
      scales: {
        x: { grid: { display: false }, ticks: { color: '#64748b', font: { size: 10 } } },
        y: {
          grid: { color: 'rgba(148,163,184,0.06)' },
          ticks: { color: '#64748b', font: { size: 10 }, callback: v => formatCurrency(v) },
          title: { display: true, text: d.value_column || 'Revenue', color: '#94a3b8' }
        }
      }
    }
  });
}

/* ---- Executive Summary ---- */
async function loadExecutiveSummary() {
  try {
    const res = await fetch(`/api/summary/${currentDataset.table_name}`);
    if (!res.ok) throw new Error('');
    const d = await res.json();
    let html = `<p>${(d.summary || 'No summary available.').replace(/\n/g, '<br>')}</p>`;
    if (d.next_steps && d.next_steps.length > 0) {
      html += '<ul style="margin-top:10px; padding-left:18px;">';
      d.next_steps.forEach(s => { html += `<li style="color:var(--text-gray); margin-bottom:4px; font-size:0.85rem;">${s}</li>`; });
      html += '</ul>';
    }
    document.getElementById('summaryContent').innerHTML = html;
  } catch {
    document.getElementById('summaryContent').innerHTML = '<p style="color:var(--text-muted);">Executive summary requires OpenAI API key.</p>';
  }
}

/* ========== CHAT ========== */
async function askQuestion() {
  const input = document.getElementById('questionInput');
  const q = input.value.trim();
  if (!q) return;
  const chatBox = document.getElementById('chatBox');

  const uDiv = document.createElement('div');
  uDiv.className = 'message user';
  uDiv.textContent = q;
  chatBox.appendChild(uDiv);
  input.value = '';
  chatBox.scrollTop = chatBox.scrollHeight;

  try {
    const res = await fetch('/api/ask', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ table_name: currentDataset.table_name, question: q })
    });
    if (!res.ok) throw new Error('Question failed');
    const d = await res.json();

    const bDiv = document.createElement('div');
    bDiv.className = 'message bot';

    let html = '';

    // Check if the backend returned an error
    if (d.success === false || d.error) {
      html = `<p style="color:var(--amber); margin:4px 0;"><i class="fa-solid fa-triangle-exclamation"></i> ${d.error || 'Could not process your question. Try rephrasing it.'}</p>`;
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
    eDiv.innerHTML = `<span style="color:var(--red);">Error: ${err.message}</span>`;
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
