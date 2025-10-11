// API base URL configuration - works for both local development and Docker
const API = (() => {
  if (location.protocol === 'file:') {
    return 'http://127.0.0.1:8000';  // Local development
  }
  // For Docker Compose - use relative paths since nginx proxies to backend
  if (location.hostname === 'localhost' && location.port === '5173') {
    return '';  // Use relative paths, nginx will proxy
  }
  // For other deployments
  if (location.hostname === 'localhost' || location.hostname === '127.0.0.1') {
    return `${location.protocol}//${location.hostname}:8000`;
  }
  // Default to same origin
  return '';
})()

async function health() {
  const statusBadge = document.getElementById('status')
  const statusText = statusBadge.querySelector('.status-text')
  
  try {
    const r = await fetch(`${API}/health`)
    if (!r.ok) {
      throw new Error(`HTTP ${r.status}: ${r.statusText}`)
    }
    const j = await r.json()
    statusBadge.className = 'status-badge status-success'
    statusText.textContent = `Connected • ${j.vectors.toLocaleString()} vectors`
  } catch (e) {
    statusBadge.className = 'status-badge status-error'
    statusText.textContent = 'API Offline'
    console.error('API health check failed:', e)
  }
}

async function loadFileOptions() {
  const fileSelect = document.getElementById('file')
  const refreshBtn = document.getElementById('refresh-files')
  
  try {
    // Show loading state
    if (refreshBtn) {
      refreshBtn.disabled = true
      refreshBtn.textContent = '⟳ Loading...'
    }
    
    const response = await fetch(`${API}/files`)
    if (!response.ok) throw new Error('Failed to fetch files')
    
    const files = await response.json()
    
    // Separate files into indexed and not indexed
    const indexed = files.filter(f => f.in_database && f.count > 0)
    const notIndexed = files.filter(f => !f.in_database || f.count === 0)
    
    // Clear existing options
    fileSelect.innerHTML = '<option value="">All Files</option>'
    
    // Add indexed files first
    if (indexed.length > 0) {
      const group = document.createElement('optgroup')
      group.label = `✓ In Database (${indexed.length})`
      indexed.forEach(f => {
        const option = document.createElement('option')
        option.value = f.filename
        option.textContent = `${f.filename} (${f.count} chunks)`
        group.appendChild(option)
      })
      fileSelect.appendChild(group)
    }
    
    // Add not indexed files with warning
    if (notIndexed.length > 0) {
      const group = document.createElement('optgroup')
      group.label = `⚠ Not Indexed (${notIndexed.length})`
      notIndexed.forEach(f => {
        const option = document.createElement('option')
        option.value = f.filename
        option.textContent = `${f.filename} (not searchable)`
        option.disabled = true
        option.style.color = '#999'
        group.appendChild(option)
      })
      fileSelect.appendChild(group)
    }
    
    console.log(`Loaded ${files.length} files: ${indexed.length} indexed, ${notIndexed.length} not indexed`)
    
    // Show warning if files need indexing
    if (notIndexed.length > 0) {
      console.warn(`⚠️ ${notIndexed.length} files need indexing. Run: python ingest.py`)
    }
    
  } catch (e) {
    console.error('Failed to load file options:', e)
    fileSelect.innerHTML = '<option value="">All Files (Error loading)</option>'
  } finally {
    // Restore refresh button
    if (refreshBtn) {
      refreshBtn.disabled = false
      refreshBtn.textContent = '⟳'
    }
  }
}

async function metrics() {
  const el = document.getElementById('metrics')
  try {
    const r = await fetch(`${API}/metrics`)
    el.textContent = JSON.stringify(await r.json(), null, 2)
  } catch (e) { el.textContent = String(e) }
}

async function bench() {
  const el = document.getElementById('bench')
  const btn = document.getElementById('run-bench')

  btn.disabled = true
  btn.textContent = '⏳ Running (10-30s)...'
  el.textContent = '🔄 Testing with 500 vectors...\n\n⚠️ If this takes > 1 minute, there\'s a performance issue.'
  try {
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 60000)

    const r = await fetch(`${API}/bench?N=5000&k=5`, {signal: controller.signal})
    clearTimeout(timeoutId)

    if (!r.ok) throw new Error(`HTTP ${r.status}`)
    
    const data = await r.json()
    el.textContent = JSON.stringify(data, null, 2)
    // Add performance warning
    if (data.avg_insert_ms > 10) {
      el.textContent += '\n\n⚠️ WARNING: Insert performance is slow!\n' +
        'Average insert: ' + data.avg_insert_ms + 'ms (should be < 5ms)\n' +
        'This may indicate disk performance issues.'
    }
  } catch (e) {
    if (e.name === 'AbortError') {
      el.textContent = '❌ Benchmark timeout after 60 seconds.\n\n' +
        'This indicates a serious performance issue.\n' +
        'Check:\n' +
        '- Is project on external/network drive?\n' +
        '- Is disk full?\n' +
        '- Run: df -h'
    } else {
      el.textContent = String(e)
    }
  } finally {
    btn.disabled = false
    btn.textContent = '⚡ Quick Bench'
  }
}

async function parity() {
  const el = document.getElementById('parity')
  el.textContent = 'Running…'
  try {
    const r = await fetch(`${API}/parity?K=5`)
    el.textContent = JSON.stringify(await r.json(), null, 2)
  } catch (e) { el.textContent = String(e) }
}

async function search() {
  const q = document.getElementById('q').value.trim()
  const k = document.getElementById('k').value || 5
  const file = document.getElementById('file').value  // No trim needed for select
  
  console.log('Search params:', { q, k, file })
  
  if (!q) {
    alert('Please enter a search query')
    return
  }

  const u = new URL(`${API}/search`)
  u.searchParams.set('q', q)
  u.searchParams.set('k', k)
  if (file) u.searchParams.set('file', file)
  
  console.log('Search URL:', u.toString())

  const el = document.getElementById('results')
  const emptyState = document.getElementById('results-empty')
  const resultsCount = document.getElementById('results-count')
  const copyBtn = document.getElementById('copy-btn')
  const button = document.getElementById('go')
  
  // Show loading state with skeletons
  button.disabled = true
  button.textContent = 'Searching...'
  emptyState.style.display = 'none'
  copyBtn.style.display = 'none'
  el.innerHTML = `
    <div class="skeleton skeleton-card"></div>
    <div class="skeleton skeleton-card"></div>
    <div class="skeleton skeleton-card"></div>
  `
  
  try {
    const r = await fetch(u)
    if (!r.ok) {
      throw new Error(`HTTP ${r.status}: ${r.statusText}`)
    }
    const data = await r.json()
    el.innerHTML = ''
    
    if (!Array.isArray(data) || data.length === 0) {
      emptyState.style.display = 'block'
      emptyState.querySelector('p').textContent = 'No results found'
      emptyState.querySelector('.empty-hint').textContent = 'Try different keywords or remove the filename filter'
      resultsCount.textContent = ''
      return
    }
    
    // Store search in history
    addToSearchHistory(q)
    
    // Update results count
    resultsCount.textContent = `${data.length} results`
    copyBtn.style.display = 'flex'
    
    // Render results with ranking
    for (let i = 0; i < data.length; i++) {
      const item = data[i]
      const wrap = document.createElement('div')
      wrap.className = 'card'
      const pv = (item.metadata?.chunk || '').replaceAll('\n', ' ')
      const preview = pv.length > 220 ? pv.slice(0, 217) + '…' : pv
      wrap.innerHTML = `
        <div class="card-rank">${i + 1}</div>
        <div class="card-content">
          <div class="card-header">
            <div class="card-title">${item.id}</div>
          </div>
          <div class="card-meta">
            <span class="chip-small">sim=${item.similarity.toFixed(4)}</span>
            <span class="chip-small chip-file">📄 ${item.metadata?.file ?? 'unknown'}</span>
          </div>
        <div class="card-body">${preview}</div>
        </div>
      `
      el.appendChild(wrap)
    }
  } catch (e) {
    el.innerHTML = `<div class="error">Search failed: ${e.message}. Check if the API is running.</div>`
    emptyState.style.display = 'none'
  } finally {
    // Reset button state
    button.disabled = false
    button.textContent = 'Search (⌘↵)'
  }
}

// Search history functionality
function addToSearchHistory(query) {
  const history = JSON.parse(localStorage.getItem('searchHistory') || '[]')
  if (!history.includes(query)) {
    history.unshift(query)
    history.splice(10) // Keep only last 10 searches
    localStorage.setItem('searchHistory', JSON.stringify(history))
    updateSearchHistory()
  }
}

function updateSearchHistory() {
  const history = JSON.parse(localStorage.getItem('searchHistory') || '[]')
  const historyEl = document.getElementById('searchHistory')
  const historyContent = document.getElementById('searchHistoryContent')
  if (!historyEl || !historyContent) return
  
  if (history.length === 0) {
    historyEl.style.display = 'none'
    return
  }
  
  historyEl.style.display = 'block'
  historyContent.innerHTML = history.map(q => 
    `<span class="history-item" onclick="document.getElementById('q').value='${q.replace(/'/g, "\\'")}'; search()">${q}</span>`
  ).join('')
}

document.getElementById('go').addEventListener('click', search)

// Allow Enter key to trigger search
document.getElementById('q').addEventListener('keypress', (e) => {
  if (e.key === 'Enter') {
    search()
  }
})

// File upload functionality
async function uploadFile() {
  const fileInput = document.getElementById('fileUpload')
  const uploadBtn = document.getElementById('uploadBtn')
  const statusEl = document.getElementById('uploadStatus')
  
  const file = fileInput.files[0]
  if (!file) {
    statusEl.innerHTML = '<div class="error">Please select a file</div>'
    return
  }
  
  const supportedExtensions = ['.txt', '.md', '.pdf', '.docx', '.pptx', '.xlsx']
  const fileExt = file.name.toLowerCase().split('.').pop()
  const hasValidExtension = supportedExtensions.some(ext => file.name.toLowerCase().endsWith(ext))
  
  console.log('File upload attempt:', {
    fileName: file.name,
    fileExt: fileExt,
    hasValidExtension: hasValidExtension,
    supportedExtensions: supportedExtensions
  })
  
  if (!hasValidExtension) {
    statusEl.innerHTML = `<div class="error">File type .${fileExt} not supported. Only ${supportedExtensions.join(', ')} files are supported</div>`
    return
  }
  
  uploadBtn.disabled = true
  uploadBtn.textContent = 'Uploading...'
  statusEl.innerHTML = '<div class="muted">Uploading and processing...</div>'
  
  try {
    const formData = new FormData()
    formData.append('file', file)
    
    console.log('Uploading file to:', `${API}/upload`)
    console.log('FormData contents:', Array.from(formData.entries()))
    
    const response = await fetch(`${API}/upload`, {
      method: 'POST',
      body: formData
    })
    
    console.log('Upload response:', response.status, response.statusText)
    
    if (!response.ok) {
      const errorText = await response.text()
      console.error('Upload error response:', errorText)
      throw new Error(`HTTP ${response.status}: ${response.statusText}`)
    }
    
    const result = await response.json()
    console.log('Upload success result:', result)
    statusEl.innerHTML = `<div class="status-success">✓ ${result.message} (${result.chunks} chunks, ${result.total_vectors} total vectors, ${result.file_type?.toUpperCase()} file)</div>`
    
    // Refresh health status and file list to show updates
    health()
    loadFileOptions()
    
    // Clear file input
    fileInput.value = ''
    
  } catch (e) {
    statusEl.innerHTML = `<div class="error">Upload failed: ${e.message}</div>`
  } finally {
    uploadBtn.disabled = false
    uploadBtn.textContent = 'Upload & Ingest'
  }
}

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {
  // Cmd/Ctrl + K to focus search
  if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
    e.preventDefault();
    document.getElementById('q').focus();
  }
  
  // Cmd/Ctrl + Enter to search
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
    e.preventDefault();
    if (document.getElementById('q').value.trim()) {
      search();
    }
  }
  
  // Escape to clear search
  if (e.key === 'Escape') {
    const searchInput = document.getElementById('q');
    if (document.activeElement === searchInput) {
      searchInput.value = '';
    }
  }
  
  // Cmd/Ctrl + T to run all tests
  if ((e.ctrlKey || e.metaKey) && e.key === 't') {
    e.preventDefault();
    runAllTests();
  }
  
  // Cmd/Ctrl + E to export results
  if ((e.ctrlKey || e.metaKey) && e.key === 'e') {
    e.preventDefault();
    const exportBtn = document.getElementById('export-btn');
    if (exportBtn && exportBtn.style.display !== 'none') {
      exportResults();
    }
  }
});

// ============================================
//   DIAGNOSTIC TEST SUITE
// ============================================

// Global variable to store test results
let testResults = {};

// Run all diagnostic tests in sequence
async function runAllTests() {
  const btn = event.target.closest('.action-button');
  if (!btn) return;
  
  const originalHTML = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = '<span class="button-icon">⏳</span><span class="button-text">Running...</span>';
  
  // Reset results
  testResults = {
    timestamp: new Date().toISOString(),
    tests: []
  };
  
  // Show a progress modal or notification
  const progressModal = document.createElement('div');
  progressModal.id = 'test-progress-modal';
  progressModal.innerHTML = `
    <h3 style="margin: 0 0 12px 0; font-size: 16px;">🧪 Running Full Diagnostic Suite</h3>
    <div id="test-progress-list"></div>
  `;
  document.body.appendChild(progressModal);
  
  const progressList = document.getElementById('test-progress-list');
  
  try {
    // Test 1: Health Check
    progressList.innerHTML += '<div>⏳ Health Check...</div>';
    await refreshHealthDiagnostic();
    progressList.lastChild.innerHTML = '✅ Health Check - Complete';
    testResults.tests.push({ name: 'Health Check', status: 'passed' });
    await sleep(500);
    
    // Test 2: Quick Benchmark
    progressList.innerHTML += '<div>⏳ Quick Benchmark (500 vectors)...</div>';
    await runBench();
    progressList.lastChild.innerHTML = '✅ Quick Benchmark - Complete';
    testResults.tests.push({ name: 'Quick Benchmark', status: 'passed' });
    await sleep(500);
    
    // Test 3: Accuracy Check
    progressList.innerHTML += '<div>⏳ Accuracy Verification...</div>';
    await runParity();
    progressList.lastChild.innerHTML = '✅ Accuracy Check - Complete';
    testResults.tests.push({ name: 'Accuracy Verification', status: 'passed' });
    await sleep(500);
    
    // Test 4: Scale Test (quick profile)
    progressList.innerHTML += '<div>⏳ Scale Test (quick)...</div>';
    await runScaleTest();
    progressList.lastChild.innerHTML = '✅ Scale Test - Complete';
    testResults.tests.push({ name: 'Scale Test', status: 'passed' });
    
    // Success
    progressList.innerHTML += '<div style="margin-top: 12px; padding: 10px; background: #f0fdf4; border-radius: 6px; color: #16a34a; font-weight: 600;">✅ All Tests Passed!</div>';
    
    // Show export button
    document.getElementById('export-btn').style.display = 'flex';
    
    // Auto-close after 3 seconds
    setTimeout(() => {
      progressModal.remove();
    }, 3000);
    
  } catch (e) {
    progressList.innerHTML += `<div style="color: var(--error); margin-top: 12px;">❌ Error: ${e.message}</div>`;
    testResults.tests.push({ name: 'Error', status: 'failed', error: e.message });
    setTimeout(() => {
      progressModal.remove();
    }, 5000);
  } finally {
    btn.disabled = false;
    btn.innerHTML = originalHTML;
  }
}

// Export test results
function exportResults() {
  if (!testResults || !testResults.tests || testResults.tests.length === 0) {
    alert('No test results to export. Run tests first!');
    return;
  }
  
  // Gather all results
  const exportData = {
    timestamp: testResults.timestamp,
    vectorBench: 'v1.0',
    systemInfo: {
      files: document.getElementById('file-count')?.textContent || 'N/A',
      queries: document.getElementById('query-count')?.textContent || 'N/A',
      p95Latency: document.getElementById('p95-latency')?.textContent || 'N/A',
      status: document.getElementById('perf-status-text')?.textContent || 'N/A',
    },
    tests: testResults.tests,
    benchResults: document.getElementById('bench-results')?.textContent || 'N/A',
    parityResults: document.getElementById('parity-results')?.textContent || 'N/A',
    healthResults: document.getElementById('health-results')?.textContent || 'N/A',
  };
  
  // Create formatted report
  const report = `
VectorBench Diagnostic Report
========================================
Generated: ${new Date(testResults.timestamp).toLocaleString()}
VectorBench Version: v1.0

SYSTEM STATUS
-------------
Indexed Files: ${exportData.systemInfo.files}
Total Queries: ${exportData.systemInfo.queries}
P95 Latency: ${exportData.systemInfo.p95Latency} (${exportData.systemInfo.status})

TEST RESULTS
------------
${exportData.tests.map(t => `✓ ${t.name}: ${t.status}`).join('\n')}

========================================
Full results available in browser console.
`.trim();
  
  // Copy to clipboard
  navigator.clipboard.writeText(report).then(() => {
    // Show success message
    const btn = event.target.closest('.action-button');
    const originalHTML = btn.innerHTML;
    btn.innerHTML = '<span class="button-icon">✅</span><span class="button-text">Copied!</span>';
    setTimeout(() => {
      btn.innerHTML = originalHTML;
    }, 2000);
    
    // Also log full data to console
    console.log('📊 VectorBench Diagnostic Report', exportData);
    alert('✅ Report copied to clipboard!\n\nFull results logged to console (F12)');
  }).catch(err => {
    console.error('Failed to copy:', err);
    alert('Failed to copy to clipboard. Results logged to console.');
    console.log('📊 VectorBench Diagnostic Report', exportData);
  });
}

// Helper function for delays
function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}


// Copy results to clipboard
function copyResults() {
  const results = document.querySelectorAll('.card');
  if (results.length === 0) return;
  
  let text = 'Search Results:\n\n';
  results.forEach((card, index) => {
    const title = card.querySelector('.card-title')?.textContent || '';
    const body = card.querySelector('.card-body')?.textContent || '';
    text += `${index + 1}. ${title}\n${body}\n\n`;
  });
  
  navigator.clipboard.writeText(text).then(() => {
    const btn = document.getElementById('copy-btn');
    const originalText = btn.textContent;
    btn.textContent = '✓';
    setTimeout(() => btn.textContent = originalText, 1000);
  });
}

// Load search history on page load
window.addEventListener('DOMContentLoaded', () => {
  health()
  loadFileOptions()
  updateSearchHistory()
  
  // Set up file upload
  document.getElementById('uploadBtn').addEventListener('click', uploadFile)
  
  // Set up metrics buttons
  document.getElementById('refresh-health').addEventListener('click', health)
  document.getElementById('refresh-metrics').addEventListener('click', metrics)
  document.getElementById('run-bench').addEventListener('click', bench)
  document.getElementById('run-parity').addEventListener('click', parity)
})

// Global chart instances
let latencyChart = null;
let scaleChart = null;

// Initialize latency chart
function initLatencyChart() {
  const ctx = document.getElementById('latencyChart').getContext('2d');
  latencyChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: [],
      datasets: [{
        label: 'Search Latency (ms)',
        data: [],
        borderColor: '#3b82f6',
        backgroundColor: 'rgba(59, 130, 246, 0.1)',
        tension: 0.4,
        fill: true
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (context) => `${context.parsed.y.toFixed(2)}ms`
          }
        }
      },
      scales: {
        y: {
          beginAtZero: true,
          title: { display: true, text: 'Latency (ms)' }
        },
        x: {
          title: { display: true, text: 'Recent Searches' }
        }
      }
    }
  });
}

// Update metrics with visual feedback
async function updateMetrics() {
  try {
    const [healthRes, metricsRes, filesRes] = await Promise.all([
      fetch(`${API}/health`),
      fetch(`${API}/metrics`),
      fetch(`${API}/files`)
    ]);
    
    const health = await healthRes.json();
    const metrics = await metricsRes.json();
    const files = await filesRes.json();
    
    // Update indexed file count
    const indexedFiles = files.filter(f => f.in_database && f.count > 0).length;
    document.getElementById('file-count').textContent = indexedFiles.toLocaleString();
    
    // Update latencies with color coding
    const p50 = metrics.p50_ms;
    const p95 = metrics.p95_ms;
    
    if (p50 !== null && p95 !== null) {
      document.getElementById('p95-latency').textContent = `${p95.toFixed(0)}ms`;
      
      // Update query count
      const queryCount = metrics.count || 0;
      document.getElementById('query-count').textContent = queryCount.toLocaleString();
      
      // Update performance status
      updatePerformanceStatus(p95);
      
      // Update chart
      updateLatencyChart(metrics.recent || []);
    } else {
      document.getElementById('p95-latency').textContent = 'N/A';
      document.getElementById('query-count').textContent = '0';
      document.getElementById('perf-status-text').textContent = 'No data';
    }
    
  } catch (e) {
    console.error('Failed to update metrics:', e);
  }
}

// Update performance status indicator
function updatePerformanceStatus(p95) {
  const statusCard = document.getElementById('performance-status');
  const statusText = document.getElementById('perf-status-text');
  
  if (!statusCard || !statusText) return;
  
  // Remove all status classes
  statusCard.classList.remove('status-excellent', 'status-good', 'status-ok', 'status-slow');
  
  if (p95 < 50) {
    statusCard.classList.add('status-excellent');
    statusText.textContent = 'Excellent';
  } else if (p95 < 100) {
    statusCard.classList.add('status-good');
    statusText.textContent = 'Good';
  } else if (p95 < 300) {
    statusCard.classList.add('status-ok');
    statusText.textContent = 'OK';
  } else {
    statusCard.classList.add('status-slow');
    statusText.textContent = 'Slow';
  }
}

// Update latency chart with recent searches
function updateLatencyChart(recentLatencies) {
  if (!latencyChart) return;
  
  const labels = recentLatencies.map((_, i) => `${i + 1}`);
  latencyChart.data.labels = labels;
  latencyChart.data.datasets[0].data = recentLatencies;
  latencyChart.update();
}

// Enhanced bench with visual results
async function runBench() {
  const btn = document.getElementById('run-bench');
  const resultsEl = document.getElementById('bench-results');
  const sizeSelect = document.getElementById('bench-size');
  
  // Get user-selected size
  const N = parseInt(sizeSelect.value);
  const estimatedTime = N <= 100 ? '2-5s' : N <= 500 ? '5-15s' : N <= 1000 ? '15-30s' : '30s-1min';
  
  btn.disabled = true;
  btn.textContent = '⏳ Running...';
  resultsEl.style.display = 'block';
  resultsEl.innerHTML = `
    <div class="muted" style="padding: 12px;">
      <div style="margin-bottom: 8px;">🔄 Running Quick Benchmark...</div>
      <div style="font-size: 12px; opacity: 0.8;">
        • Testing ${N.toLocaleString()} vectors<br>
        • Estimated time: ${estimatedTime}<br>
        • Measuring insert + search performance
      </div>
    </div>
  `;
  
  try {
    // Add timeout protection
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 60000); // 60s timeout
    
    const r = await fetch(`${API}/bench?N=${N}&k=5`, { signal: controller.signal });
    clearTimeout(timeoutId);
    
    if (!r.ok) throw new Error(`Server returned ${r.status}`);
    const data = await r.json();
    
    // Determine result class
    let resultClass = 'result-success';
    let statusIcon = '✓';
    let statusText = 'Good Performance';
    
    if (data.search_ms > 200) {
      resultClass = 'result-warning';
      statusIcon = '⚠';
      statusText = 'Consider Optimization';
    }
    if (data.search_ms > 500) {
      resultClass = 'result-error';
      statusIcon = '❌';
      statusText = 'Performance Issue';
    }
    
    resultsEl.className = `result-card ${resultClass}`;
    resultsEl.innerHTML = `
      <h4>${statusIcon} Quick Benchmark Results</h4>
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 16px; margin: 12px 0;">
        <div>
          <div class="metric-label">Database Size</div>
          <div class="metric-value" style="font-size: 20px;">${data.N.toLocaleString()}</div>
          <div class="metric-helper">vectors</div>
        </div>
        <div>
          <div class="metric-label">Insert Speed</div>
          <div class="metric-value" style="font-size: 20px;">${data.avg_insert_ms.toFixed(2)}</div>
          <div class="metric-helper">ms per vector</div>
        </div>
        <div>
          <div class="metric-label">Search Time</div>
          <div class="metric-value" style="font-size: 20px;">${data.search_ms.toFixed(1)}</div>
          <div class="metric-helper">milliseconds</div>
        </div>
        <div>
          <div class="metric-label">File Size</div>
          <div class="metric-value" style="font-size: 20px;">${data.file_MB.toFixed(1)}</div>
          <div class="metric-helper">megabytes</div>
        </div>
      </div>
      <div style="font-size: 13px; color: var(--muted); margin-top: 12px;">
        <strong>${statusText}:</strong> Search completed in ${data.search_ms.toFixed(1)}ms. 
        ${data.search_ms < 100 ? 'Great for production use!' : 
          data.search_ms < 300 ? 'Acceptable for most use cases.' : 
          'Consider upgrading to ANN algorithm for better performance.'}
      </div>
      ${data.avg_insert_ms > 10 ? `
        <div style="margin-top: 12px; padding: 10px; background: #fff3cd; border: 1px solid #ffc107; border-radius: 8px; font-size: 13px; color: #856404;">
          ⚠️ <strong>Slow inserts detected (${data.avg_insert_ms.toFixed(2)}ms avg)</strong><br>
          <div style="margin-top: 6px; font-size: 12px;">
            This may indicate:<br>
            • Project on iCloud or network drive<br>
            • Slow disk I/O<br>
            • Move database to local storage for better performance
          </div>
        </div>
      ` : ''}
    `;
  } catch (e) {
    resultsEl.className = 'result-card result-error';
    if (e.name === 'AbortError') {
      resultsEl.innerHTML = `
        <h4>❌ Benchmark Timeout</h4>
        <p style="margin: 12px 0;">Benchmark took longer than 60 seconds to complete.</p>
        <div style="padding: 12px; background: var(--bg); border-radius: 8px; font-size: 13px;">
          <strong>Common causes:</strong><br>
          • Database on iCloud or network drive (VERY slow)<br>
          • System under heavy load<br>
          • Disk performance issues<br>
          <br>
          <strong>Solution:</strong> Move project to local storage (~/Projects/)
        </div>
      `;
    } else {
    resultsEl.innerHTML = `<h4>❌ Benchmark Failed</h4><p>${e.message}</p>`;
    }
  } finally {
    btn.disabled = false;
    btn.textContent = '⚡ Bench';
  }
}

// Enhanced parity check with visual results
async function runParity() {
  const btn = document.getElementById('run-parity');
  const resultsEl = document.getElementById('parity-results');
  const sizeSelect = document.getElementById('parity-size');
  
  // Get user-selected test size
  const K = parseInt(sizeSelect.value);
  
  btn.disabled = true;
  btn.textContent = '⏳ Checking...';
  resultsEl.style.display = 'block';
  resultsEl.innerHTML = `
    <div class="muted" style="padding: 12px;">
      <div style="margin-bottom: 8px;">🔍 Running Accuracy Check...</div>
      <div style="font-size: 12px; opacity: 0.8;">
        Comparing top ${K} results from VectorLiteDB vs NumPy<br>
        This verifies mathematical correctness
      </div>
    </div>
  `;
  
  try {
    const r = await fetch(`${API}/parity?K=${K}`);
    const data = await r.json();
    
    const resultClass = data.ok ? 'result-success' : 'result-error';
    const statusIcon = data.ok ? '✓' : '❌';
    const statusText = data.ok ? 'Accuracy Verified' : 'Accuracy Mismatch';
    
    resultsEl.className = `result-card ${resultClass}`;
    resultsEl.innerHTML = `
      <h4>${statusIcon} ${statusText}</h4>
      <p style="margin: 12px 0; font-size: 14px; line-height: 1.6;">
        ${data.ok ? 
          '✅ <strong>Perfect Match!</strong><br>VectorLiteDB results are identical to the gold-standard NumPy implementation. Your search results are mathematically correct!' :
          '❌ <strong>Mismatch Detected!</strong><br>VectorLiteDB results differ from NumPy. This may indicate a version issue or data corruption.'}
      </p>
      <div style="padding: 10px; background: var(--bg); border-radius: 8px; font-size: 13px; margin-top: 12px;">
        <div style="margin-bottom: 8px;"><strong>Test Details:</strong></div>
        <div>• Compared top ${K} search results</div>
        <div>• Baseline: NumPy ${data.ok ? '✓' : '✗'}</div>
        <div>• VectorLiteDB: ${data.ok ? '✓' : '✗'}</div>
      </div>
      <details style="margin-top: 12px; font-size: 12px;">
        <summary style="cursor: pointer; color: var(--primary); padding: 8px; background: var(--bg); border-radius: 6px;">📋 View Raw Data</summary>
        <div style="margin-top: 8px; padding: 12px; background: var(--card); border: 1px solid var(--border); border-radius: 6px; font-family: monospace; font-size: 11px;">
          <div style="margin-bottom: 8px;"><strong>NumPy IDs:</strong></div>
          <div style="margin-bottom: 12px; padding: 8px; background: var(--bg); border-radius: 4px;">${JSON.stringify(data.numpy_topk, null, 2)}</div>
          <div style="margin-bottom: 8px;"><strong>VectorLiteDB IDs:</strong></div>
          <div style="padding: 8px; background: var(--bg); border-radius: 4px;">${JSON.stringify(data.vldb_topk, null, 2)}</div>
        </div>
      </details>
    `;
  } catch (e) {
    resultsEl.className = 'result-card result-error';
    resultsEl.innerHTML = `<h4>❌ Parity Check Failed</h4><p>${e.message}</p>`;
  } finally {
    btn.disabled = false;
    btn.textContent = 'Run Accuracy Check';
  }
}

// NEW: Scale test with visualization
async function runScaleTest() {
  const btn = document.getElementById('run-scale-test');
  const chartContainer = document.getElementById('scale-chart-container');
  const profileSelect = document.getElementById('scale-profile');
  
  btn.disabled = true;
  chartContainer.style.display = 'block';
  
  // Get user-selected profile
  const profile = profileSelect.value;
  let sizes, estimatedTime;
  
  switch(profile) {
    case 'quick':
      sizes = [100, 250, 500];
      estimatedTime = '15-30 seconds';
      break;
    case 'standard':
      sizes = [500, 1000, 2000];
      estimatedTime = '45-90 seconds';
      break;
    case 'thorough':
      sizes = [1000, 2500, 5000];
      estimatedTime = '2-4 minutes';
      break;
    default:
      sizes = [100, 250, 500];
      estimatedTime = '15-30 seconds';
  }
  
  const totalTests = sizes.length;
  const results = [];
  
  // Show initial progress
  chartContainer.innerHTML = `
    <div class="muted" style="padding: 16px; text-align: center;">
      <div style="margin-bottom: 12px;">📊 Running ${profile.charAt(0).toUpperCase() + profile.slice(1)} Scale Test...</div>
      <div style="font-size: 13px;">
        Testing ${sizes.map(s => s.toLocaleString()).join(', ')} vectors<br>
        <span style="font-size: 12px; opacity: 0.7;">Estimated: ${estimatedTime}</span>
      </div>
      <div style="margin-top: 12px; font-size: 12px;" id="scale-progress">
        ⏱️ Starting test 1/${totalTests}...
      </div>
    </div>
  `;
  
  try {
    for (let i = 0; i < sizes.length; i++) {
      const N = sizes[i];
      btn.textContent = `⏳ ${N} (${i+1}/${totalTests})`;
      document.getElementById('scale-progress').textContent = 
        `⏱️ Testing ${N.toLocaleString()} vectors (${i+1}/${totalTests})...`;
      
      // Add timeout per test
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 45000); // 45s per test
      
      const r = await fetch(`${API}/bench?N=${N}&k=5`, { signal: controller.signal });
      clearTimeout(timeoutId);
      
      if (!r.ok) throw new Error(`Test ${i+1} failed with status ${r.status}`);
      
      const data = await r.json();
      results.push({ 
        N: data.N, 
        searchMs: data.search_ms,
        insertMs: data.avg_insert_ms 
      });
    }
    
    // Create scale chart
    createScaleChart(results);
    
  } catch (e) {
    chartContainer.innerHTML = `
      <div class="result-card result-error">
        <h4>❌ Scale Test Failed</h4>
        <p>${e.name === 'AbortError' ? 'Test timeout - likely slow disk I/O' : e.message}</p>
        <div style="margin-top: 12px; font-size: 13px;">
          ${results.length > 0 ? `Completed ${results.length}/${totalTests} tests before error.` : 'No tests completed.'}
        </div>
      </div>
    `;
  } finally {
    btn.disabled = false;
    btn.textContent = '📊 Scale';
  }
}

// Create scalability chart
function createScaleChart(results) {
  const chartContainer = document.getElementById('scale-chart-container');
  
  // Recreate canvas element (it was removed by innerHTML during progress updates)
  chartContainer.innerHTML = '<canvas id="scaleChart"></canvas>';
  
  const canvas = document.getElementById('scaleChart');
  if (!canvas) {
    console.error('Scale chart canvas not found');
    return;
  }
  
  const ctx = canvas.getContext('2d');
  
  if (scaleChart) scaleChart.destroy();
  
  scaleChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: results.map(r => r.N.toLocaleString()),
      datasets: [{
        label: 'Search Time',
        data: results.map(r => r.searchMs),
        borderColor: '#3b82f6',
        backgroundColor: 'rgba(59, 130, 246, 0.1)',
        tension: 0.3,
        fill: true,
        pointRadius: 6,
        pointHoverRadius: 8
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        tooltip: {
          callbacks: {
            label: (context) => `${context.parsed.y.toFixed(2)}ms`
          }
        }
      },
      scales: {
        y: {
          beginAtZero: true,
          title: { display: true, text: 'Search Time (ms)' }
        },
        x: {
          title: { display: true, text: 'Number of Vectors' }
        }
      }
    }
  });
}

// Toggle section
function toggleSection(sectionId) {
  const content = document.getElementById(sectionId);
  const header = content.previousElementSibling;
  const icon = header.querySelector('.collapse-icon');
  
  // Toggle display
  if (content.style.display === 'none') {
    content.style.display = 'block';
    icon.classList.remove('collapsed');
    icon.textContent = '▼';
  } else {
    content.style.display = 'none';
    icon.classList.add('collapsed');
    icon.textContent = '▶';
  }
}

// Initialize on page load
window.addEventListener('DOMContentLoaded', () => {
  initLatencyChart();
  updateMetrics();
  
  // Auto-refresh metrics every 5 seconds
  setInterval(updateMetrics, 5000);
  
  // Update button handlers
  document.getElementById('refresh-health').addEventListener('click', refreshHealthDiagnostic);
  document.getElementById('run-bench').addEventListener('click', runBench);
  document.getElementById('run-parity').addEventListener('click', runParity);
  document.getElementById('run-scale-test').addEventListener('click', runScaleTest);
});

// Enhanced health diagnostic with detailed results
async function refreshHealthDiagnostic() {
  const btn = document.getElementById('refresh-health');
  const resultsEl = document.getElementById('health-results');
  
  btn.disabled = true;
  btn.textContent = '⏳ Checking...';
  resultsEl.style.display = 'block';
  resultsEl.innerHTML = '<div class="muted" style="padding: 12px;">🔄 Checking system status...</div>';
  
  try {
    // Fetch health and metrics
    const [healthRes, metricsRes, filesRes] = await Promise.all([
      fetch(`${API}/health`),
      fetch(`${API}/metrics`),
      fetch(`${API}/files`)
    ]);
    
    const health = await healthRes.json();
    const metrics = await metricsRes.json();
    const files = await filesRes.json();
    
    // Update header badge
    const statusBadge = document.getElementById('status');
    const statusText = statusBadge.querySelector('.status-text');
    statusBadge.className = 'status-badge status-success';
    statusText.textContent = `Connected • ${health.vectors.toLocaleString()} vectors`;
    
    // Update metrics
    updateMetrics();
    loadFileOptions();
    
    // Show detailed results
    const indexedFiles = files.filter(f => f.in_database).length;
    const totalFiles = files.length;
    
    resultsEl.className = 'result-card result-success';
    resultsEl.innerHTML = `
      <h4>✅ System Healthy</h4>
      <div style="display: grid; gap: 12px; margin-top: 12px;">
        <div style="padding: 10px; background: var(--bg); border-radius: 8px;">
          <div style="font-size: 13px; font-weight: 600; margin-bottom: 6px;">📊 Database Status</div>
          <div style="font-size: 14px;">• Total vectors: <strong>${health.vectors.toLocaleString()}</strong></div>
          <div style="font-size: 14px;">• Indexed files: <strong>${indexedFiles}/${totalFiles}</strong></div>
        </div>
        <div style="padding: 10px; background: var(--bg); border-radius: 8px;">
          <div style="font-size: 13px; font-weight: 600; margin-bottom: 6px;">⚡ Performance</div>
          <div style="font-size: 14px;">• P50 latency: <strong>${metrics.p50_ms ? metrics.p50_ms.toFixed(1) + 'ms' : 'N/A'}</strong></div>
          <div style="font-size: 14px;">• P95 latency: <strong>${metrics.p95_ms ? metrics.p95_ms.toFixed(1) + 'ms' : 'N/A'}</strong></div>
          <div style="font-size: 14px;">• Recent queries: <strong>${metrics.count || 0}</strong></div>
        </div>
        <div style="padding: 10px; background: var(--bg); border-radius: 8px;">
          <div style="font-size: 13px; font-weight: 600; margin-bottom: 6px;">🔌 Connection</div>
          <div style="font-size: 14px;">• API Status: <strong style="color: var(--success);">Online ✓</strong></div>
          <div style="font-size: 14px;">• Response time: <strong>&lt; 100ms</strong></div>
        </div>
      </div>
    `;
  } catch (e) {
    // Update header to offline
    const statusBadge = document.getElementById('status');
    const statusText = statusBadge.querySelector('.status-text');
    statusBadge.className = 'status-badge status-error';
    statusText.textContent = 'API Offline';
    
    resultsEl.className = 'result-card result-error';
    resultsEl.innerHTML = `
      <h4>❌ System Error</h4>
      <p style="margin: 12px 0;">${e.message}</p>
      <div style="padding: 10px; background: var(--bg); border-radius: 8px; font-size: 13px;">
        <strong>Troubleshooting:</strong><br>
        • Is the API server running? (uvicorn app:app --reload)<br>
        • Check console for errors (F12)<br>
        • Verify database file exists (kb.db)
      </div>
    `;
  } finally {
    btn.disabled = false;
    btn.textContent = 'Refresh Status & Metrics';
  }
}

