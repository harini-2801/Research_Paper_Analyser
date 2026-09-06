/* ==========================================================================
   RPRA Frontend Application JS
   Handles REST API, WebSockets, Cytoscape Graph Rendering, and Evidence Inspector
   ========================================================================== */

// Base API configuration (supports Vercel standalone frontend connecting to remote Render backend)
const API_BASE = window.API_BASE_URL || (window.location.origin.includes('localhost') || window.location.origin.includes('127.0.0.1') ? '' : 'http://127.0.0.1:8000');
const WS_BASE = API_BASE.replace(/^http/, 'ws');

let cy = null;
let currentGraphData = null;

// Initialize on DOM load
document.addEventListener('DOMContentLoaded', () => {
  setupTabs();
  setupModals();
  setupWeightSliders();
  setupDropzone();
  connectWebSocket();
  fetchStatus();
  fetchData();

  // Button Listeners
  document.getElementById('btn-run-demo')?.addEventListener('click', () => runPipeline(true));
  document.getElementById('btn-run-full')?.addEventListener('click', () => runPipeline(false));
  document.getElementById('btn-fit-graph')?.addEventListener('click', () => cy && cy.fit());
  document.getElementById('graph-search')?.addEventListener('input', filterGraphNodes);
});

// ----------------------------------------------------------------------
// WebSocket Progress Listener
// ----------------------------------------------------------------------
function connectWebSocket() {
  const wsUrl = `${WS_BASE}/ws/progress`;
  const wsStatusText = document.getElementById('ws-status-text');
  const wsStatusDot = document.querySelector('#ws-status span');

  try {
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      if (wsStatusText) wsStatusText.innerText = 'Connected';
      if (wsStatusDot) wsStatusDot.className = 'w-2 h-2 rounded-full bg-emerald-400 animate-ping';
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      updateProgressPanel(data);
    };

    ws.onclose = () => {
      if (wsStatusText) wsStatusText.innerText = 'Disconnected';
      if (wsStatusDot) wsStatusDot.className = 'w-2 h-2 rounded-full bg-rose-500';
      setTimeout(connectWebSocket, 5000);
    };

    ws.onerror = () => {
      if (wsStatusText) wsStatusText.innerText = 'Offline Mode';
      if (wsStatusDot) wsStatusDot.className = 'w-2 h-2 rounded-full bg-amber-500';
    };
  } catch (err) {
    console.warn('WebSocket connection skipped:', err);
  }
}

// ----------------------------------------------------------------------
// REST API Data Fetching
// ----------------------------------------------------------------------
async function fetchStatus() {
  try {
    const res = await fetch(`${API_BASE}/api/status`);
    const data = await res.json();

    document.getElementById('stat-papers-count').innerText = data.pdf_count || 0;
    document.getElementById('stat-papers-sub').innerText = `${data.pdf_count} PDFs in corpus`;
    document.getElementById('stat-kg-count').innerHTML = `${data.kg_nodes} <span class="text-xs font-normal text-slate-400">nodes</span>`;
    document.getElementById('stat-kg-sub').innerText = `${data.kg_edges} edges connected`;
    document.getElementById('stat-contradictions-count').innerText = data.contradictions_count || 0;
    document.getElementById('stat-gaps-count').innerText = data.gaps_count || 0;

    if (data.status === 'running') {
      showProgressPanel();
    }
  } catch (err) {
    console.error('Failed to fetch status:', err);
  }
}

async function fetchData() {
  await Promise.all([
    fetchGraph(),
    fetchContradictions(),
    fetchGaps(),
    fetchDocuments(),
    fetchScores()
  ]);
}

async function runPipeline(skipExtraction) {
  try {
    showProgressPanel();
    const res = await fetch(`${API_BASE}/api/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ skip_extraction: skipExtraction, skip_explanation: false })
    });
    const data = await res.json();
    console.log('Pipeline started:', data);
  } catch (err) {
    alert('Failed to trigger pipeline execution: ' + err.message);
  }
}

// ----------------------------------------------------------------------
// Progress Panel Updates
// ----------------------------------------------------------------------
function showProgressPanel() {
  const panel = document.getElementById('progress-panel');
  if (panel) panel.classList.remove('hidden');
}

function hideProgressPanel() {
  const panel = document.getElementById('progress-panel');
  if (panel) panel.classList.add('hidden');
}

function updateProgressPanel(data) {
  showProgressPanel();

  const stageBadge = document.getElementById('progress-stage-badge');
  const progressBar = document.getElementById('progress-bar');
  const progressMessage = document.getElementById('progress-message');
  const progressElapsed = document.getElementById('progress-elapsed');

  if (stageBadge) stageBadge.innerText = data.stage.toUpperCase();
  if (progressMessage) progressMessage.innerText = data.message;
  if (progressElapsed && data.elapsed_seconds) {
    progressElapsed.innerText = `${data.elapsed_seconds}s`;
  }

  // Calculate stage percentage
  const stages = ['ingestion', 'classification', 'extraction', 'scoring', 'kg_construction', 'contradiction_detection', 'gap_discovery', 'explanation', 'export', 'pipeline'];
  const idx = stages.indexOf(data.stage);
  const pct = Math.max(10, Math.min(100, Math.round(((idx + 1) / stages.length) * 100)));

  if (progressBar) progressBar.style.width = `${pct}%`;

  if (data.status === 'complete' && data.stage === 'pipeline') {
    setTimeout(() => {
      fetchStatus();
      fetchData();
      hideProgressPanel();
    }, 1500);
  }
}

// ----------------------------------------------------------------------
// Knowledge Graph Rendering (Cytoscape.js)
// ----------------------------------------------------------------------
async function fetchGraph() {
  try {
    const res = await fetch(`${API_BASE}/api/graph`);
    const data = await res.json();
    currentGraphData = data;

    const placeholder = document.getElementById('cy-placeholder');
    if (!data.nodes || data.nodes.length === 0) {
      if (placeholder) placeholder.classList.remove('hidden');
      return;
    }

    if (placeholder) placeholder.classList.add('hidden');
    renderCytoscape(data);
  } catch (err) {
    console.error('Failed to fetch graph:', err);
  }
}

function renderCytoscape(data) {
  const container = document.getElementById('cy-container');
  if (!container) return;

  const elements = [
    ...data.nodes.map(n => ({
      data: {
        id: n.data.id,
        label: n.data.label,
        type: n.data.type,
        doc_id: n.data.doc_id,
        is_bridge: n.data.is_bridge,
      }
    })),
    ...data.edges.map(e => ({
      data: {
        id: e.data.id,
        source: e.data.source,
        target: e.data.target,
        label: e.data.label,
        sentence: e.data.sentence,
        doc_id: e.data.doc_id,
        page: e.data.page,
        section: e.data.section,
      }
    }))
  ];

  cy = cytoscape({
    container: container,
    elements: elements,
    style: [
      {
        selector: 'node',
        style: {
          'label': 'data(label)',
          'color': '#f8fafc',
          'font-size': '10px',
          'font-family': 'Plus Jakarta Sans',
          'text-valign': 'bottom',
          'text-margin-y': 4,
          'width': 28,
          'height': 28,
          'background-color': '#64748b',
          'border-width': 2,
          'border-color': 'rgba(255, 255, 255, 0.2)',
          'transition-property': 'background-color, border-width, width, height',
          'transition-duration': '0.3s'
        }
      },
      {
        selector: 'node[type = "document"]',
        style: { 'background-color': '#3b82f6', 'width': 36, 'height': 36, 'shape': 'rectangle' }
      },
      {
        selector: 'node[type = "objective"]',
        style: { 'background-color': '#10b981' }
      },
      {
        selector: 'node[type = "methodology"]',
        style: { 'background-color': '#14b8a6' }
      },
      {
        selector: 'node[type = "dataset"]',
        style: { 'background-color': '#a855f7' }
      },
      {
        selector: 'node[type = "model"]',
        style: { 'background-color': '#f59e0b' }
      },
      {
        selector: 'node[type = "metric"]',
        style: { 'background-color': '#06b6d4' }
      },
      {
        selector: 'node[type = "limitation"], node[type = "research_gap"]',
        style: { 'background-color': '#ef4444' }
      },
      {
        selector: 'node[?is_bridge]',
        style: {
          'border-width': 4,
          'border-color': '#ec4899',
          'width': 40,
          'height': 40,
          'font-weight': 'bold'
        }
      },
      {
        selector: 'edge',
        style: {
          'width': 1.5,
          'line-color': 'rgba(148, 163, 184, 0.3)',
          'target-arrow-color': 'rgba(148, 163, 184, 0.5)',
          'target-arrow-shape': 'triangle',
          'curve-style': 'bezier',
          'label': 'data(label)',
          'font-size': '8px',
          'color': '#94a3b8',
          'text-rotation': 'autorotate'
        }
      },
      {
        selector: 'node:selected',
        style: {
          'border-color': '#38bdf8',
          'border-width': 4,
          'shadow-blur': 20,
          'shadow-color': '#38bdf8'
        }
      }
    ],
    layout: {
      name: 'cose',
      animate: true,
      animationDuration: 800,
      padding: 30
    }
  });

  // Node Selection Listener for Evidence Inspector
  cy.on('tap', 'node', (evt) => {
    const node = evt.target;
    inspectNode(node.data());
  });

  cy.on('tap', 'edge', (evt) => {
    const edge = evt.target;
    inspectEdge(edge.data());
  });
}

function filterGraphNodes(evt) {
  if (!cy) return;
  const q = evt.target.value.toLowerCase();
  cy.nodes().forEach(node => {
    const label = node.data('label').toLowerCase();
    if (!q || label.includes(q)) {
      node.style('opacity', 1);
    } else {
      node.style('opacity', 0.15);
    }
  });
}

// ----------------------------------------------------------------------
// Evidence Inspector Sidebar Updates
// ----------------------------------------------------------------------
function inspectNode(data) {
  const drawer = document.getElementById('evidence-drawer-content');
  if (!drawer) return;

  drawer.innerHTML = `
    <div class="glass-card p-4 rounded-xl border border-indigo-500/30 space-y-3">
      <div class="flex items-center justify-between">
        <span class="px-2 py-0.5 rounded text-[10px] font-bold font-mono bg-indigo-500/20 text-indigo-300 uppercase">${data.type}</span>
        ${data.is_bridge ? '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-pink-500/20 text-pink-300">Bridge Entity</span>' : ''}
      </div>
      <h4 class="text-sm font-bold text-white">${data.label}</h4>
      <div class="text-slate-400 space-y-1">
        <p><strong class="text-slate-300">ID:</strong> ${data.id}</p>
        <p><strong class="text-slate-300">Doc ID:</strong> ${data.doc_id || 'Cross-document'}</p>
      </div>
    </div>
  `;
}

function inspectEdge(data) {
  const drawer = document.getElementById('evidence-drawer-content');
  if (!drawer) return;

  drawer.innerHTML = `
    <div class="glass-card p-4 rounded-xl border border-purple-500/30 space-y-3">
      <div class="flex items-center justify-between">
        <span class="px-2 py-0.5 rounded text-[10px] font-bold font-mono bg-purple-500/20 text-purple-300 uppercase">Relation Edge</span>
        <span class="text-slate-400">${data.label}</span>
      </div>
      <div class="text-slate-400 space-y-1">
        <p><strong class="text-slate-300">Source:</strong> ${data.source}</p>
        <p><strong class="text-slate-300">Target:</strong> ${data.target}</p>
        <p><strong class="text-slate-300">Document:</strong> ${data.doc_id || 'N/A'}</p>
        <p><strong class="text-slate-300">Section:</strong> ${data.section || 'N/A'}</p>
        <p><strong class="text-slate-300">Page:</strong> ${data.page || 'N/A'}</p>
      </div>
      ${data.sentence ? `
        <div class="p-3 rounded-lg bg-slate-950/60 border border-white/10 italic text-slate-300">
          "${data.sentence}"
        </div>
      ` : ''}
    </div>
  `;
}

// ----------------------------------------------------------------------
// Contradictions Hub
// ----------------------------------------------------------------------
async function fetchContradictions() {
  try {
    const res = await fetch(`${API_BASE}/api/contradictions`);
    const data = await res.json();
    const container = document.getElementById('contradictions-list');
    if (!container) return;

    if (data.length === 0) {
      container.innerHTML = `
        <div class="glass-card p-8 rounded-2xl border border-white/10 text-center text-slate-400">
          <i data-lucide="shield-check" class="w-10 h-10 text-slate-600 mx-auto mb-2"></i>
          <p class="text-sm">No contradictions detected yet. Trigger a pipeline run to inspect claims.</p>
        </div>
      `;
      lucide.createIcons();
      return;
    }

    container.innerHTML = data.map(c => `
      <div class="glass-card p-5 rounded-2xl border ${c.confirmed ? 'border-rose-500/40 bg-rose-950/10' : 'border-amber-500/30'} space-y-4">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-3">
            <span class="px-3 py-1 rounded-full text-xs font-bold font-mono ${c.confirmed ? 'bg-rose-500/20 text-rose-300 border border-rose-500/40' : 'bg-amber-500/20 text-amber-300 border border-amber-500/40'}">
              ${c.confirmed ? 'Confirmed Contradiction' : 'Unconfirmed Candidate'}
            </span>
            <span class="text-xs text-slate-400">Bridge Entity: <strong class="text-pink-400">${c.bridge_entity || 'N/A'}</strong></span>
          </div>
          <div class="flex items-center gap-3 text-xs">
            <span>NLI Conf: <strong class="font-mono text-cyan-400">${(c.nli_confidence * 100).toFixed(0)}%</strong></span>
            <span>Methodology Sim: <strong class="font-mono text-purple-400">${c.methodology_similarity}</strong></span>
          </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <!-- Claim 1 -->
          <div class="claim-card-a p-4 rounded-xl space-y-2">
            <div class="flex items-center justify-between text-[11px] text-slate-400">
              <span class="font-bold text-indigo-400">${c.claim_1.doc_id}</span>
              <span>${c.claim_1.section || 'Section'} • Page ${c.claim_1.page || 1}</span>
            </div>
            <p class="text-xs text-slate-200 leading-relaxed font-mono">"${c.claim_1.sentence || c.claim_1.text}"</p>
          </div>

          <!-- Claim 2 -->
          <div class="claim-card-b p-4 rounded-xl space-y-2">
            <div class="flex items-center justify-between text-[11px] text-slate-400">
              <span class="font-bold text-pink-400">${c.claim_2.doc_id}</span>
              <span>${c.claim_2.section || 'Section'} • Page ${c.claim_2.page || 1}</span>
            </div>
            <p class="text-xs text-slate-200 leading-relaxed font-mono">"${c.claim_2.sentence || c.claim_2.text}"</p>
          </div>
        </div>

        <!-- Grounded RAG Explanation -->
        <div class="p-4 rounded-xl bg-slate-950/60 border border-white/10 text-xs text-slate-300 space-y-1">
          <p class="font-semibold text-slate-200 flex items-center gap-1.5">
            <i data-lucide="sparkles" class="w-3.5 h-3.5 text-indigo-400"></i>
            <span>Grounded Evidence Explanation</span>
          </p>
          <p class="text-slate-300 leading-relaxed">${c.explanation}</p>
        </div>
      </div>
    `).join('');

    lucide.createIcons();
  } catch (err) {
    console.error('Failed to fetch contradictions:', err);
  }
}

// ----------------------------------------------------------------------
// Research Gaps Explorer
// ----------------------------------------------------------------------
async function fetchGaps() {
  try {
    const res = await fetch(`${API_BASE}/api/gaps`);
    const data = await res.json();
    const container = document.getElementById('gaps-list');
    if (!container) return;

    if (data.length === 0) {
      container.innerHTML = `
        <div class="glass-card p-8 rounded-2xl border border-white/10 text-center text-slate-400 col-span-2">
          <i data-lucide="compass" class="w-10 h-10 text-slate-600 mx-auto mb-2"></i>
          <p class="text-sm">No research gaps discovered yet. Run pipeline analysis on your corpus.</p>
        </div>
      `;
      lucide.createIcons();
      return;
    }

    container.innerHTML = data.map(g => `
      <div class="glass-card p-5 rounded-2xl border border-amber-500/30 bg-amber-950/10 space-y-4 flex flex-col justify-between">
        <div class="space-y-3">
          <div class="flex items-center justify-between">
            <span class="px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-500/20 text-amber-300 border border-amber-500/40 font-mono">
              Novelty Score: ${(g.novelty_score * 100).toFixed(0)}%
            </span>
            <span class="text-xs text-slate-400">Bridge Entity: <strong class="text-pink-400">${g.entity}</strong></span>
          </div>

          <h4 class="text-sm font-bold text-white">${g.description}</h4>

          <div class="p-3 rounded-xl bg-slate-950/60 border border-white/10 text-xs text-slate-300 space-y-1">
            <p class="font-semibold text-slate-200">Opportunity Grounding:</p>
            <p class="text-slate-400">${g.explanation}</p>
          </div>
        </div>

        <div class="pt-3 border-t border-white/10 flex items-center justify-between text-xs text-slate-400">
          <span>Connected Papers: <strong class="text-indigo-300">${g.doc_1_id} ↔ ${g.doc_2_id}</strong></span>
          <span>Density: <strong class="font-mono text-cyan-400">${g.connection_density}</strong></span>
        </div>
      </div>
    `).join('');

    lucide.createIcons();
  } catch (err) {
    console.error('Failed to fetch research gaps:', err);
  }
}

// ----------------------------------------------------------------------
// Documents & Relationship Scores
// ----------------------------------------------------------------------
async function fetchDocuments() {
  try {
    const res = await fetch(`${API_BASE}/api/documents`);
    const data = await res.json();
    const tbody = document.getElementById('docs-table-body');
    if (!tbody) return;

    if (data.length === 0) {
      tbody.innerHTML = `<tr><td colspan="6" class="py-4 text-center text-slate-500">No documents ingested yet.</td></tr>`;
      return;
    }

    tbody.innerHTML = data.map(d => `
      <tr class="hover:bg-slate-900/40 transition-colors">
        <td class="py-3 px-4 font-mono font-bold text-indigo-400">${d.doc_id}</td>
        <td class="py-3 px-4 text-slate-200">${d.title}</td>
        <td class="py-3 px-4">
          <span class="px-2 py-0.5 rounded text-[11px] font-semibold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
            ${d.category}
          </span>
        </td>
        <td class="py-3 px-4 font-mono text-cyan-400">${(d.category_confidence * 100).toFixed(0)}%</td>
        <td class="py-3 px-4 font-mono">${d.total_pages}</td>
        <td class="py-3 px-4 text-slate-400">${d.segments.join(', ')}</td>
      </tr>
    `).join('');
  } catch (err) {
    console.error('Failed to fetch documents:', err);
  }
}

async function fetchScores() {
  try {
    const res = await fetch(`${API_BASE}/api/scores`);
    const data = await res.json();
    const container = document.getElementById('scores-container');
    if (!container) return;

    if (data.length === 0) {
      container.innerHTML = `<p class="text-xs text-slate-500 col-span-2">Run scoring to calculate relatedness across 5 dimensions.</p>`;
      return;
    }

    container.innerHTML = data.map(s => `
      <div class="glass-card p-4 rounded-xl border border-white/10 space-y-3">
        <div class="flex items-center justify-between">
          <span class="font-bold text-indigo-300 text-xs">${s.doc_1_id} ↔ ${s.doc_2_id}</span>
          <span class="text-sm font-bold font-mono text-emerald-400">Score: ${s.composite_score}</span>
        </div>
        <div class="grid grid-cols-5 gap-2 text-[10px] text-center font-mono">
          <div class="p-1.5 rounded bg-slate-900/60"><span class="text-slate-500 block">Obj</span>${s.components.objective}</div>
          <div class="p-1.5 rounded bg-slate-900/60"><span class="text-slate-500 block">Meth</span>${s.components.methodology}</div>
          <div class="p-1.5 rounded bg-slate-900/60"><span class="text-slate-500 block">DS</span>${s.components.dataset}</div>
          <div class="p-1.5 rounded bg-slate-900/60"><span class="text-slate-500 block">Res</span>${s.components.results_metrics}</div>
          <div class="p-1.5 rounded bg-slate-900/60"><span class="text-slate-500 block">Cite</span>${s.components.citation}</div>
        </div>
      </div>
    `).join('');
  } catch (err) {
    console.error('Failed to fetch scores:', err);
  }
}

// ----------------------------------------------------------------------
// UI Helpers (Tabs, Modals, Sliders, Dropzone)
// ----------------------------------------------------------------------
function setupTabs() {
  const btns = document.querySelectorAll('.tab-btn');
  const contents = document.querySelectorAll('.tab-content');

  btns.forEach(btn => {
    btn.addEventListener('click', () => {
      const target = btn.getAttribute('data-tab');
      btns.forEach(b => b.classList.remove('active'));
      contents.forEach(c => c.classList.add('hidden'));

      btn.classList.add('active');
      const activeContent = document.getElementById(target);
      if (activeContent) activeContent.classList.remove('hidden');

      if (target === 'tab-graph' && cy) {
        setTimeout(() => cy.resize(), 100);
      }
    });
  });
}

function setupModals() {
  const modalUpload = document.getElementById('modal-upload');
  const modalWeights = document.getElementById('modal-weights');

  document.getElementById('btn-open-upload')?.addEventListener('click', () => modalUpload?.classList.remove('hidden'));
  document.getElementById('btn-close-upload')?.addEventListener('click', () => modalUpload?.classList.add('hidden'));

  document.getElementById('btn-open-weights')?.addEventListener('click', () => modalWeights?.classList.remove('hidden'));
  document.getElementById('btn-close-weights')?.addEventListener('click', () => modalWeights?.classList.add('hidden'));
}

function setupWeightSliders() {
  const sliders = ['obj', 'meth', 'ds', 'res', 'cite'].map(key => ({
    key: key,
    slider: document.getElementById(`slider-w-${key}`),
    val: document.getElementById(`val-w-${key}`)
  }));

  const weightSum = document.getElementById('weight-sum');

  function updateSum() {
    let sum = 0;
    sliders.forEach(item => {
      if (item.slider && item.val) {
        const v = parseFloat(item.slider.value);
        item.val.innerText = v.toFixed(2);
        sum += v;
      }
    });
    if (weightSum) {
      weightSum.innerText = sum.toFixed(2);
      weightSum.className = Math.abs(sum - 1.0) < 1e-4 ? 'font-mono text-emerald-400' : 'font-mono text-rose-400';
    }
  }

  sliders.forEach(item => {
    item.slider?.addEventListener('input', updateSum);
  });

  document.getElementById('btn-save-weights')?.addEventListener('click', async () => {
    const payload = {
      objective: parseFloat(document.getElementById('slider-w-obj').value),
      methodology: parseFloat(document.getElementById('slider-w-meth').value),
      dataset: parseFloat(document.getElementById('slider-w-ds').value),
      results_metrics: parseFloat(document.getElementById('slider-w-res').value),
      citation: parseFloat(document.getElementById('slider-w-cite').value)
    };

    try {
      const res = await fetch(`${API_BASE}/api/config/weights`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (res.ok) {
        alert('Weights updated successfully!');
        document.getElementById('modal-weights')?.classList.add('hidden');
      } else {
        alert(data.detail || 'Failed to update weights.');
      }
    } catch (err) {
      alert('Error saving weights: ' + err.message);
    }
  });
}

function setupDropzone() {
  const dropzone = document.getElementById('dropzone');
  const fileInput = document.getElementById('file-input');
  const uploadStatus = document.getElementById('upload-status');

  if (!dropzone || !fileInput) return;

  dropzone.addEventListener('click', () => fileInput.click());

  dropzone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropzone.classList.add('border-cyan-400');
  });

  dropzone.addEventListener('dragleave', () => {
    dropzone.classList.remove('border-cyan-400');
  });

  dropzone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropzone.classList.remove('border-cyan-400');
    if (e.dataTransfer.files.length > 0) {
      handleFiles(e.dataTransfer.files);
    }
  });

  fileInput.addEventListener('change', () => {
    if (fileInput.files.length > 0) {
      handleFiles(fileInput.files);
    }
  });

  async function handleFiles(files) {
    for (const file of files) {
      if (!file.name.endsWith('.pdf')) continue;
      const formData = new FormData();
      formData.append('file', file);

      if (uploadStatus) uploadStatus.innerText = `Uploading ${file.name}...`;

      try {
        const res = await fetch(`${API_BASE}/api/upload`, {
          method: 'POST',
          body: formData
        });
        const data = await res.json();
        if (res.ok) {
          if (uploadStatus) uploadStatus.innerText = `Uploaded: ${file.name}`;
          fetchStatus();
        } else {
          if (uploadStatus) uploadStatus.innerText = `Error: ${data.detail}`;
        }
      } catch (err) {
        if (uploadStatus) uploadStatus.innerText = `Upload failed: ${err.message}`;
      }
    }
  }
}
