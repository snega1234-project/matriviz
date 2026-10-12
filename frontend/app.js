/**
 * DataVista Frontend Application
 * Connects directly to the Python Flask Modular Backend (api.py + analysis.py)
 * Purely upload-driven: Direct CSV column mapping without aggregation.
 * Streams in-memory Seaborn charts (bytes/base64) and automatically deletes uploaded files on refresh.
 */

const API_BASE = 'http://127.0.0.1:5000/api';

// Application State
const state = {
  activeFileName: '',      // Internal server-stored filename (e.g., uuid_data.csv)
  displayName: '',         // Original user filename (e.g., data.csv)
  columns: [],
  numericColumns: [],
  categoricalColumns: [],
  previewRows: [],
  totalRows: 0,
  totalCols: 0,
  selectedX: '',
  selectedY: '',
  chartType: 'bar',
  palette: 'berry',        // Maps to Seaborn mako in analysis.py
  viewMode: 'seaborn',     // 'seaborn' (in-memory bytes) or 'interactive'
  chartInstance: null,
  currentChartBase64: '',
  savedCharts: [],
  backendConnected: false
};

// DOM Elements
const backendStatusPill = document.getElementById('backendStatusPill');
const backendStatusText = document.getElementById('backendStatusText');

const dropZone = document.getElementById('dropZone');
const csvFileInput = document.getElementById('csvFileInput');
const fileInfoCard = document.getElementById('fileInfoCard');
const loadedFileName = document.getElementById('loadedFileName');
const loadedFileSize = document.getElementById('loadedFileSize');
const removeFileBtn = document.getElementById('removeFileBtn');

const xAxisSelect = document.getElementById('xAxisSelect');
const yAxisSelect = document.getElementById('yAxisSelect');
const chartTypeList = document.getElementById('chartTypeList');
const paletteSelector = document.getElementById('paletteSelector');
const saveChartBtn = document.getElementById('saveChartBtn');
const savedChartsList = document.getElementById('savedChartsList');
const savedCountBadge = document.getElementById('savedCountBadge');

const statRowCount = document.getElementById('statRowCount');
const statColCount = document.getElementById('statColCount');
const statSumValue = document.getElementById('statSumValue');
const statAvgValue = document.getElementById('statAvgValue');

const activeChartTitle = document.getElementById('activeChartTitle');
const activeChartSubtitle = document.getElementById('activeChartSubtitle');
const seabornChartImg = document.getElementById('seabornChartImg');
const mainChartCanvas = document.getElementById('mainChartCanvas');
const chartLoadingOverlay = document.getElementById('chartLoadingOverlay');
const chartPlaceholder = document.getElementById('chartPlaceholder');
const viewToggleBtn = document.getElementById('viewToggleBtn');
const exportPngBtn = document.getElementById('exportPngBtn');

const dataTable = document.getElementById('dataTable');
const tableHead = document.getElementById('tableHead');
const tableBody = document.getElementById('tableBody');
const tableSearchInput = document.getElementById('tableSearchInput');
const previewRowBadge = document.getElementById('previewRowBadge');

const themeToggleBtn = document.getElementById('themeToggleBtn');
const toastContainer = document.getElementById('toastContainer');

/* --------------------------------------------------------------------------
   Initialization & Refresh Cleanup Hooks
   -------------------------------------------------------------------------- */
document.addEventListener('DOMContentLoaded', () => {
  setupEventListeners();
  checkBackendHealth();
  loadSavedChartsFromStorage();
  setupRefreshCleanup();
});

/**
 * Ensures that whenever the page is refreshed, closed, or navigated away,
 * the active CSV file in backend/uploads is deleted from server storage!
 */
function setupRefreshCleanup() {
  const triggerCleanup = () => {
    if (state.activeFileName) {
      const payload = JSON.stringify({ filename: state.activeFileName });
      const blob = new Blob([payload], { type: 'application/json' });
      if (navigator.sendBeacon) {
        navigator.sendBeacon(`${API_BASE}/cleanup`, blob);
      } else {
        fetch(`${API_BASE}/cleanup`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: payload,
          keepalive: true
        });
      }
    }
  };

  window.addEventListener('beforeunload', triggerCleanup);
  window.addEventListener('pagehide', triggerCleanup);
}

function setupEventListeners() {
  // Drag and drop
  ['dragenter', 'dragover'].forEach(name => {
    dropZone.addEventListener(name, (e) => {
      e.preventDefault();
      dropZone.classList.add('drag-active');
    });
  });

  ['dragleave', 'drop'].forEach(name => {
    dropZone.addEventListener(name, (e) => {
      e.preventDefault();
      dropZone.classList.remove('drag-active');
    });
  });

  dropZone.addEventListener('drop', handleFileDrop);
  csvFileInput.addEventListener('change', handleFileSelect);
  removeFileBtn.addEventListener('click', clearData);

  // Axes changes
  xAxisSelect.addEventListener('change', (e) => {
    state.selectedX = e.target.value;
    triggerVisualizationRequest();
  });

  yAxisSelect.addEventListener('change', (e) => {
    state.selectedY = e.target.value;
    triggerVisualizationRequest();
  });

  // Chart type selection
  chartTypeList.addEventListener('click', (e) => {
    const card = e.target.closest('.chart-type-card');
    if (!card) return;

    chartTypeList.querySelectorAll('.chart-type-card').forEach(c => c.classList.remove('active'));
    card.classList.add('active');

    state.chartType = card.dataset.chartType;
    triggerVisualizationRequest();
  });

  // Color Palette
  paletteSelector.addEventListener('click', (e) => {
    const swatch = e.target.closest('.palette-swatch');
    if (!swatch) return;

    paletteSelector.querySelectorAll('.palette-swatch').forEach(s => s.classList.remove('active'));
    swatch.classList.add('active');

    state.palette = swatch.dataset.palette;
    triggerVisualizationRequest();
  });

  // View Mode Toggle (Seaborn vs Interactive Canvas)
  viewToggleBtn.addEventListener('click', toggleViewMode);

  // Save to Chart List
  saveChartBtn.addEventListener('click', saveCurrentChart);

  // Export PNG
  exportPngBtn.addEventListener('click', exportChartPNG);

  // Table Search
  tableSearchInput.addEventListener('input', handleTableSearch);

  // Theme Toggle
  themeToggleBtn.addEventListener('click', toggleTheme);
}

/* --------------------------------------------------------------------------
   Backend Connectivity & Health Check
   -------------------------------------------------------------------------- */
async function checkBackendHealth() {
  try {
    const res = await fetch(`${API_BASE}/health`);
    if (res.ok) {
      const data = await res.json();
      state.backendConnected = true;
      if (backendStatusPill) backendStatusPill.classList.remove('error');
      if (backendStatusText) backendStatusText.textContent = 'Backend: Connected';
      console.log('Backend connected:', data);
    } else {
      throw new Error('Non-200 response');
    }
  } catch (err) {
    state.backendConnected = false;
    if (backendStatusPill) backendStatusPill.classList.add('error');
    if (backendStatusText) backendStatusText.textContent = 'Backend Offline';
    showToast('Backend server is not running on port 5000', 'error');
  }
}

/* --------------------------------------------------------------------------
   File Upload to Backend
   -------------------------------------------------------------------------- */
function handleFileDrop(e) {
  const files = e.dataTransfer.files;
  if (!files || files.length === 0) return;
  uploadFileToBackend(files[0]);
}

function handleFileSelect(e) {
  const file = e.target.files[0];
  if (!file) return;
  uploadFileToBackend(file);
}

async function uploadFileToBackend(file) {
  if (!file.name.toLowerCase().endsWith('.csv')) {
    showToast('Only .csv files are supported!', 'error');
    return;
  }

  // Cleanup any previous uploaded file from server first
  cleanupPreviousFile();

  showToast(`Uploading ${file.name} to Python backend...`, 'info');
  const formData = new FormData();
  formData.append('file', file);

  try {
    const res = await fetch(`${API_BASE}/upload`, {
      method: 'POST',
      body: formData
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.error || 'Upload failed');
    }

    handleDatasetLoaded(data);
    showToast(`File uploaded successfully (${data.total_rows} rows)!`, 'success');
  } catch (err) {
    showToast(`Error uploading: ${err.message}`, 'error');
  }
}

function cleanupPreviousFile() {
  if (state.activeFileName) {
    const oldFile = state.activeFileName;
    fetch(`${API_BASE}/cleanup`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filename: oldFile })
    }).catch(e => console.log('Cleanup error', e));
  }
}

function handleDatasetLoaded(data) {
  state.activeFileName = data.filename;
  state.displayName = data.display_name || data.filename;
  state.columns = data.columns;
  state.numericColumns = data.numeric_columns || [];
  state.categoricalColumns = data.categorical_columns || [];
  state.previewRows = data.preview_data || [];
  state.totalRows = data.total_rows;
  state.totalCols = data.total_columns;

  // Update UI Card
  loadedFileName.textContent = state.displayName;
  loadedFileSize.textContent = `Server Storage • ${formatBytes(data.file_size)} • Auto-cleans on refresh`;
  fileInfoCard.classList.remove('hidden');

  // Populate Axes
  populateAxisSelectors();

  // Update KPI overview
  statRowCount.textContent = data.total_rows.toLocaleString();
  statColCount.textContent = data.total_columns.toLocaleString();

  // Populate Data Preview Table
  renderDataTable(state.previewRows);

  // Enable controls
  xAxisSelect.disabled = false;
  yAxisSelect.disabled = false;
  saveChartBtn.disabled = false;

  // Request visualization
  triggerVisualizationRequest();
}

function clearData() {
  // Call backend cleanup to delete file from disk
  if (state.activeFileName) {
    const fileToDelete = state.activeFileName;
    fetch(`${API_BASE}/cleanup`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filename: fileToDelete })
    }).then(() => {
      console.log(`File ${fileToDelete} deleted from server.`);
    }).catch(() => {});
  }

  state.activeFileName = '';
  state.displayName = '';
  state.columns = [];
  state.numericColumns = [];
  state.categoricalColumns = [];
  state.previewRows = [];
  state.selectedX = '';
  state.selectedY = '';

  fileInfoCard.classList.add('hidden');
  csvFileInput.value = '';

  xAxisSelect.innerHTML = '<option value="">Upload CSV first...</option>';
  yAxisSelect.innerHTML = '<option value="">Upload CSV first...</option>';
  xAxisSelect.disabled = true;
  yAxisSelect.disabled = true;
  saveChartBtn.disabled = true;

  statRowCount.textContent = '0';
  statColCount.textContent = '0';
  statSumValue.textContent = '--';
  statAvgValue.textContent = '--';

  tableHead.innerHTML = '<tr><th>Upload CSV to view data table</th></tr>';
  tableBody.innerHTML = '<tr><td class="empty-table-cell">No data loaded yet</td></tr>';
  previewRowBadge.textContent = '0 records';

  seabornChartImg.classList.add('hidden');
  seabornChartImg.src = '';
  mainChartCanvas.classList.add('hidden');
  if (state.chartInstance) {
    state.chartInstance.destroy();
    state.chartInstance = null;
  }
  chartPlaceholder.classList.remove('hidden');
  activeChartTitle.textContent = 'Statistical Visualization';
  activeChartSubtitle.textContent = 'Upload a CSV file and choose axes to request chart from Python backend.';

  showToast('Dataset cleared and file deleted from server storage.', 'info');
}

/* --------------------------------------------------------------------------
   Populate Axes Dropdowns
   -------------------------------------------------------------------------- */
function populateAxisSelectors() {
  xAxisSelect.innerHTML = '';
  yAxisSelect.innerHTML = '';

  state.columns.forEach(col => {
    const isNum = state.numericColumns.includes(col);
    const prefix = isNum ? '[123]' : '[ABC]';

    const optX = document.createElement('option');
    optX.value = col;
    optX.textContent = `${prefix} ${col}`;
    xAxisSelect.appendChild(optX);

    const optY = document.createElement('option');
    optY.value = col;
    optY.textContent = `${prefix} ${col}`;
    yAxisSelect.appendChild(optY);
  });

  // Default pick: Categorical for X, Numeric for Y
  const defaultX = state.categoricalColumns.length > 0 ? state.categoricalColumns[0] : state.columns[0];
  const defaultY = state.numericColumns.length > 0 ? state.numericColumns[0] : (state.columns[1] || state.columns[0]);

  state.selectedX = defaultX;
  state.selectedY = defaultY;

  xAxisSelect.value = state.selectedX;
  yAxisSelect.value = state.selectedY;
}

/* --------------------------------------------------------------------------
   Backend Chart Generation (Seaborn In-Memory Bytes Stream)
   -------------------------------------------------------------------------- */
async function triggerVisualizationRequest() {
  if (!state.activeFileName || !state.selectedX || !state.selectedY) {
    return;
  }

  chartPlaceholder.classList.add('hidden');
  chartLoadingOverlay.classList.remove('hidden');

  const isDark = document.body.classList.contains('dark-theme');

  const requestBody = {
    filename: state.activeFileName,
    x_axis: state.selectedX,
    y_axis: state.selectedY,
    chart_type: state.chartType,
    palette: state.palette,
    theme: isDark ? 'dark' : 'light'
  };

  try {
    const res = await fetch(`${API_BASE}/visualize`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(requestBody)
    });

    const data = await res.json();
    chartLoadingOverlay.classList.add('hidden');

    if (!res.ok) {
      throw new Error(data.error || 'Visualization error');
    }

    renderVisualResult(data);
  } catch (err) {
    chartLoadingOverlay.classList.add('hidden');
    showToast(`Chart error: ${err.message}`, 'error');
  }
}

function renderVisualResult(data) {
  state.currentChartBase64 = data.image_base64;

  // Update titles without aggregation
  activeChartTitle.textContent = `${state.selectedY} by ${state.selectedX}`;
  activeChartSubtitle.textContent = `${state.chartType.toUpperCase()} Plot • Direct Column Visualization`;

  // Update NumPy statistical KPIs
  if (data.summary_stats) {
    statSumValue.textContent = Math.round(data.summary_stats.total_sum).toLocaleString();
    statAvgValue.textContent = (Math.round(data.summary_stats.mean * 10) / 10).toLocaleString();
  }

  if (state.viewMode === 'seaborn') {
    seabornChartImg.src = data.image_base64;
    seabornChartImg.classList.remove('hidden');
    mainChartCanvas.classList.add('hidden');
  } else {
    renderInteractiveChart(data);
  }
}

function renderInteractiveChart(data) {
  seabornChartImg.classList.add('hidden');
  mainChartCanvas.classList.remove('hidden');

  if (state.chartInstance) {
    state.chartInstance.destroy();
  }

  const isDark = document.body.classList.contains('dark-theme');
  const textColor = isDark ? '#f8fafc' : '#0f172a';
  const gridColor = isDark ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.08)';

  const ctx = mainChartCanvas.getContext('2d');
  state.chartInstance = new Chart(ctx, {
    type: ['pie', 'doughnut'].includes(state.chartType) ? state.chartType : (state.chartType === 'area' ? 'line' : 'bar'),
    data: {
      labels: data.labels,
      datasets: [{
        label: state.selectedY,
        data: data.values,
        backgroundColor: 'rgba(56, 189, 248, 0.75)',
        borderColor: '#38bdf8',
        borderWidth: 2,
        fill: state.chartType === 'area',
        tension: 0.35,
        borderRadius: 6
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: ['pie', 'doughnut'].includes(state.chartType) }
      },
      scales: ['pie', 'doughnut'].includes(state.chartType) ? {} : {
        x: { grid: { color: gridColor }, ticks: { color: textColor } },
        y: { grid: { color: gridColor }, ticks: { color: textColor } }
      }
    }
  });
}

function toggleViewMode() {
  if (state.viewMode === 'seaborn') {
    state.viewMode = 'interactive';
    viewToggleBtn.textContent = '⚡ Interactive Chart';
    viewToggleBtn.classList.remove('active');
  } else {
    state.viewMode = 'seaborn';
    viewToggleBtn.textContent = '🎨 Static Plot';
    viewToggleBtn.classList.add('active');
  }
  triggerVisualizationRequest();
}

/* --------------------------------------------------------------------------
   Data Table Preview
   -------------------------------------------------------------------------- */
function renderDataTable(rows) {
  if (!state.columns.length) return;

  // Header
  tableHead.innerHTML = '';
  const trHead = document.createElement('tr');
  state.columns.forEach(col => {
    const th = document.createElement('th');
    th.textContent = col;
    trHead.appendChild(th);
  });
  tableHead.appendChild(trHead);

  renderTableRows(rows.slice(0, 50));
  previewRowBadge.textContent = `${rows.length} records shown`;
}

function renderTableRows(rows) {
  tableBody.innerHTML = '';
  if (!rows || rows.length === 0) {
    tableBody.innerHTML = '<tr><td colspan="' + state.columns.length + '" class="empty-table-cell">No matching records</td></tr>';
    return;
  }

  rows.forEach(row => {
    const tr = document.createElement('tr');
    state.columns.forEach(col => {
      const td = document.createElement('td');
      const val = row[col];
      td.textContent = (val !== undefined && val !== null) ? val : '-';
      tr.appendChild(td);
    });
    tableBody.appendChild(tr);
  });
}

function handleTableSearch(e) {
  const q = e.target.value.toLowerCase().trim();
  if (!q) {
    renderTableRows(state.previewRows.slice(0, 50));
    return;
  }

  const filtered = state.previewRows.filter(row => {
    return state.columns.some(col => String(row[col] ?? '').toLowerCase().includes(q));
  });
  renderTableRows(filtered);
}

/* --------------------------------------------------------------------------
   Saved Charts Gallery
   -------------------------------------------------------------------------- */
function saveCurrentChart() {
  if (!state.selectedX || !state.selectedY || !state.currentChartBase64) {
    showToast('Please generate a chart first!', 'error');
    return;
  }

  const item = {
    id: Date.now(),
    title: `${state.selectedY} vs ${state.selectedX}`,
    fileName: state.activeFileName,
    selectedX: state.selectedX,
    selectedY: state.selectedY,
    chartType: state.chartType,
    palette: state.palette,
    timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  };

  state.savedCharts.unshift(item);
  saveSavedChartsToStorage();
  renderSavedCharts();
  showToast(`Saved "${item.title}" to chart list!`, 'success');
}

function renderSavedCharts() {
  savedCountBadge.textContent = state.savedCharts.length;

  if (state.savedCharts.length === 0) {
    savedChartsList.innerHTML = `
      <div class="empty-saved-placeholder">
        <p>No saved charts yet.</p>
        <small>Click "Save to Chart List" to bookmark visualizations.</small>
      </div>`;
    return;
  }

  savedChartsList.innerHTML = '';
  state.savedCharts.forEach(item => {
    const el = document.createElement('div');
    el.className = 'saved-chart-item';
    el.innerHTML = `
      <div class="saved-meta">
        <span class="saved-title">${escapeHtml(item.title)}</span>
        <span class="saved-tags">${item.chartType.toUpperCase()} • ${item.timestamp}</span>
      </div>
      <div class="saved-actions">
        <button class="btn-mini" data-action="load" title="Load this chart">View</button>
        <button class="btn-mini delete" data-action="delete" title="Delete">✕</button>
      </div>
    `;

    el.querySelector('[data-action="load"]').addEventListener('click', () => loadSavedChart(item));
    el.querySelector('[data-action="delete"]').addEventListener('click', () => deleteSavedChart(item.id));
    savedChartsList.appendChild(el);
  });
}

function loadSavedChart(item) {
  state.selectedX = item.selectedX;
  state.selectedY = item.selectedY;
  state.chartType = item.chartType;
  state.palette = item.palette;

  xAxisSelect.value = item.selectedX;
  yAxisSelect.value = item.selectedY;

  chartTypeList.querySelectorAll('.chart-type-card').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.chartType === item.chartType);
  });

  paletteSelector.querySelectorAll('.palette-swatch').forEach(sw => {
    sw.classList.toggle('active', sw.dataset.palette === item.palette);
  });

  triggerVisualizationRequest();
  showToast(`Loaded saved chart: ${item.title}`, 'info');
}

function deleteSavedChart(id) {
  state.savedCharts = state.savedCharts.filter(c => c.id !== id);
  saveSavedChartsToStorage();
  renderSavedCharts();
  showToast('Chart bookmark removed.', 'info');
}

function saveSavedChartsToStorage() {
  try {
    const safeList = state.savedCharts.map(c => ({
      id: c.id,
      title: c.title,
      fileName: c.fileName,
      selectedX: c.selectedX,
      selectedY: c.selectedY,
      chartType: c.chartType,
      palette: c.palette,
      timestamp: c.timestamp
    }));
    localStorage.setItem('visualcsv_saved_charts', JSON.stringify(safeList));
  } catch (e) {
    console.error('Storage error', e);
  }
}

function loadSavedChartsFromStorage() {
  try {
    const raw = localStorage.getItem('visualcsv_saved_charts');
    if (raw) state.savedCharts = JSON.parse(raw);
  } catch (e) {
    state.savedCharts = [];
  }
  renderSavedCharts();
}

/* --------------------------------------------------------------------------
   Export & Theme
   -------------------------------------------------------------------------- */
function exportChartPNG() {
  if (state.viewMode === 'seaborn') {
    if (!seabornChartImg.src || seabornChartImg.src.startsWith('data:image') === false) {
      showToast('No active chart to export.', 'error');
      return;
    }
    const a = document.createElement('a');
    a.href = seabornChartImg.src;
    a.download = `plot_${state.selectedY}_by_${state.selectedX}.png`;
    a.click();
    showToast('Plot downloaded as PNG!', 'success');
  } else {
    if (!state.chartInstance) return;
    const a = document.createElement('a');
    a.href = mainChartCanvas.toDataURL('image/png', 1.0);
    a.download = `chart_${state.selectedY}_by_${state.selectedX}.png`;
    a.click();
    showToast('Interactive chart exported!', 'success');
  }
}

function toggleTheme() {
  document.body.classList.toggle('dark-theme');
  document.body.classList.toggle('light-theme');
  const isDark = document.body.classList.contains('dark-theme');
  themeToggleBtn.querySelector('.theme-icon').textContent = isDark ? '🌙' : '☀️';
  triggerVisualizationRequest();
}

/* --------------------------------------------------------------------------
   Helpers
   -------------------------------------------------------------------------- */
function showToast(message, type = 'info') {
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  const icon = type === 'success' ? '✓' : type === 'error' ? '✕' : 'ℹ';
  toast.innerHTML = `<span style="font-weight:700;">${icon}</span> <span>${escapeHtml(message)}</span>`;
  toastContainer.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(10px)';
    toast.style.transition = 'all 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 3200);
}

function formatBytes(bytes, decimals = 1) {
  if (!+bytes) return '0 Bytes';
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`;
}

function escapeHtml(str) {
  return String(str).replace(/[&<>"']/g, m => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[m]);
}
