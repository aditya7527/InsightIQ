console.log('app.js loaded - START');

let currentDataset = null;
let charts = {};
let form = null;

// Catch all errors
window.onerror = function(msg, url, lineNo, columnNo, error) {
  console.error('ERROR:', msg, 'at', lineNo + ':' + columnNo, error);
  const debugPanel = document.getElementById('debugPanel');
  if (debugPanel) {
    debugPanel.style.display = 'block';
    const debugOutput = document.getElementById('debugOutput');
    const errLine = document.createElement('div');
    errLine.textContent = '❌ ERROR: ' + msg;
    errLine.style.color = '#f00';
    debugOutput.appendChild(errLine);
  }
  return false;
};

function debug(msg) {
  console.log(msg);
  try {
    const debugPanel = document.getElementById('debugPanel');
    if (debugPanel) {
      debugPanel.style.display = 'block';
      const debugOutput = document.getElementById('debugOutput');
      if (debugOutput) {
        const line = document.createElement('div');
        line.textContent = msg;
        debugOutput.appendChild(line);
      }
    }
  } catch (e) {
    console.error('Debug function error:', e);
  }
}

debug('🔧 app.js: Script loaded');

let currentDataset = null;
let charts = {};
let form = null;

debug('🔧 app.js: Script loaded');

// Wait for DOM to load
document.addEventListener('DOMContentLoaded', () => {
  debug('📍 DOMContentLoaded fired');
  form = document.getElementById('uploadForm');
  debug('Form element: ' + (form ? 'FOUND' : 'NOT FOUND'));
  
  // Test: Auto-fetch analytics on page load to verify renderinng works
  if (window.location.search.includes('test=1')) {
    debug('🧪 TEST MODE: Auto-fetching analytics...');
    testLoadAnalytics();
    return;
  }
  
  if (!form) {
    debug('❌ ERROR: Form element not found!');
    return;
  }

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    debug('📤 Form submitted');
    
    const uploadBtn = document.getElementById('uploadBtn');
    uploadBtn.disabled = true;
    uploadBtn.textContent = '⏳ Uploading...';

    try {
      const fd = new FormData(form);
      debug('📦 FormData prepared');
      
      const response = await fetch('/api/upload', { method: 'POST', body: fd });
      debug('Response status: ' + response.status);
      
      const data = await response.json();
      debug('📥 Upload response received');
      debug('Dataset name: ' + data.metadata.name);
      debug('Table name: ' + data.metadata.table_name);

      if (!response.ok) {
        throw new Error(data.detail || data.error || 'Upload failed');
      }

      currentDataset = data.metadata;
      debug('✓ currentDataset set');
      debug('🔄 Calling loadDashboard()');
      
      showStatus('✓ Dataset uploaded successfully! Generating insights...', 'success');
      
      // Load analytics after upload
      await loadDashboard();
      debug('✓ loadDashboard() completed');
      
      // Hide upload, show dashboard
      document.querySelector('.upload-section').style.display = 'none';
      document.getElementById('dashboard').style.display = 'block';
      debug('✓ Dashboard now visible');
      
      // Scroll to dashboard
      setTimeout(() => {
        document.getElementById('dashboard').scrollIntoView({ behavior: 'smooth' });
      }, 100);
      
      // Reset form
      form.reset();
    } catch (error) {
      debug('❌ Error: ' + error.message);
      console.error('Error:', error);
      showStatus('✗ Error: ' + error.message, 'error');
    } finally {
      uploadBtn.disabled = false;
      uploadBtn.textContent = 'Upload & Analyze';
    }
  });
});

function showStatus(message, type) {
  const statusEl = document.getElementById('uploadStatus');
  statusEl.textContent = message;
  statusEl.className = type;
  statusEl.style.display = 'block';
}

async function loadDashboard() {
  try {
    debug('📊 loadDashboard() starting');
    const metadata = currentDataset;
    debug('metadata available: ' + !!metadata);
    
    // Update basic info with animation
    animateValue('dsName', '', metadata.name);
    animateValue('dsRows', '0', metadata.rows.toLocaleString());
    animateValue('dsColumns', '0', Object.keys(metadata.schema).length);
    debug('✓ Values animated');
    
    // Get analytics data
    debug('📡 Fetching analytics...');
    const analyticsData = await fetchAnalytics();
    debug('✓ Analytics data: ' + Object.keys(analyticsData).join(', '));
    
    // Render statistics table
    renderStatsTable(metadata.schema, analyticsData);
    debug('✓ Stats table rendered');
    
    // Render numeric summary if available
    if (analyticsData.numeric_summary && analyticsData.numeric_summary.length > 0) {
      document.getElementById('numericSummary').style.display = 'block';
      renderNumericSummary(analyticsData.numeric_summary);
      debug('✓ Numeric summary rendered');
    }
    
    // Generate charts
    generateCharts(analyticsData);
    debug('✓ Charts generated');
    
    // Generate insights
    generateInsights(analyticsData, metadata);
    debug('✓ Insights generated');
    
    debug('✅ Dashboard fully loaded');
  } catch (error) {
    debug('❌ loadDashboard error: ' + error.message);
    console.error('Error loading dashboard:', error);
    throw error;
  }
}

function animateValue(elementId, start, end) {
  const element = document.getElementById(elementId);
  if (!element) return;
  
  // If end is not a number, just set it
  if (isNaN(end)) {
    element.textContent = end;
    element.style.animation = 'slideIn 0.3s ease-out';
    return;
  }
  
  const startNum = parseInt(start) || 0;
  const endNum = parseInt(end.replace(/,/g, '')) || 0;
  const duration = 1000;
  const increment = (endNum - startNum) / (duration / 16);
  let current = startNum;
  
  const timer = setInterval(() => {
    current += increment;
    if (current >= endNum) {
      current = endNum;
      clearInterval(timer);
    }
    element.textContent = Math.floor(current).toLocaleString();
  }, 16);
}

async function fetchAnalytics() {
  try {
    const url = `/api/analytics/${currentDataset.table_name}`;
    debug('🔗 Analytics URL: ' + url);
    
    const response = await fetch(url);
    debug('📊 Analytics response: ' + response.status);
    
    if (!response.ok) {
      throw new Error(`Analytics request failed with status ${response.status}`);
    }
    
    const data = await response.json();
    debug('✓ Analytics JSON parsed');
    return data;
  } catch (error) {
    console.error('Error fetching analytics:', error);
    showStatus('⚠️ Warning: Could not fetch analytics: ' + error.message, 'error');
    return {};
  }
}

function renderStatsTable(schema, analytics) {
  const statsBody = document.getElementById('statsBody');
  statsBody.innerHTML = '';
  
  const columnStats = analytics.column_stats || {};
  
  for (const [col, dtype] of Object.entries(schema)) {
    const stats = columnStats[col] || {};
    const row = document.createElement('tr');
    row.innerHTML = `
      <td><strong>${col}</strong></td>
      <td>${dtype.split('[')[0]}</td>
      <td>${stats.non_null_count || '-'}</td>
      <td>${stats.missing_percent ? stats.missing_percent.toFixed(1) + '%' : '-'}</td>
    `;
    statsBody.appendChild(row);
  }
}

function renderNumericSummary(numericSummary) {
  const numericBody = document.getElementById('numericBody');
  numericBody.innerHTML = '';
  
  numericSummary.forEach(col => {
    const row = document.createElement('tr');
    row.innerHTML = `
      <td><strong>${col.name}</strong></td>
      <td>${col.min !== null ? col.min.toFixed(2) : '-'}</td>
      <td>${col.max !== null ? col.max.toFixed(2) : '-'}</td>
      <td>${col.mean !== null ? col.mean.toFixed(2) : '-'}</td>
      <td>${col.median !== null ? col.median.toFixed(2) : '-'}</td>
      <td>${col.std !== null ? col.std.toFixed(2) : '-'}</td>
    `;
    numericBody.appendChild(row);
  });
}

function generateCharts(analyticsData) {
  try {
    console.log('Skipping chart generation temporarily for debugging');
    const chartsGrid = document.getElementById('chartsGrid');
    if (chartsGrid) {
      chartsGrid.innerHTML = '<p style="padding: 20px; text-align: center; color: #666;">Charts rendering ...</p>';
    }
  } catch (error) {
    console.error('Error in generateCharts:', error);
  }
}

function createDistributionChart(numericSummary) {
  try {
    const ctx = document.getElementById('distributionChart');
    if (!ctx) {
      console.error('distributionChart canvas not found');
      return;
    }
    
    console.log('Creating distribution chart with', numericSummary.length, 'columns');
    
    const labels = numericSummary.map(col => col.name);
    const means = numericSummary.map(col => col.mean || 0);
    const mins = numericSummary.map(col => col.min || 0);
    const maxs = numericSummary.map(col => col.max || 0);
    
    charts.distribution = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [
          {
            label: 'Minimum',
            data: mins,
            backgroundColor: 'rgba(255, 99, 132, 0.5)',
            borderColor: 'rgba(255, 99, 132, 1)',
            borderWidth: 1,
          },
          {
            label: 'Mean',
            data: means,
            backgroundColor: 'rgba(102, 126, 234, 0.5)',
            borderColor: 'rgba(102, 126, 234, 1)',
            borderWidth: 1,
          },
          {
            label: 'Maximum',
            data: maxs,
            backgroundColor: 'rgba(75, 192, 75, 0.5)',
            borderColor: 'rgba(75, 192, 75, 1)',
            borderWidth: 1,
          },
        ]
      },
      options: {
        responsive: true,
        plugins: { legend: { display: true } },
        scales: { y: { beginAtZero: true } }
      }
    });
    console.log('Distribution chart created successfully');
  } catch (error) {
    console.error('Error creating distribution chart:', error);
  }
}

function createMissingDataChart(columnStats) {
  try {
    const ctx = document.getElementById('missingChart');
    if (!ctx) {
      console.error('missingChart canvas not found');
      return;
    }
    
    const columns = Object.keys(columnStats);
    const missingPercents = columns.map(col => columnStats[col].missing_percent || 0);
    
    console.log('Creating missing data chart for', columns.length, 'columns');
    
    charts.missing = new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: columns,
        datasets: [{
          data: missingPercents,
          backgroundColor: [
            'rgba(255, 99, 132, 0.6)',
            'rgba(255, 159, 64, 0.6)',
            'rgba(255, 205, 86, 0.6)',
            'rgba(75, 192, 75, 0.6)',
            'rgba(102, 126, 234, 0.6)',
            'rgba(153, 102, 255, 0.6)',
          ],
          borderColor: [
            'rgba(255, 99, 132, 1)',
            'rgba(255, 159, 64, 1)',
            'rgba(255, 205, 86, 1)',
            'rgba(75, 192, 75, 1)',
            'rgba(102, 126, 234, 1)',
            'rgba(153, 102, 255, 1)',
          ],
          borderWidth: 1,
        }]
      },
      options: {
        responsive: true,
        plugins: { legend: { display: true, position: 'bottom' } }
      }
    });
    console.log('Missing data chart created successfully');
  } catch (error) {
    console.error('Error creating missing data chart:', error);
  }
}

function createDataTypeChart(schema) {
  try {
    const ctx = document.getElementById('typeChart');
    if (!ctx) {
      console.error('typeChart canvas not found');
      return;
    }
    
    const typeCount = {};
    for (const dtype of Object.values(schema)) {
      const cleanType = dtype.split('[')[0].trim();
      typeCount[cleanType] = (typeCount[cleanType] || 0) + 1;
    }
    
    console.log('Creating data type chart with types:', Object.keys(typeCount));
    
    charts.types = new Chart(ctx, {
      type: 'pie',
      data: {
        labels: Object.keys(typeCount),
        datasets: [{
          data: Object.values(typeCount),
          backgroundColor: [
            'rgba(102, 126, 234, 0.6)',
            'rgba(255, 99, 132, 0.6)',
            'rgba(75, 192, 75, 0.6)',
            'rgba(255, 159, 64, 0.6)',
          ],
          borderColor: [
            'rgba(102, 126, 234, 1)',
            'rgba(255, 99, 132, 1)',
            'rgba(75, 192, 75, 1)',
            'rgba(255, 159, 64, 1)',
          ],
          borderWidth: 1,
        }]
      },
      options: {
        responsive: true,
        plugins: { legend: { display: true, position: 'bottom' } }
      }
    });
    console.log('Data type chart created successfully');
  } catch (error) {
    console.error('Error creating data type chart:', error);
  }
}

function generateInsights(analyticsData, metadata) {
  const insightsBox = document.getElementById('insights');
  const insights = [];
  
  // Total records insight
  insights.push({
    icon: '📊',
    title: 'Dataset Size',
    description: `Your dataset contains ${metadata.rows.toLocaleString()} records across ${Object.keys(metadata.schema).length} columns.`
  });
  
  // Data quality insight
  const columnStats = analyticsData.column_stats || {};
  const totalColumns = Object.keys(columnStats).length;
  const completeColumns = Object.values(columnStats).filter(s => (s.missing_percent || 0) === 0).length;
  
  if (totalColumns > 0) {
    insights.push({
      icon: '✓',
      title: 'Data Quality',
      description: `${completeColumns} out of ${totalColumns} columns have no missing values. Overall data quality is good.`
    });
  }
  
  // Numeric columns insight
  const numericSummary = analyticsData.numeric_summary || [];
  if (numericSummary.length > 0) {
    const avgValue = (numericSummary.reduce((sum, col) => sum + (col.mean || 0), 0) / numericSummary.length).toFixed(2);
    insights.push({
      icon: '🔢',
      title: 'Numeric Analysis',
      description: `Analyzed ${numericSummary.length} numeric columns with an average mean value of ${avgValue}.`
    });
  }
  
  // Data type insight
  const schema = metadata.schema;
  const typeCount = {};
  for (const dtype of Object.values(schema)) {
    const cleanType = dtype.split('[')[0].trim();
    typeCount[cleanType] = (typeCount[cleanType] || 0) + 1;
  }
  const dominantType = Object.entries(typeCount).sort((a, b) => b[1] - a[1])[0];
  
  insights.push({
    icon: '📋',
    title: 'Dominant Data Type',
    description: `Most of your columns (${dominantType[1]}) are of type "${dominantType[0]}".`
  });
  
  // Recommendations
  insights.push({
    icon: '💡',
    title: 'Recommendations',
    description: 'Consider data normalization for numeric columns. Use this data for predictive modeling or trend analysis.'
  });
  
  // Render insights
  insightsBox.innerHTML = insights.map(insight => `
    <div class="insight-item">
      <div class="insight-icon">${insight.icon}</div>
      <div class="insight-text">
        <strong>${insight.title}</strong>
        <span>${insight.description}</span>
      </div>
    </div>
  `).join('');
}

function goBack() {
  // Clear current dataset
  currentDataset = null;
  charts = {};
  
  // Show upload section, hide dashboard
  document.querySelector('.upload-section').style.display = 'block';
  document.getElementById('dashboard').style.display = 'none';
  
  // Clear status
  document.getElementById('uploadStatus').innerHTML = '';
  document.getElementById('uploadStatus').className = '';
}
// Test function to verify rendering works
async function testLoadAnalytics() {
  try {
    debug('🧪 Fetching test analytics...');
    const response = await fetch('/api/analytics/dataset_28b98f2fb6b04acba983709c69ed9867');
    
    if (!response.ok) {
      debug('❌ Test fetch failed: ' + response.status);
      return;
    }
    
    const analyticsData = await response.json();
    debug('✓ Test data received, rendering...');
    
    // Set test dataset
    currentDataset = {
      name: 'Test Dataset',
      rows: 10,
      table_name: 'dataset_28b98f2fb6b04acba983709c69ed9867',
      schema: {ID:'int64', Name:'object', Age:'int64', Salary:'int64', Department:'object'}
    };
    
    // Show dashboard
    document.querySelector('.upload-section').style.display = 'none';
    document.getElementById('dashboard').style.display = 'block';
    debug('✓ Dashboard visible');
    
    // Set values
    animateValue('dsName', '', 'Test Dataset');
    animateValue('dsRows', '0', '10');
    animateValue('dsColumns', '0', '5');
    debug('✓ Values animated');
    
    // Render
    renderStatsTable(currentDataset.schema, analyticsData);
    generateCharts(analyticsData);
    generateInsights(analyticsData, currentDataset);
    debug('✅ Test rendering complete');
  } catch (error) {
    debug('❌ Test error: ' + error.message);
    console.error(error);
  }
}