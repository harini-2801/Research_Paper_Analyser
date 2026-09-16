/* ==========================================================================
   Research Paper Relationship Analyzer - web client

   Talks to the FastAPI backend in rpra/server.py. Every fetch here maps to a
   route defined there; if a shape changes, it changes in both places.
   ========================================================================== */

(function () {
  "use strict";

  // When the page is served by the API itself, same-origin works. When it is
  // served from a static host (Vercel), point it at the API with
  // window.RPRA_API_BASE or ?api=https://host.
  var API_BASE = (function () {
    var fromQuery = new URLSearchParams(window.location.search).get("api");
    if (fromQuery) return fromQuery.replace(/\/$/, "");
    if (window.RPRA_API_BASE) return String(window.RPRA_API_BASE).replace(/\/$/, "");
    return "";
  })();

  // Where the frozen demo bundle lives depends on how the page is served:
  // the FastAPI app mounts it under /static, a plain static host serves it
  // beside index.html. Try both rather than assume one.
  // Above this spread a "bridge" concept links nearly every paper and tells
  // you nothing about any specific pair of them.
  var BRIDGE_MAX_SPREAD = 4;
  // Even after dropping the hubs, every qualifying concept at once is busy.
  var BRIDGE_MAX_SHOWN = 40;

  var DEMO_URLS = ["/static/demo/data.json", "./demo/data.json", "demo/data.json"];

  var state = {
    demoMode: false,
    demo: null,
    status: null,
    documents: [],
    contradictions: [],
    gaps: [],
    scores: [],
    graph: { nodes: [], edges: [], bridge_entities: {} },
    weights: { objective: 0.25, methodology: 0.25, dataset: 0.2, results_metrics: 0.2, citation: 0.1 },
    draftWeights: null,
    cy: null,
    running: false,
    selectedDoc: null,
    confirmedOnly: false,
  };

  var STAGES = [
    "corpus_fetch",
    "ingestion", "citations", "classification", "extraction", "embedding",
    "scoring", "kg_construction", "contradiction_detection", "gap_discovery",
    "explanation", "export",
  ];

  var STAGE_LABELS = {
    ingestion: "Ingesting PDFs",
    citations: "Parsing references",
    classification: "Classifying",
    extraction: "Extracting entities",
    embedding: "Embedding",
    corpus_fetch: "Fetching papers",
    scoring: "Scoring pairs",
    kg_construction: "Building graph",
    contradiction_detection: "Finding contradictions",
    gap_discovery: "Discovering gaps",
    explanation: "Explaining",
    export: "Exporting",
    pipeline: "Pipeline",
  };

  var WEIGHT_LABELS = {
    objective: "Objective",
    methodology: "Methodology",
    dataset: "Dataset",
    results_metrics: "Results & metrics",
    citation: "Citation",
  };

  // Shape is the secondary encoding for entity type, so identity never rests
  // on hue alone. Keys match EntityType in rpra/models.py.
  var ENTITY_SHAPES = {
    dataset: "hexagon",
    model: "round-rectangle",
    methodology: "ellipse",
    evaluation_metric: "triangle",
    quantitative_result: "diamond",
    objective: "pentagon",
    limitation: "vee",
    research_gap: "star",
  };

  // ------------------------------------------------------------------
  // Utilities
  // ------------------------------------------------------------------

  function $(id) { return document.getElementById(id); }
  function el(tag, cls) { var n = document.createElement(tag); if (cls) n.className = cls; return n; }

  function esc(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function cssVar(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  function fmt(n, digits) {
    if (n == null || isNaN(n)) return "0";
    return Number(n).toFixed(digits == null ? 2 : digits);
  }

  function shortDoc(id) {
    if (!id) return "";
    return id.length > 30 ? id.slice(0, 28) + "…" : id;
  }

  function titleFor(docId) {
    var doc = state.documents.find(function (d) { return d.doc_id === docId; });
    return doc && doc.title ? doc.title : docId;
  }

  async function api(path, options) {
    var response = await fetch(API_BASE + path, options);
    if (!response.ok) {
      var detail = response.statusText;
      try {
        var body = await response.json();
        detail = body.detail || detail;
        if (Array.isArray(detail)) detail = detail.map(function (d) { return d.msg; }).join("; ");
      } catch (e) { /* non-JSON error body */ }
      throw new Error(detail);
    }
    return response.json();
  }

  function toast(message, kind) {
    var host = $("toasts");
    var node = el("div", "toast" + (kind ? " toast--" + kind : ""));
    var glyph = kind === "error"
      ? '<path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0zM12 9v4M12 17h.01"/>'
      : '<path d="M20 6 9 17l-5-5"/>';
    node.innerHTML =
      '<svg class="toast__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
      'stroke-linecap="round" stroke-linejoin="round">' + glyph + "</svg>" +
      "<span>" + esc(message) + "</span>";
    host.appendChild(node);
    setTimeout(function () { node.remove(); }, 4800);
  }

  function emptyState(icon, title, body) {
    return '<div class="empty">' +
      '<svg class="empty__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
      'stroke-linecap="round" stroke-linejoin="round">' + icon + "</svg>" +
      '<p class="empty__title">' + esc(title) + "</p>" +
      '<p class="empty__body">' + esc(body) + "</p></div>";
  }

  var ICON_SEARCH = '<circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/>';

  // ------------------------------------------------------------------
  // Theme
  // ------------------------------------------------------------------

  function applyTheme(theme) {
    if (theme) {
      document.documentElement.setAttribute("data-theme", theme);
      try { localStorage.setItem("rpra-theme", theme); } catch (e) { /* private mode */ }
    }
    var dark = document.documentElement.getAttribute("data-theme") === "dark" ||
      (!document.documentElement.hasAttribute("data-theme") &&
        window.matchMedia("(prefers-color-scheme: dark)").matches);

    $("icon-theme").innerHTML = dark
      ? '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>'
      : '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>';

    if (state.cy) applyGraphStyle(state.cy);
    if (state.scores.length) renderRelationships();
  }

  function initTheme() {
    var stored = null;
    try { stored = localStorage.getItem("rpra-theme"); } catch (e) { /* ignore */ }
    if (stored) document.documentElement.setAttribute("data-theme", stored);
    applyTheme(null);
  }

  // ------------------------------------------------------------------
  // WebSocket progress
  // ------------------------------------------------------------------

  function setConn(stateName, label) {
    if (state.demoMode && stateName !== "demo") return;
    $("conn").setAttribute("data-state", stateName);
    $("conn-label").textContent = label;
  }

  function connectSocket() {
    var base = API_BASE || window.location.origin;
    var url = base.replace(/^http/, "ws") + "/ws/progress";
    var socket;

    try {
      socket = new WebSocket(url);
    } catch (e) {
      setConn("down", "offline");
      return;
    }

    socket.onopen = function () {
      state.socketRetries = 0;
      setConn("live", "live");
      // The server only uses inbound frames as a keepalive signal.
      setInterval(function () {
        if (socket.readyState === WebSocket.OPEN) socket.send("ping");
      }, 25000);
    };

    socket.onmessage = function (event) {
      var payload;
      try { payload = JSON.parse(event.data); } catch (e) { return; }
      handleProgress(payload);
    };

    socket.onclose = function () {
      // On a static host there is no socket to reconnect to. Retrying forever
      // would spam the console and overwrite the demo-mode label.
      if (state.demoMode) return;
      setConn("down", "reconnecting");
      state.socketRetries = (state.socketRetries || 0) + 1;
      if (state.socketRetries <= 5) {
        setTimeout(connectSocket, 3000 * state.socketRetries);
      } else {
        setConn("down", "no live backend");
      }
    };

    socket.onerror = function () {
      if (!state.demoMode) setConn("down", "offline");
    };
  }

  function handleProgress(event) {
    var stageLabel = STAGE_LABELS[event.stage] || event.stage;
    $("status-stage").textContent = stageLabel;
    $("status-message").textContent = event.message || "";

    var index = STAGES.indexOf(event.stage);
    if (index >= 0) {
      var pct = Math.round(((index + 1) / STAGES.length) * 100);
      $("status-fill").style.width = pct + "%";
    }
    if (event.elapsed_seconds) {
      $("status-elapsed").textContent = fmt(event.elapsed_seconds, 1) + "s";
    }

    if (event.stage === "corpus_fetch" && event.status === "complete") {
      toast(event.message, "success");
      refreshStatus().then(renderEverything);
      return;
    }

    if (event.type === "complete") {
      $("status-fill").style.width = "100%";
      $("status-stage").textContent = "complete";
      setRunning(false);
      toast("Analysis complete in " + fmt(event.details && event.details.elapsed_seconds, 1) + "s", "success");
      refreshAll();
    } else if (event.type === "error" || (event.stage === "pipeline" && event.status === "failed")) {
      // Only a pipeline-level failure is terminal. Per-document failures are
      // expected on a corpus with one unreadable PDF and must not stop the UI.
      setRunning(false);
      setConn("live", "live");
      toast(event.message || "Pipeline failed", "error");
      $("status-stage").textContent = "failed";
    } else if (event.status === "failed" && event.doc_id) {
      toast(event.message || ("Could not process " + event.doc_id), "error");
    }
  }

  function setRunning(running) {
    state.running = running;
    $("btn-run").disabled = running;
    $("btn-run").innerHTML = running
      ? '<svg class="icon spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round"><path d="M12 2a10 10 0 0 1 10 10"/></svg> Running…'
      : '<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"><path d="M5 3l14 9-14 9V3z"/></svg> Run analysis';
    setConn(running ? "busy" : "live", running ? "analysing" : "live");
  }

  // ------------------------------------------------------------------
  // Data loading
  // ------------------------------------------------------------------

  /**
   * Load the frozen demo bundle.
   *
   * On a static host there is no backend, so every panel would sit empty and
   * the app would look broken. The bundle holds the exact API payloads from a
   * real run, so everything except starting a new run keeps working.
   */
  async function enterDemoMode(reason) {
    if (state.demo) return true;

    for (var i = 0; i < DEMO_URLS.length; i++) {
      try {
        var response = await fetch(DEMO_URLS[i]);
        if (!response.ok) continue;
        state.demo = await response.json();
        break;
      } catch (e) { /* try the next candidate */ }
    }

    if (!state.demo) {
      setConn("down", "no backend");
      return false;
    }

    state.demoMode = true;
    state.status = state.demo.status;
    state.documents = state.demo.documents || [];
    state.contradictions = state.demo.contradictions || [];
    state.gaps = state.demo.gaps || [];
    state.scores = state.demo.scores || [];
    state.graph = state.demo.graph || { nodes: [], edges: [], bridge_entities: {} };
    if (state.status && state.status.config && state.status.config.weights) {
      state.weights = state.status.config.weights;
    }

    setConn("demo", "demo data");
    var banner = $("demo-banner");
    banner.setAttribute("data-show", "true");
    $("demo-banner-text").textContent =
      "Showing a saved analysis of " + state.documents.length +
      " arXiv papers. " + (reason || "No backend is connected") +
      " — browsing works, starting a new run needs a live API.";
    $("btn-run").disabled = true;
    $("btn-run").title = "Connect a backend to run the pipeline";
    return true;
  }

  async function refreshStatus() {
    try {
      var status = await api("/api/status");
      state.status = status;
      if (status.config && status.config.weights) {
        state.weights = status.config.weights;
      }
      renderFigures();
      renderCorpusRail();
      $("backend-line").textContent =
        (status.summary && status.summary.extraction_backend
          ? status.summary.extraction_backend + " extraction · "
          : "") +
        (status.summary && status.summary.embedding_backend
          ? status.summary.embedding_backend + " embeddings"
          : "knowledge graph · contradictions · research gaps");
      $("btn-export").disabled = !status.has_results;
      if (status.status === "running" && !state.running) setRunning(true);
      setConn(state.running ? "busy" : "live", state.running ? "analysing" : "live");
      state.demoMode = false;
      $("demo-banner").setAttribute("data-show", "false");
      return true;
    } catch (e) {
      return false;
    }
  }

  async function refreshAll() {
    var live = await refreshStatus();

    if (!live) {
      var loaded = await enterDemoMode("The API at this address did not respond");
      if (loaded) {
        renderEverything();
        return;
      }
      renderEverything();
      return;
    }

    var results = await Promise.allSettled([
      api("/api/documents"),
      api("/api/contradictions"),
      api("/api/gaps"),
      api("/api/scores"),
      api("/api/graph"),
    ]);

    if (results[0].status === "fulfilled") state.documents = results[0].value;
    if (results[1].status === "fulfilled") state.contradictions = results[1].value;
    if (results[2].status === "fulfilled") state.gaps = results[2].value;
    if (results[3].status === "fulfilled") state.scores = results[3].value;
    if (results[4].status === "fulfilled") state.graph = results[4].value;

    renderEverything();
  }

  function renderEverything() {
    $("count-docs").textContent = state.documents.length;
    $("count-contradictions").textContent = state.contradictions.length;
    $("count-gaps").textContent = state.gaps.length;
    $("count-scores").textContent = state.scores.length;

    renderFigures();
    renderCorpusRail();
    renderGraph();
    renderRelationships();
    renderContradictions();
    renderGaps();
    renderDocuments();
  }

  // ------------------------------------------------------------------
  // Figures
  // ------------------------------------------------------------------

  function renderFigures() {
    var status = state.status || {};
    var summary = status.summary || {};

    $("fig-papers").textContent = status.pdf_count || 0;
    $("fig-papers-note").textContent = summary.documents
      ? summary.documents + " analysed"
      : (status.pdf_count ? "not yet analysed" : "none ingested");

    $("fig-nodes").textContent = summary.kg_nodes || 0;
    $("fig-nodes-note").textContent = (summary.kg_edges || 0) + " edges";

    $("fig-bridges").textContent = summary.bridge_entities || 0;
    $("fig-bridges-note").textContent = (summary.entities || 0) + " entities total";

    $("fig-contradictions").textContent = summary.contradictions || 0;
    $("fig-contradictions-note").textContent = (summary.confirmed_contradictions || 0) + " confirmed";

    $("fig-gaps").textContent = summary.gaps || 0;
    $("fig-gaps-note").textContent = "novelty ranked";
  }

  // ------------------------------------------------------------------
  // Corpus rail
  // ------------------------------------------------------------------

  function renderCorpusRail() {
    var list = $("corpus-list");
    var files = (state.status && state.status.pdf_files) || [];
    $("corpus-count").textContent = files.length + (files.length === 1 ? " paper" : " papers");
    list.innerHTML = "";

    if (!files.length) {
      var note = el("li");
      note.className = "hint";
      note.style.padding = "14px 10px";
      note.innerHTML =
        "No papers in the corpus yet. Drop PDFs below, or " +
        '<button class="btn btn--ghost" id="btn-seed" style="padding:2px 6px">' +
        "load the sample corpus</button>.";
      list.appendChild(note);

      var seedBtn = $("btn-seed");
      if (seedBtn) {
        seedBtn.addEventListener("click", async function () {
          if (state.demoMode) {
            toast("Connect a backend first.", "error");
            return;
          }
          seedBtn.disabled = true;
          try {
            var res = await api("/api/corpus/seed", { method: "POST" });
            toast(res.message, "success");
            refreshStatus().then(renderCorpusRail);
          } catch (err) {
            toast(err.message, "error");
          } finally {
            seedBtn.disabled = false;
          }
        });
      }
      return;
    }

    files.forEach(function (filename) {
      var docId = filename.replace(/\.pdf$/i, "");
      var doc = state.documents.find(function (d) { return d.doc_id === docId; });

      var item = el("li", "corpus-item");
      item.setAttribute("role", "option");
      item.setAttribute("aria-selected", state.selectedDoc === docId ? "true" : "false");

      var meta = doc
        ? esc(doc.category) + " · " + doc.segment_count + " sections · p." + doc.total_pages
        : "not analysed";

      item.innerHTML =
        '<svg class="corpus-item__glyph" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
        'stroke-linecap="round" stroke-linejoin="round">' +
        '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/></svg>' +
        '<span class="corpus-item__body">' +
        '<span class="corpus-item__title">' + esc(doc && doc.title ? doc.title : docId) + "</span>" +
        '<span class="corpus-item__meta">' + meta + "</span></span>" +
        '<button class="corpus-item__remove" title="Remove from corpus" aria-label="Remove ' + esc(filename) + '">' +
        '<svg class="icon icon--sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
        'stroke-linecap="round"><path d="M18 6 6 18M6 6l12 12"/></svg></button>';

      item.addEventListener("click", function (evt) {
        if (evt.target.closest(".corpus-item__remove")) return;
        state.selectedDoc = state.selectedDoc === docId ? null : docId;
        renderCorpusRail();
        if (doc) inspectDocument(doc);
        if (state.cy) focusNode(docId);
      });

      item.querySelector(".corpus-item__remove").addEventListener("click", async function (evt) {
        evt.stopPropagation();
        try {
          await api("/api/corpus/" + encodeURIComponent(filename), { method: "DELETE" });
          toast("Removed " + filename, "success");
          refreshStatus();
        } catch (err) {
          toast(err.message, "error");
        }
      });

      list.appendChild(item);
    });
  }

  // ------------------------------------------------------------------
  // Knowledge graph
  // ------------------------------------------------------------------

  function applyGraphStyle(cy) {
    var docColor = cssVar("--cat-document");
    var bridgeColor = cssVar("--cat-bridge");
    var entityColor = cssVar("--cat-entity");
    var ink = cssVar("--ink-primary");
    var muted = cssVar("--ink-muted");
    var rule = cssVar("--rule-strong");
    var surface = cssVar("--bg-page");
    var accent = cssVar("--accent");
    var rampLow = cssVar("--seq-200");
    var rampHigh = cssVar("--seq-600");

    cy.style()
      .resetToDefault()
      .selector("node")
      .style({
        "background-color": entityColor,
        shape: "ellipse",
        width: 17,
        height: 17,
        label: "data(short_label)",
        "font-size": 7.5,
        "font-family": "Inter, system-ui, sans-serif",
        color: muted,
        "text-valign": "bottom",
        "text-margin-y": 3,
        "text-max-width": 88,
        "text-wrap": "ellipsis",
        "border-width": 1.5,
        "border-color": surface,
        "overlay-opacity": 0,
      })
      .selector('node[node_type = "document"]')
      .style({
        "background-color": docColor,
        shape: "round-rectangle",
        // Sized by how many papers it links to, so the hubs of the literature
        // are visible before you read a single label.
        width: "mapData(degree, 0, 12, 56, 104)",
        height: "mapData(degree, 0, 12, 30, 46)",
        "font-size": 11,
        "font-weight": 700,
        color: ink,
        "text-max-width": 150,
        "text-wrap": "wrap",
        "text-valign": "center",
        "text-margin-y": 0,
        "text-outline-color": surface,
        "text-outline-width": 2.5,
        "border-width": 2,
        "border-color": docColor,
        "border-opacity": 0.45,
        "z-index": 10,
        // Cytoscape has no blur, so the glow is a wide translucent border.
        "shadow-blur": 18,
        "shadow-color": docColor,
        "shadow-opacity": 0.7,
      })
      .selector('node[node_type = "bridge_entity"]')
      .style({
        "background-color": bridgeColor,
        shape: "diamond",
        width: 30,
        height: 30,
        "font-size": 9.5,
        "font-weight": 700,
        color: ink,
        "border-width": 2,
        "border-color": bridgeColor,
        "border-opacity": 0.45,
        "z-index": 8,
        "shadow-blur": 16,
        "shadow-color": bridgeColor,
        "shadow-opacity": 0.7,
      });

    // Shape per entity type: the secondary channel that keeps identity legible
    // without relying on hue.
    Object.keys(ENTITY_SHAPES).forEach(function (type) {
      cy.style().selector('node[entity_type = "' + type + '"]').style({ shape: ENTITY_SHAPES[type] });
    });

    cy.style()
      .selector("edge")
      .style({
        width: 1,
        "line-color": rule,
        "curve-style": "bezier",
        "target-arrow-shape": "none",
        opacity: 0.55,
        "overlay-opacity": 0,
      })
      .selector('edge[edge_type = "contains"]')
      .style({ "line-style": "dotted", opacity: 0.3, width: 0.8 })
      .selector('edge[edge_type = "has_bridge_entity"]')
      .style({ "line-color": bridgeColor, opacity: 0.5, width: 1.4 })
      .selector('edge[edge_type = "relationship_score"]')
      .style({
        "line-color": "mapData(composite_score, 0.3, 0.7, " + rampLow + ", " + rampHigh + ")",
        // Width and opacity both carry the score, so the strongest links read
        // first even at low zoom.
        width: "mapData(composite_score, 0.3, 0.7, 1, 9)",
        opacity: "mapData(composite_score, 0.3, 0.7, 0.35, 0.95)",
        "curve-style": "straight",
      })
      .selector('edge[edge_type = "cites"]')
      .style({
        "line-color": docColor,
        "target-arrow-shape": "triangle",
        "target-arrow-color": docColor,
        "arrow-scale": 0.7,
        width: 1.6,
        "line-style": "dashed",
        opacity: 0.9,
      })
      .selector(".dimmed")
      .style({ opacity: 0.06 })
      .selector(".highlight")
      .style({
        "border-width": 4,
        "border-color": accent,
        "border-opacity": 1,
        "shadow-blur": 26,
        "shadow-color": accent,
        "shadow-opacity": 0.95,
        "z-index": 30,
      })
      .update();
  }

  /**
   * Build the elements for a view.
   *
   * Drawing the whole graph at once is what made it unreadable: 1219 nodes,
   * and the concepts that connect the most papers - "accuracy", "transformer" -
   * are hubs that drag every paper into one ball. Each view answers a different
   * question and draws only what that question needs.
   */
  function buildElements(view, threshold) {
    var all = state.graph.nodes || [];
    var edges = state.graph.edges || [];
    var docs = all.filter(function (n) { return n.data.node_type === "document"; });

    if (view === "full") {
      return { nodes: all, edges: edges };
    }

    if (view === "network") {
      // How are these papers related? Papers only, linked where the composite
      // score clears the threshold, plus any direct citations between them.
      var keptEdges = edges.filter(function (e) {
        var d = e.data;
        if (d.edge_type === "cites") return true;
        return d.edge_type === "relationship_score" &&
          typeof d.composite_score === "number" &&
          d.composite_score >= threshold;
      });

      var degree = {};
      keptEdges.forEach(function (e) {
        degree[e.data.source] = (degree[e.data.source] || 0) + 1;
        degree[e.data.target] = (degree[e.data.target] || 0) + 1;
      });

      var sized = docs.map(function (n) {
        return {
          data: Object.assign({}, n.data, { degree: degree[n.data.id] || 0 }),
        };
      });
      return { nodes: sized, edges: keptEdges };
    }

    // "bridges": which concepts actually link papers together?
    // A concept shared by nearly every paper says nothing about any pair of
    // them, so only the discriminating ones are drawn.
    var spread = state.graph.bridge_entities || {};
    var informative = {};
    Object.keys(spread).forEach(function (text) {
      var count = new Set(spread[text]).size;
      if (count >= 2 && count <= BRIDGE_MAX_SPREAD) informative[text.toLowerCase()] = count;
    });

    var bridgeNodes = all
      .filter(function (n) {
        return n.data.node_type === "bridge_entity" &&
          informative[String(n.data.label || "").toLowerCase()] !== undefined;
      })
      // Fewest papers first: a concept shared by two is the most telling.
      .sort(function (a, b) {
        return informative[String(a.data.label).toLowerCase()] -
               informative[String(b.data.label).toLowerCase()];
      })
      .slice(0, BRIDGE_MAX_SHOWN);

    var visible = {};
    docs.concat(bridgeNodes).forEach(function (n) { visible[n.data.id] = true; });

    var bridgeEdges = edges.filter(function (e) {
      return e.data.edge_type === "has_bridge_entity" &&
        visible[e.data.source] && visible[e.data.target];
    });

    return { nodes: docs.concat(bridgeNodes), edges: bridgeEdges };
  }

  function renderGraph() {
    var host = $("graph-host");
    var empty = $("graph-empty");

    if (!(state.graph.nodes || []).length) {
      if (empty) empty.style.display = "";
      if (state.cy) { state.cy.destroy(); state.cy = null; }
      updateGraphCount(0, 0);
      return;
    }
    if (empty) empty.style.display = "none";
    if (state.cy) { state.cy.destroy(); state.cy = null; }

    var view = $("graph-view").value;
    var threshold = parseFloat($("graph-threshold").value);
    var elements = buildElements(view, threshold);

    var cy = cytoscape({
      container: host,
      elements: elements,
      wheelSensitivity: 0.22,
      minZoom: 0.1,
      maxZoom: 3.5,
    });

    state.cy = cy;
    applyGraphStyle(cy);
    applyGraphSearch();
    runLayout(cy, view);

    cy.on("tap", "node", function (evt) {
      highlightNeighbourhood(cy, evt.target);
      inspectNode(evt.target.data());
    });
    cy.on("tap", "edge", function (evt) { inspectEdge(evt.target.data()); });
    cy.on("tap", function (evt) {
      if (evt.target === cy) {
        cy.elements().removeClass("dimmed highlight");
        clearInspector();
      }
    });

    updateGraphCount(cy.nodes().length, (state.graph.nodes || []).length);
    updateLegendNote(view);
  }

  function updateGraphCount(shown, total) {
    var counter = $("graph-count");
    if (counter) counter.textContent = shown + " of " + total + " nodes";
  }

  function updateLegendNote(view) {
    var note = $("legend-note");
    if (!note) return;
    if (view === "network") note.textContent = "thicker link = more related";
    else if (view === "bridges") note.textContent =
      "concepts shared by 2–" + BRIDGE_MAX_SPREAD + " papers only";
    else note.textContent = "shape encodes entity type";

    var entityLegend = document.querySelector(".legend__item--entity");
    if (entityLegend) entityLegend.style.display = view === "full" ? "" : "none";
  }

  function runLayout(cy, view) {
    var count = cy.nodes().length;

    if (view === "network") {
      // Only ~30 nodes, so they can be spread generously. Edge length is
      // inverse to the score, which puts strongly related papers side by side
      // and lets the clusters place themselves.
      cy.layout({
        name: "cose",
        animate: false,
        randomize: true,
        nodeRepulsion: 42000,
        idealEdgeLength: function (edge) {
          var score = edge.data("composite_score");
          return typeof score === "number" ? 70 + (1 - score) * 280 : 190;
        },
        edgeElasticity: 160,
        gravity: 14,
        numIter: 1600,
        padding: 60,
        nodeDimensionsIncludeLabels: true,
      }).run();
    } else {
      var iterations = count > 600 ? 320 : count > 250 ? 700 : 1200;
      cy.layout({
        name: "cose",
        animate: false,
        randomize: true,
        nodeRepulsion: count > 300 ? 14000 : 26000,
        idealEdgeLength: count > 300 ? 110 : 170,
        edgeElasticity: 130,
        gravity: 22,
        numIter: iterations,
        padding: 50,
        nodeDimensionsIncludeLabels: true,
      }).run();
    }

    cy.fit(undefined, 45);
  }

  function highlightNeighbourhood(cy, node) {
    cy.elements().addClass("dimmed").removeClass("highlight");
    node.closedNeighborhood().removeClass("dimmed");
    node.addClass("highlight");
  }

  function focusNode(nodeId) {
    if (!state.cy) return;
    var node = state.cy.getElementById(nodeId);
    if (!node || !node.length) return;
    highlightNeighbourhood(state.cy, node);
    state.cy.animate({ center: { eles: node }, zoom: 1.2 }, { duration: 320 });
  }

  /** Dim nodes that do not match the search box, rather than removing them. */
  function applyGraphSearch() {
    if (!state.cy) return;
    var query = $("graph-search").value.trim().toLowerCase();

    state.cy.batch(function () {
      if (!query) {
        state.cy.elements().removeClass("dimmed");
        return;
      }
      state.cy.elements().addClass("dimmed");
      state.cy.nodes().forEach(function (node) {
        if (String(node.data("label") || "").toLowerCase().indexOf(query) >= 0) {
          node.removeClass("dimmed");
          node.connectedEdges().removeClass("dimmed");
        }
      });
    });
  }

  // ------------------------------------------------------------------
  // Evidence inspector
  // ------------------------------------------------------------------

  function citation(evidence) {
    var parts = [evidence.source_doc_id];
    if (evidence.section) parts.push("§" + evidence.section);
    if (evidence.page_number) parts.push("p." + evidence.page_number);
    return parts.join(" · ");
  }

  function evidenceBlock(evidence, variant) {
    if (!evidence || !evidence.sentence_span) return "";
    return '<div class="evidence' + (variant ? " evidence--" + variant : "") + '">' +
      '<div class="evidence__quote">“' + esc(evidence.sentence_span) + "”</div>" +
      '<cite class="evidence__cite">' + esc(citation(evidence)) + "</cite></div>";
  }

  function setInspector(html) { $("inspector-body").innerHTML = html; }

  function clearInspector() {
    setInspector(emptyState(
      '<path d="M3 3h18v18H3zM7 8h10M7 12h10M7 16h6"/>',
      "Nothing selected",
      "Select a graph node, a contradiction, or a research gap to see the verbatim sentences it was derived from, with section and page."
    ));
  }

  function kv(pairs) {
    return '<div class="kv">' + pairs.map(function (pair) {
      return '<span class="kv__k">' + esc(pair[0]) + '</span><span class="kv__v">' + pair[1] + "</span>";
    }).join("") + "</div>";
  }

  function inspectNode(data) {
    var kindLabel = data.node_type === "document" ? "Paper"
      : data.node_type === "bridge_entity" ? "Bridge concept" : "Entity";

    var rows = [["Type", esc(kindLabel)]];
    if (data.entity_type) rows.push(["Entity type", esc(data.entity_type.replace(/_/g, " "))]);
    if (data.category) rows.push(["Category", esc(data.category)]);
    if (data.doc_id) rows.push(["Paper", esc(data.doc_id)]);
    if (data.section) rows.push(["Section", esc(data.section)]);
    if (data.page_number) rows.push(["Page", esc(data.page_number)]);

    var html = '<div class="inspector__section">' +
      '<span class="eyebrow">' + esc(kindLabel) + "</span>" +
      '<h3 style="font-size:14.5px;margin-top:5px">' + esc(data.label) + "</h3>" +
      kv(rows) + "</div>";

    if (data.sentence_span) {
      html += '<div class="inspector__section"><span class="eyebrow">Source sentence</span>' +
        evidenceBlock({
          sentence_span: data.sentence_span,
          source_doc_id: data.doc_id,
          section: data.section,
          page_number: data.page_number,
        }) + "</div>";
    }

    if (data.node_type === "bridge_entity") {
      var sharing = state.graph.bridge_entities[data.label] || [];
      if (sharing.length) {
        html += '<div class="inspector__section"><span class="eyebrow">Shared by ' +
          sharing.length + ' papers</span><ul style="margin:7px 0 0;padding-left:16px;font-size:12px">' +
          sharing.map(function (id) { return "<li>" + esc(titleFor(id)) + "</li>"; }).join("") +
          "</ul></div>";
      }
    }

    setInspector(html);
  }

  function inspectEdge(data) {
    var rows = [["Relation", esc(String(data.edge_type).replace(/[-_]/g, " "))]];
    if (data.composite_score != null) rows.push(["Score", fmt(data.composite_score, 3)]);
    if (data.confidence != null) rows.push(["Confidence", fmt(data.confidence, 2)]);
    if (data.is_cross_document) rows.push(["Scope", "cross-document"]);

    var html = '<div class="inspector__section"><span class="eyebrow">Relation</span>' +
      '<h3 style="font-size:14px;margin-top:5px">' + esc(shortDoc(data.source)) +
      " → " + esc(shortDoc(data.target)) + "</h3>" + kv(rows) + "</div>";

    if (data.sentence_span) {
      html += '<div class="inspector__section"><span class="eyebrow">Evidence</span>' +
        evidenceBlock({
          sentence_span: data.sentence_span,
          source_doc_id: data.source_doc_id,
          section: data.section,
          page_number: data.page_number,
        }) + "</div>";
    }
    setInspector(html);
  }

  function inspectDocument(doc) {
    var html = '<div class="inspector__section"><span class="eyebrow">Paper</span>' +
      '<h3 style="font-size:14.5px;margin-top:5px">' + esc(doc.title) + "</h3>" +
      kv([
        ["ID", esc(doc.doc_id)],
        ["Category", esc(doc.category) + " (" + fmt(doc.category_confidence, 2) + ")"],
        ["Pages", esc(doc.total_pages)],
        ["Sections", esc(doc.segment_count)],
        ["References", esc(doc.reference_count)],
      ]) + "</div>";

    var related = state.scores
      .filter(function (s) { return s.doc_a === doc.doc_id || s.doc_b === doc.doc_id; })
      .slice(0, 5);

    if (related.length) {
      html += '<div class="inspector__section"><span class="eyebrow">Most related papers</span>';
      related.forEach(function (score) {
        var other = score.doc_a === doc.doc_id ? score.doc_b : score.doc_a;
        html += '<div style="margin-top:9px">' +
          '<div style="font-size:11.5px;margin-bottom:3px">' + esc(titleFor(other)) + "</div>" +
          meterHtml(score.composite_score) + "</div>";
      });
      html += "</div>";
    }
    setInspector(html);
  }

  function meterHtml(value) {
    var pct = Math.round(Math.max(0, Math.min(1, value || 0)) * 100);
    return '<div class="meter"><span class="meter__track">' +
      '<span class="meter__fill" style="width:' + pct + '%"></span></span>' +
      '<span class="meter__value">' + fmt(value, 2) + "</span></div>";
  }

  // ------------------------------------------------------------------
  // Relationships (sequential encoding: one hue, light to dark)
  // ------------------------------------------------------------------

  function rampColor(value) {
    var steps = ["--seq-100", "--seq-200", "--seq-300", "--seq-400", "--seq-500", "--seq-600", "--seq-700"];
    var index = Math.min(steps.length - 1, Math.max(0, Math.round((value || 0) * (steps.length - 1))));
    return cssVar(steps[index]);
  }

  function renderRelationships() {
    var area = $("relationships-area");
    if (!state.scores.length) {
      area.innerHTML = emptyState(ICON_SEARCH, "No relationship scores yet",
        "Run the analysis to score every pair of papers across objective, methodology, dataset, results and citation similarity.");
      return;
    }

    var docIds = state.documents.map(function (d) { return d.doc_id; });
    if (!docIds.length) {
      docIds = Array.from(new Set(state.scores.flatMap(function (s) { return [s.doc_a, s.doc_b]; })));
    }

    var lookup = {};
    state.scores.forEach(function (s) {
      lookup[s.doc_a + " " + s.doc_b] = s;
      lookup[s.doc_b + " " + s.doc_a] = s;
    });

    // ---- Matrix ----
    var html = '<div class="card"><div class="card__head">' +
      '<div><span class="eyebrow">Pairwise composite score</span></div>' +
      '<span class="hint">Darker means more strongly related</span></div>' +
      '<div class="card__body"><div class="matrix-wrap"><table class="matrix">' +
      "<thead><tr><th></th>";

    docIds.forEach(function (id) {
      html += "<th><span>" + esc(titleFor(id)) + "</span></th>";
    });
    html += "</tr></thead><tbody>";

    docIds.forEach(function (rowId) {
      html += "<tr><th>" + esc(titleFor(rowId)) + "</th>";
      docIds.forEach(function (colId) {
        if (rowId === colId) {
          html += '<td class="is-diagonal">—</td>';
          return;
        }
        var score = lookup[rowId + " " + colId];
        var value = score ? score.composite_score : 0;
        // Label colour flips on the dark half of the ramp so the number stays
        // legible against its own cell.
        var textColor = value > 0.55 ? "#ffffff" : cssVar("--ink-primary");
        html += '<td style="background:' + rampColor(value) + ";color:" + textColor +
          '" data-pair="' + esc(rowId) + "|" + esc(colId) + '" title="' +
          esc(titleFor(rowId)) + " ↔ " + esc(titleFor(colId)) + ": " + fmt(value, 3) + '">' +
          (value ? fmt(value, 2).replace("0.", ".") : "") + "</td>";
      });
      html += "</tr>";
    });

    html += "</tbody></table></div>" +
      '<div class="scale"><span>0.0</span><span class="scale__ramp">' +
      ["--seq-100", "--seq-200", "--seq-300", "--seq-400", "--seq-500", "--seq-600", "--seq-700"]
        .map(function (step) { return '<span style="background:' + cssVar(step) + '"></span>'; }).join("") +
      "</span><span>1.0</span></div></div></div>";

    // ---- Ranked breakdown ----
    html += '<div class="card"><div class="card__head"><span class="eyebrow">Strongest pairs, by dimension</span>' +
      '<span class="hint">' + state.scores.length + " pairs scored</span></div>";

    state.scores.slice(0, 12).forEach(function (score) {
      html += '<div style="padding:13px 15px;border-bottom:1px solid var(--rule-hairline)">' +
        '<div style="display:flex;justify-content:space-between;gap:12px;align-items:baseline;flex-wrap:wrap">' +
        '<div style="font-family:var(--font-display);font-size:13.5px;min-width:0">' +
        esc(titleFor(score.doc_a)) + ' <span style="color:var(--ink-muted)">↔</span> ' +
        esc(titleFor(score.doc_b)) + "</div>" +
        '<div style="width:132px;flex:none">' + meterHtml(score.composite_score) + "</div></div>" +
        '<div class="components">';

      Object.keys(WEIGHT_LABELS).forEach(function (key) {
        var value = score.components[key] || 0;
        html += '<span class="components__name">' + WEIGHT_LABELS[key] + "</span>" +
          '<span class="meter__track"><span class="meter__fill" style="width:' +
          Math.round(value * 100) + "%;background:" + rampColor(value) + '"></span></span>' +
          '<span class="components__weight">' + fmt(value, 2) + "</span>";
      });

      html += "</div></div>";
    });

    html += "</div>";
    area.innerHTML = html;

    area.querySelectorAll("td[data-pair]").forEach(function (cell) {
      cell.addEventListener("click", function () {
        var ids = cell.getAttribute("data-pair").split("|");
        var score = lookup[ids[0] + " " + ids[1]];
        if (score) inspectScore(score);
      });
    });
  }

  function inspectScore(score) {
    var rows = Object.keys(WEIGHT_LABELS).map(function (key) {
      return [WEIGHT_LABELS[key], meterHtml(score.components[key] || 0)];
    });
    setInspector(
      '<div class="inspector__section"><span class="eyebrow">Relationship</span>' +
      '<h3 style="font-size:13.5px;margin-top:5px">' + esc(titleFor(score.doc_a)) +
      '</h3><div style="color:var(--ink-muted);font-size:11px;margin:3px 0">↔</div>' +
      '<h3 style="font-size:13.5px">' + esc(titleFor(score.doc_b)) + "</h3>" +
      '<div style="margin-top:11px">' + meterHtml(score.composite_score) + "</div></div>" +
      '<div class="inspector__section"><span class="eyebrow">Dimensions</span>' + kv(rows) + "</div>"
    );
  }

  // ------------------------------------------------------------------
  // Contradictions
  // ------------------------------------------------------------------

  function markNumbers(text) {
    // Highlight reported values - the numbers are what the two claims actually
    // disagree about, so they should be findable at a glance.
    return esc(text).replace(/(\d{1,3}(?:\.\d+)?\s?%|\b0\.\d{2,4}\b)/g,
      '<span class="claim__value">$1</span>');
  }

  function renderContradictions() {
    var area = $("contradictions-area");
    var items = state.contradictions;
    if (state.confirmedOnly) items = items.filter(function (c) { return c.confirmed; });

    if (!items.length) {
      var hasRun = state.status && state.status.has_results;
      var title, body;

      if (state.contradictions.length) {
        title = "No confirmed contradictions";
        body = "There are " + state.contradictions.length +
          " unconfirmed candidates. Clear the filter to review them.";
      } else if (hasRun) {
        // Zero is a real result, not a failure. Say so, or the panel reads as
        // broken when the corpus genuinely contains no numeric disagreement.
        title = "No contradictions in this corpus";
        body = "Every candidate was rejected. A pair is only reported when both " +
          "papers state a measured result for the same metric on the same dataset, " +
          "under the same evaluation regime, and the reported values differ " +
          "materially. Papers that study different methods rarely meet that bar.";
      } else {
        title = "No contradictions detected";
        body = "Run the analysis. Claims are compared across papers that share a " +
          "dataset and a metric; only genuine disagreements are reported.";
      }

      area.innerHTML = emptyState(
        '<path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0zM12 9v4M12 17h.01"/>',
        title, body
      );
      return;
    }

    area.innerHTML = items.map(function (item, index) {
      var confirmed = item.confirmed;
      var chipIcon = confirmed
        ? '<path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0zM12 9v4M12 17h.01"/>'
        : '<circle cx="12" cy="12" r="9"/><path d="M12 8v4M12 16h.01"/>';

      return '<div class="card" data-contradiction="' + index + '">' +
        '<div class="card__head">' +
        '<span class="eyebrow">Contradiction ' + (index + 1) + "</span>" +
        '<div style="display:flex;gap:7px;align-items:center;flex-wrap:wrap">' +
        '<span class="chip chip--' + (confirmed ? "confirmed" : "unconfirmed") + '">' +
        '<svg class="chip__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
        'stroke-linecap="round" stroke-linejoin="round">' + chipIcon + "</svg>" +
        (confirmed ? "Confirmed" : "Unconfirmed") + "</span>" +
        '<span class="chip chip--neutral">confidence ' + fmt(item.confidence, 2) + "</span>" +
        "</div></div>" +

        '<div class="spread">' +
        '<div class="claim claim--a">' +
        '<div class="claim__source">' +
        '<svg class="icon icon--sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
        'stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/></svg>' +
        esc(titleFor(item.doc_a)) + "</div>" +
        '<div class="claim__text">' + markNumbers(item.claim_a) + "</div>" +
        (item.evidence[0] ? evidenceBlock(item.evidence[0]) : "") +
        "</div>" +

        '<div class="spread__divider"><span class="spread__badge">VERSUS</span></div>' +

        '<div class="claim claim--b">' +
        '<div class="claim__source">' +
        '<svg class="icon icon--sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
        'stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/></svg>' +
        esc(titleFor(item.doc_b)) + "</div>" +
        '<div class="claim__text">' + markNumbers(item.claim_b) + "</div>" +
        (item.evidence[1] ? evidenceBlock(item.evidence[1], "b") : "") +
        "</div></div>" +

        '<div class="signals">' +
        signal("Stance", item.nli_label) +
        signal("Stance conf.", fmt(item.nli_confidence, 2)) +
        signal("Shared dataset", item.dataset_compatible ? "yes" : "no") +
        signal("Comparable metric", item.metrics_comparable ? "yes" : "no") +
        signal("Methodology sim.", fmt(item.methodology_similarity, 2)) +
        "</div>" +

        (item.explanation
          ? '<div style="padding:11px 16px;border-top:1px solid var(--rule-hairline);font-size:12.5px;color:var(--ink-secondary)">' +
            esc(item.explanation) + "</div>"
          : "") +
        "</div>";
    }).join("");

    area.querySelectorAll("[data-contradiction]").forEach(function (card) {
      card.addEventListener("click", function () {
        inspectContradiction(items[Number(card.getAttribute("data-contradiction"))]);
      });
    });
  }

  function signal(label, value) {
    return '<div class="signal"><span class="signal__label">' + esc(label) +
      '</span><span class="signal__value">' + esc(value) + "</span></div>";
  }

  function inspectContradiction(item) {
    setInspector(
      '<div class="inspector__section"><span class="eyebrow">Contradiction</span>' +
      '<h3 style="font-size:14px;margin-top:5px">' +
      (item.confirmed ? "Confirmed" : "Unconfirmed") + " disagreement</h3>" +
      kv([
        ["Paper A", esc(titleFor(item.doc_a))],
        ["Paper B", esc(titleFor(item.doc_b))],
        ["Stance", esc(item.nli_label)],
        ["Confidence", fmt(item.confidence, 3)],
        ["Method sim.", fmt(item.methodology_similarity, 3)],
      ]) + "</div>" +
      '<div class="inspector__section"><span class="eyebrow">Evidence trail</span>' +
      item.evidence.map(function (e, i) { return evidenceBlock(e, i === 1 ? "b" : null); }).join("") +
      "</div>"
    );
  }

  // ------------------------------------------------------------------
  // Research gaps
  // ------------------------------------------------------------------

  function renderGaps() {
    var area = $("gaps-area");
    if (!state.gaps.length) {
      area.innerHTML = emptyState(
        '<path d="M9 18h6M10 22h4M12 2a7 7 0 0 0-4 12.7V17h8v-2.3A7 7 0 0 0 12 2z"/>',
        "No research gaps yet",
        "Run the analysis. Gaps come from three sources: statements the authors make directly, concept pairings absent from the whole corpus, and papers that share a concept but little else."
      );
      return;
    }

    area.innerHTML = state.gaps.map(function (gap, index) {
      return '<div class="card" data-gap="' + index + '">' +
        '<div class="card__head">' +
        '<span class="eyebrow">Gap ' + (index + 1) + "</span>" +
        '<div style="display:flex;align-items:center;gap:9px;min-width:148px">' +
        '<span class="eyebrow">Novelty</span>' + meterHtml(gap.novelty_score) + "</div></div>" +
        '<div class="card__body">' +
        '<p style="font-family:var(--font-display);font-size:14px;line-height:1.55;margin:0">' +
        esc(gap.description) + "</p>" +
        (gap.bridge_entities && gap.bridge_entities.length
          ? '<div style="margin-top:10px;display:flex;gap:5px;flex-wrap:wrap">' +
            gap.bridge_entities.map(function (b) {
              return '<span class="chip chip--bridge">' + esc(b) + "</span>";
            }).join("") + "</div>"
          : "") +
        (gap.supporting_docs && gap.supporting_docs.length
          ? '<div style="margin-top:9px;font-size:11px;color:var(--ink-muted);font-family:var(--font-mono)">' +
            gap.supporting_docs.length + " supporting paper" +
            (gap.supporting_docs.length === 1 ? "" : "s") + "</div>"
          : "") +
        (gap.evidence && gap.evidence.length ? evidenceBlock(gap.evidence[0]) : "") +
        "</div></div>";
    }).join("");

    area.querySelectorAll("[data-gap]").forEach(function (card) {
      card.addEventListener("click", function () {
        inspectGap(state.gaps[Number(card.getAttribute("data-gap"))]);
      });
    });
  }

  function inspectGap(gap) {
    setInspector(
      '<div class="inspector__section"><span class="eyebrow">Research gap</span>' +
      '<p style="font-family:var(--font-display);font-size:13.5px;line-height:1.5;margin:6px 0 10px">' +
      esc(gap.description) + "</p>" + meterHtml(gap.novelty_score) + "</div>" +
      (gap.explanation
        ? '<div class="inspector__section"><span class="eyebrow">Why</span>' +
          '<p style="font-size:12px;margin:6px 0 0;color:var(--ink-secondary)">' +
          esc(gap.explanation) + "</p></div>"
        : "") +
      '<div class="inspector__section"><span class="eyebrow">Supporting papers</span>' +
      '<ul style="margin:7px 0 0;padding-left:16px;font-size:12px">' +
      (gap.supporting_docs || []).map(function (id) {
        return "<li>" + esc(titleFor(id)) + "</li>";
      }).join("") + "</ul></div>" +
      (gap.evidence && gap.evidence.length
        ? '<div class="inspector__section"><span class="eyebrow">Evidence trail</span>' +
          gap.evidence.map(function (e) { return evidenceBlock(e); }).join("") + "</div>"
        : "")
    );
  }

  // ------------------------------------------------------------------
  // Documents table
  // ------------------------------------------------------------------

  function renderDocuments() {
    var area = $("corpus-area");
    if (!state.documents.length) {
      area.innerHTML = emptyState(
        '<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>',
        "No documents analysed",
        "Upload PDFs and run the analysis to see how each paper was segmented and classified."
      );
      return;
    }

    area.innerHTML = '<div class="card"><table class="table"><thead><tr>' +
      "<th>Paper</th><th>Category</th><th>Confidence</th><th>Pages</th>" +
      "<th>Sections</th><th>Refs</th></tr></thead><tbody>" +
      state.documents.map(function (doc) {
        return '<tr data-doc="' + esc(doc.doc_id) + '" style="cursor:pointer">' +
          "<td><div style=\"font-weight:500\">" + esc(doc.title) + "</div>" +
          '<div class="mono" style="font-size:10.5px;color:var(--ink-muted)">' + esc(doc.doc_id) + "</div></td>" +
          '<td><span class="chip chip--neutral">' + esc(doc.category) + "</span>" +
          (doc.needs_review
            ? '<div style="font-size:10px;color:var(--status-warning);margin-top:3px">flagged for review</div>'
            : "") + "</td>" +
          '<td class="mono">' + fmt(doc.category_confidence, 2) + "</td>" +
          '<td class="mono">' + esc(doc.total_pages) + "</td>" +
          '<td style="font-size:11px;color:var(--ink-secondary)">' + esc(doc.segments.join(", ")) + "</td>" +
          '<td class="mono">' + esc(doc.reference_count) + "</td></tr>";
      }).join("") + "</tbody></table></div>";

    area.querySelectorAll("tr[data-doc]").forEach(function (row) {
      row.addEventListener("click", function () {
        var doc = state.documents.find(function (d) { return d.doc_id === row.getAttribute("data-doc"); });
        if (doc) inspectDocument(doc);
      });
    });
  }

  // ------------------------------------------------------------------
  // Weights modal
  // ------------------------------------------------------------------

  function openWeights() {
    state.draftWeights = Object.assign({}, state.weights);
    renderWeightSliders();
    $("modal-weights").setAttribute("data-open", "true");
  }

  function closeWeights() {
    $("modal-weights").setAttribute("data-open", "false");
  }

  function renderWeightSliders() {
    var host = $("weights-sliders");
    host.innerHTML = Object.keys(WEIGHT_LABELS).map(function (key) {
      return '<div class="slider-row"><div class="slider-row__head">' +
        '<span class="slider-row__name">' + WEIGHT_LABELS[key] + "</span>" +
        '<span class="slider-row__value" id="wv-' + key + '">' +
        fmt(state.draftWeights[key], 2) + "</span></div>" +
        '<input type="range" min="0" max="1" step="0.05" value="' +
        state.draftWeights[key] + '" data-weight="' + key + '" /></div>';
    }).join("");

    host.querySelectorAll("input[data-weight]").forEach(function (input) {
      input.addEventListener("input", function () {
        var key = input.getAttribute("data-weight");
        state.draftWeights[key] = parseFloat(input.value);
        $("wv-" + key).textContent = fmt(state.draftWeights[key], 2);
        updateWeightSum();
      });
    });
    updateWeightSum();
  }

  function weightSum() {
    return Object.keys(WEIGHT_LABELS).reduce(function (total, key) {
      return total + (state.draftWeights[key] || 0);
    }, 0);
  }

  function updateWeightSum() {
    var sum = weightSum();
    var valid = Math.abs(sum - 1) < 1e-4;
    var readout = $("weights-sum");
    readout.textContent = "Sum " + fmt(sum, 2) + (valid ? "" : " — must be 1.00");
    readout.setAttribute("data-valid", valid ? "true" : "false");
    $("btn-save-weights").disabled = !valid;
  }

  // ------------------------------------------------------------------
  // Actions
  // ------------------------------------------------------------------

  async function runPipeline() {
    if (state.running) return;
    setRunning(true);
    $("status-fill").style.width = "2%";
    $("status-stage").textContent = "starting";
    $("status-message").textContent = "Submitting run…";

    try {
      await api("/api/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          extraction_backend: $("sel-backend").value,
          use_nli: $("chk-nli").checked,
          skip_explanation: false,
        }),
      });
    } catch (err) {
      setRunning(false);
      $("status-stage").textContent = "idle";
      $("status-message").textContent = "Ready.";
      $("status-fill").style.width = "0";
      toast(err.message, "error");
    }
  }

  async function uploadFiles(files) {
    var pdfs = Array.from(files).filter(function (f) { return /\.pdf$/i.test(f.name); });
    if (!pdfs.length) {
      toast("Only PDF files can be added to the corpus.", "error");
      return;
    }

    var uploaded = 0;
    for (var i = 0; i < pdfs.length; i++) {
      var form = new FormData();
      form.append("file", pdfs[i]);
      try {
        await api("/api/upload", { method: "POST", body: form });
        uploaded++;
      } catch (err) {
        toast(pdfs[i].name + ": " + err.message, "error");
      }
    }
    if (uploaded) {
      toast("Added " + uploaded + " paper" + (uploaded === 1 ? "" : "s") + " to the corpus.", "success");
      refreshStatus();
    }
  }

  // ------------------------------------------------------------------
  // Wiring
  // ------------------------------------------------------------------

  function initTabs() {
    var tabs = Array.from(document.querySelectorAll(".tab"));
    tabs.forEach(function (tab) {
      tab.addEventListener("click", function () {
        tabs.forEach(function (other) {
          var active = other === tab;
          other.setAttribute("aria-selected", active ? "true" : "false");
          $(other.getAttribute("data-panel")).setAttribute("data-active", active ? "true" : "false");
        });
        // Cytoscape cannot size itself while its container is display:none.
        if (tab.getAttribute("data-panel") === "panel-graph" && state.cy) {
          setTimeout(function () { state.cy.resize(); state.cy.fit(undefined, 36); }, 30);
        }
      });
    });
  }

  function syncThresholdVisibility() {
    var wrap = $("threshold-wrap");
    if (wrap) wrap.style.display = $("graph-view").value === "network" ? "" : "none";
  }

  function init() {
    initTheme();
    syncThresholdVisibility();
    initTabs();
    clearInspector();

    $("btn-theme").addEventListener("click", function () {
      var dark = document.documentElement.getAttribute("data-theme") === "dark" ||
        (!document.documentElement.hasAttribute("data-theme") &&
          window.matchMedia("(prefers-color-scheme: dark)").matches);
      applyTheme(dark ? "light" : "dark");
    });

    $("btn-run").addEventListener("click", runPipeline);

    function openBackendModal() {
      $("input-backend").value = API_BASE || "";
      $("modal-backend").setAttribute("data-open", "true");
      setTimeout(function () { $("input-backend").focus(); }, 60);
    }

    function closeBackendModal() {
      $("modal-backend").setAttribute("data-open", "false");
    }

    function applyBackend(url) {
      var target = new URL(window.location.href);
      if (url) {
        target.searchParams.set("api", url.replace(/\/$/, ""));
      } else {
        target.searchParams.delete("api");
      }
      window.location.href = target.toString();
    }

    /**
     * Keep the button's label in sync with the dropdown so "Load" never reads
     * as a no-op or an ambiguous action - the confusion this caused before was
     * clicking Load while "Sample" was still selected, expecting the arXiv set.
     */
    function syncCorpusButtonLabel() {
      var which = $("sel-corpus").value;
      $("btn-load-corpus").textContent = which === "arxiv" ? "Load 30" : "Load 6";
    }
    $("sel-corpus").addEventListener("change", syncCorpusButtonLabel);
    syncCorpusButtonLabel();

    $("btn-load-corpus").addEventListener("click", async function () {
      if (state.demoMode) {
        toast("Connect a backend before loading a corpus.", "error");
        return;
      }
      var which = $("sel-corpus").value;
      var button = $("btn-load-corpus");
      button.disabled = true;
      try {
        var path = which === "arxiv" ? "/api/corpus/fetch-arxiv" : "/api/corpus/seed";
        var res = await api(path, { method: "POST" });
        toast(res.message, "success");
        // The arXiv fetch runs in the background and reports over the socket;
        // the sample corpus is replaced synchronously and is ready now.
        if (which !== "arxiv") refreshStatus().then(renderEverything);
      } catch (err) {
        toast(err.message, "error");
      } finally {
        button.disabled = false;
      }
    });

    $("btn-connect-api").addEventListener("click", openBackendModal);
    $("btn-close-backend").addEventListener("click", closeBackendModal);
    $("btn-cancel-backend").addEventListener("click", closeBackendModal);
    $("modal-backend").addEventListener("click", function (evt) {
      if (evt.target === $("modal-backend")) closeBackendModal();
    });
    $("btn-backend-same-origin").addEventListener("click", function () {
      applyBackend("");
    });
    $("btn-save-backend").addEventListener("click", function () {
      var entered = $("input-backend").value.trim();
      if (!entered) {
        toast("Enter a backend URL, or choose “Use this origin”.", "error");
        return;
      }
      if (!/^https?:\/\//i.test(entered)) {
        toast("The URL needs to start with http:// or https://", "error");
        return;
      }
      applyBackend(entered);
    });
    $("input-backend").addEventListener("keydown", function (evt) {
      if (evt.key === "Enter") $("btn-save-backend").click();
    });
    $("btn-export").addEventListener("click", function () {
      if (state.demoMode) {
        toast("Reports are generated by the backend. Connect one to download.", "error");
        return;
      }
      window.open(API_BASE + "/api/report?fmt=pdf", "_blank");
    });

    $("btn-weights").addEventListener("click", openWeights);
    $("btn-close-weights").addEventListener("click", closeWeights);
    $("modal-weights").addEventListener("click", function (evt) {
      if (evt.target === $("modal-weights")) closeWeights();
    });
    $("btn-reset-weights").addEventListener("click", function () {
      state.draftWeights = { objective: 0.25, methodology: 0.25, dataset: 0.2, results_metrics: 0.2, citation: 0.1 };
      renderWeightSliders();
    });
    $("btn-save-weights").addEventListener("click", async function () {
      try {
        var response = await api("/api/config/weights", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(state.draftWeights),
        });
        state.weights = response.weights;
        closeWeights();
        toast(response.message, "success");
      } catch (err) {
        toast(err.message, "error");
      }
    });

    document.addEventListener("keydown", function (evt) {
      if (evt.key !== "Escape") return;
      closeWeights();
      $("modal-backend").setAttribute("data-open", "false");
    });

    var dropzone = $("dropzone");
    var fileInput = $("file-input");
    dropzone.addEventListener("click", function () { fileInput.click(); });
    dropzone.addEventListener("keydown", function (evt) {
      if (evt.key === "Enter" || evt.key === " ") { evt.preventDefault(); fileInput.click(); }
    });
    fileInput.addEventListener("change", function () {
      if (fileInput.files.length) uploadFiles(fileInput.files);
      fileInput.value = "";
    });
    ["dragenter", "dragover"].forEach(function (type) {
      dropzone.addEventListener(type, function (evt) {
        evt.preventDefault();
        dropzone.classList.add("is-over");
      });
    });
    ["dragleave", "drop"].forEach(function (type) {
      dropzone.addEventListener(type, function (evt) {
        evt.preventDefault();
        dropzone.classList.remove("is-over");
      });
    });
    dropzone.addEventListener("drop", function (evt) {
      if (evt.dataTransfer && evt.dataTransfer.files.length) uploadFiles(evt.dataTransfer.files);
    });

    $("graph-search").addEventListener("input", applyGraphSearch);

    $("graph-view").addEventListener("change", function () {
      syncThresholdVisibility();
      renderGraph();
    });

    $("graph-threshold").addEventListener("input", function () {
      $("threshold-value").textContent = parseFloat(this.value).toFixed(2);
    });
    $("graph-threshold").addEventListener("change", renderGraph);
    $("btn-fit").addEventListener("click", function () {
      if (state.cy) state.cy.fit(undefined, 36);
    });
    $("btn-relayout").addEventListener("click", function () {
      if (state.cy) runLayout(state.cy, $("graph-view").value);
    });

    $("chk-confirmed-only").addEventListener("change", function (evt) {
      state.confirmedOnly = evt.target.checked;
      renderContradictions();
    });

    $("btn-clear-inspector").addEventListener("click", function () {
      clearInspector();
      if (state.cy) state.cy.elements().removeClass("dimmed highlight");
    });

    refreshAll().then(function () {
      if (!state.demoMode) connectSocket();
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
