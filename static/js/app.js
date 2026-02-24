/**
 * Lexical Analyzer  –  app.js
 * Tab-based layout: Tokens / Errors / Stats tabs in header
 */

/* ── DOM refs ──────────────────────────────────────────────────────── */
const codeInput     = document.getElementById("codeInput");
const lineNumbers   = document.getElementById("lineNumbers");
const charCount     = document.getElementById("charCount");
const btnAnalyze    = document.getElementById("btnAnalyze");
const btnClear      = document.getElementById("btnClear");
const btnLoadSample = document.getElementById("btnLoadSample");
const btnCopyTokens = document.getElementById("btnCopyTokens");
const langBtns      = document.querySelectorAll(".lang-btn");


const tabPanels     = document.getElementById("tabPanels");
const tabButtons    = document.getElementById("tabButtons");

const outputMeta    = document.getElementById("outputMeta");
const metaLang      = document.getElementById("metaLang");

const tokenBody     = document.getElementById("tokenBody");
const typeFilter    = document.getElementById("typeFilter");
const tokenSearch   = document.getElementById("tokenSearch");

const errorList     = document.getElementById("errorList");

const statsGrid     = document.getElementById("statsGrid");
const statsChart    = document.getElementById("statsChart");

/* ── State ──────────────────────────────────────────────────────────── */
let selectedLang  = "c";      // default: C
let allTokens     = [];
let errorCount    = 0;        // total error count
let chartInstance = null;
let activeTab     = "tokens"; // default tab

/* ── Language selector ──────────────────────────────────────────────── */
langBtns.forEach(btn => {
  btn.addEventListener("click", () => {
    langBtns.forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    selectedLang = btn.dataset.lang;
  });
});

/* ── Tab switching ──────────────────────────────────────────────────── */
function switchTab(tabName) {
  activeTab = tabName;
  
  // Update button states
  document.querySelectorAll(".tab-btn").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.tab === tabName);
  });
  
  // Update panel visibility
  document.querySelectorAll(".tab-panel").forEach(panel => {
    panel.classList.toggle("active", panel.id === `panel${tabName.charAt(0).toUpperCase() + tabName.slice(1)}`);
  });
  
  // Render chart when stats tab is opened
  if (tabName === "stats" && allTokens.length) {
    renderChart(allTokens, errorCount);
  }
}

// Tab button click handlers
if (tabButtons) {
  tabButtons.addEventListener("click", e => {
    const btn = e.target.closest(".tab-btn");
    if (btn) switchTab(btn.dataset.tab);
  });
}

/* ── Line numbers ────────────────────────────────────────────────────── */
function updateLineNumbers() {
  const lines = codeInput.value.split("\n").length;
  lineNumbers.textContent = Array.from({ length: lines }, (_, i) => i + 1).join("\n");
  charCount.textContent   = `${codeInput.value.length} character${codeInput.value.length !== 1 ? "s" : ""}`;
}

codeInput.addEventListener("input",  updateLineNumbers);
codeInput.addEventListener("scroll", () => {
  lineNumbers.scrollTop = codeInput.scrollTop;
});

// Tab key inserts spaces instead of focus-cycling
codeInput.addEventListener("keydown", e => {
  if (e.key === "Tab") {
    e.preventDefault();
    const start = codeInput.selectionStart;
    const end   = codeInput.selectionEnd;
    codeInput.value = codeInput.value.slice(0, start) + "    " + codeInput.value.slice(end);
    codeInput.selectionStart = codeInput.selectionEnd = start + 4;
    updateLineNumbers();
  }
});

/* ── Clear ───────────────────────────────────────────────────────────── */
btnClear.addEventListener("click", () => {
  codeInput.value = "";
  updateLineNumbers();
  resetOutput();
});

/* ── Sample loader ───────────────────────────────────────────────────── */
btnLoadSample.addEventListener("click", () => {
  const samples = window.SAMPLES || {};
  codeInput.value = (samples[selectedLang] || "").trimStart();
  updateLineNumbers();
  resetOutput();
});

/* ── Copy tokens ──────────────────────────────────────────────────────── */
btnCopyTokens.addEventListener("click", async () => {
  if (!allTokens.length) return;
  
  // Create HTML table for rich paste (Word, Excel, Google Sheets)
  let html = '<table border="1" cellpadding="5" cellspacing="0">';
  html += '<thead><tr><th>#</th><th>Type</th><th>Value</th><th>Line</th><th>Col</th></tr></thead>';
  html += '<tbody>';
  
  // Also create plain text TSV version as fallback
  let tsv = "#\tType\tValue\tLine\tCol\n";
  
  allTokens.forEach((tok, idx) => {
    const num = idx + 1;
    const type = tok.type;
    let value = tok.value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    const plainValue = tok.value.replace(/\n/g, '\\n').replace(/\t/g, '\\t');
    const line = tok.line;
    const col = tok.column;
    
    html += `<tr><td>${num}</td><td>${type}</td><td>${value}</td><td>${line}</td><td>${col}</td></tr>`;
    tsv += `${num}\t${type}\t${plainValue}\t${line}\t${col}\n`;
  });
  
  html += '</tbody></table>';
  
  try {
    // Copy both HTML and plain text formats
    const clipboardItem = new ClipboardItem({
      'text/html': new Blob([html], { type: 'text/html' }),
      'text/plain': new Blob([tsv], { type: 'text/plain' })
    });
    
    await navigator.clipboard.write([clipboardItem]);
    
    // Visual feedback
    const original = btnCopyTokens.innerHTML;
    btnCopyTokens.innerHTML = '✅ Copied!';
    btnCopyTokens.disabled = true;
    setTimeout(() => {
      btnCopyTokens.innerHTML = original;
      btnCopyTokens.disabled = false;
    }, 2000);
  } catch (err) {
    // Fallback to plain TSV if ClipboardItem is not supported
    try {
      await navigator.clipboard.writeText(tsv);
      const original = btnCopyTokens.innerHTML;
      btnCopyTokens.innerHTML = '✅ Copied!';
      btnCopyTokens.disabled = true;
      setTimeout(() => {
        btnCopyTokens.innerHTML = original;
        btnCopyTokens.disabled = false;
      }, 2000);
    } catch (fallbackErr) {
      console.error('Failed to copy:', fallbackErr);
      alert('Failed to copy to clipboard');
    }
  }
});



/* ── Token filter / search ───────────────────────────────────────────── */
function filterTokens() {
  const query = tokenSearch.value.toLowerCase().trim();
  const type  = typeFilter.value;
  const rows  = tokenBody.querySelectorAll("tr");
  rows.forEach(row => {
    const rowType  = row.dataset.type  || "";
    const rowValue = row.dataset.value || "";
    const matchType  = !type  || rowType  === type;
    const matchQuery = !query || rowType.toLowerCase().includes(query) || rowValue.toLowerCase().includes(query);
    row.hidden = !(matchType && matchQuery);
  });
}
tokenSearch.addEventListener("input",  filterTokens);
typeFilter.addEventListener( "change", filterTokens);

/* ── Analyze ─────────────────────────────────────────────────────────── */
btnAnalyze.addEventListener("click", runAnalysis);
codeInput.addEventListener("keydown", e => {
  if ((e.ctrlKey || e.metaKey) && e.key === "Enter") runAnalysis();
});

async function runAnalysis() {
  const code = codeInput.value;
  if (!code.trim()) { shakeBtn(btnAnalyze); return; }

  showLoading(true);
  resetOutput(true);

  try {
    const resp = await fetch("/api/analyze", {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ code, language: selectedLang }),
    });
    const data = await resp.json();

    if (!resp.ok) {
      showApiError(data.error || `HTTP ${resp.status}`);
      return;
    }
    renderResults(data);
  } catch (err) {
    showApiError("Network error – make sure the server is running.");
    console.error(err);
  } finally {
    showLoading(false);
  }
}

/* ── Rendering ───────────────────────────────────────────────────────── */
function renderResults(data) {
  const { language, tokens, errors, stats } = data;

  const labelMap = { c: "C", cpp: "C++", python: "Python" };
  metaLang.textContent = `Language: ${labelMap[language] || language}`;
  outputMeta.hidden = false;

  allTokens = tokens;
  errorCount = errors.length;  // Store error count globally


  tabPanels.hidden   = false;
  tabButtons.hidden  = false;

  // Update tab counts
  document.getElementById("tabCountTokens").textContent = tokens.length;
  document.getElementById("tabCountErrors").textContent = errors.length;

  renderTokenTable(tokens);
  renderErrors(errors);
  renderStats(stats);
  renderChart(tokens, errors.length);  // Pass actual error count
  
  // Switch to tokens tab by default
  switchTab("tokens");
}

/* Token table ──────────────────────────────────────────────────────── */
function renderTokenTable(tokens) {
  // Populate type filter
  const types = [...new Set(tokens.map(t => t.type))].sort();
  typeFilter.innerHTML = '<option value="">All types</option>';
  types.forEach(t => {
    const opt = document.createElement("option");
    opt.value = t; opt.textContent = t;
    typeFilter.appendChild(opt);
  });

  // Build rows
  tokenBody.innerHTML = "";
  const frag = document.createDocumentFragment();
  tokens.forEach((tok, idx) => {
    const tr = document.createElement("tr");
    tr.dataset.type  = tok.type;
    tr.dataset.value = tok.value;
    if (tok.type === "ERROR") tr.classList.add("token-row-error");

    tr.innerHTML = `
      <td class="td-num">${idx + 1}</td>
      <td><span class="token-type type-${tok.type}">${escHtml(tok.type)}</span></td>
      <td class="token-value" title="${escHtml(tok.value)}">${escHtml(displayValue(tok.value))}</td>
      <td class="td-line">${tok.line}</td>
      <td class="td-col">${tok.column}</td>
    `;
    frag.appendChild(tr);
  });
  tokenBody.appendChild(frag);
}

/* Errors ────────────────────────────────────────────────────────────── */
function renderErrors(errors) {
  if (!errors.length) {
    errorList.innerHTML = '<p class="no-errors">✅ No errors found.</p>';
    return;
  }
  const frag = document.createDocumentFragment();
  errors.forEach(err => {
    const card = document.createElement("div");
    card.className = "error-card";
    card.innerHTML = `
      <div class="error-card-header">
        <span class="error-label">⚠ Error</span>
        <span class="error-location">Line ${err.line}, Col ${err.column}</span>
      </div>
      <div class="error-msg">${escHtml(err.message || "Unknown error")}</div>
      ${err.value ? `<div class="error-value">${escHtml(displayValue(err.value))}</div>` : ""}
    `;
    frag.appendChild(card);
  });
  errorList.innerHTML = "";
  errorList.appendChild(frag);
}

/* Stats ─────────────────────────────────────────────────────────────── */
function renderStats(stats) {
  const byType = stats.by_type || {};
  statsGrid.innerHTML = "";
  const summary = [
    { label: "Total Tokens", count: stats.total,       accent: true },
    { label: "Errors",       count: stats.error_count, danger: stats.error_count > 0 },
    ...Object.entries(byType).sort((a,b)=>b[1]-a[1]).slice(0, 10).map(
      ([t, c]) => ({ label: t, count: c })
    ),
  ];
  summary.forEach(({ label, count, danger }) => {
    const card = document.createElement("div");
    card.className = "stat-card";
    const color = danger ? "var(--danger)" : "var(--accent)";
    card.innerHTML = `<div class="stat-count" style="color:${color}">${count}</div><div class="stat-label">${escHtml(label)}</div>`;
    statsGrid.appendChild(card);
  });
}

function renderChart(tokens, errorCount = 0) {
  const byType = {};
  tokens.forEach(t => { byType[t.type] = (byType[t.type] || 0) + 1; });
  
  // Replace ERROR token count with actual error count
  if (errorCount > 0) {
    byType.ERROR = errorCount;
  } else if (byType.ERROR) {
    // If no errorCount provided, use ERROR tokens count
    errorCount = byType.ERROR;
  }
  
  const labels = Object.keys(byType);
  const values = labels.map(k => byType[k]);
  if (!window.Chart) {
    const s = document.createElement("script");
    s.src = "https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js";
    s.onload = () => drawChart(labels, values);
    document.head.appendChild(s);
  } else {
    drawChart(labels, values);
  }
}

function drawChart(labels, values) {
  // Color mapping: ERROR always red, others get distinct colors
  const colorMap = {
    ERROR:       "#f85149",  // Red
    KEYWORD:     "#ff7b72",  // Coral red
    IDENTIFIER:  "#79c0ff",  // Light blue
    INTEGER:     "#a5d6ff",  // Sky blue
    FLOAT:       "#a5d6ff",  // Sky blue
    STRING:      "#a5d6ff",  // Sky blue
    F_STRING:    "#a5d6ff",  // Sky blue
    CHAR:        "#a5d6ff",  // Sky blue
    OPERATOR:    "#ffa657",  // Orange
    DELIMITER:   "#d2a8ff",  // Purple
    PREPROCESSOR:"#7ee787",  // Green
    BOOLEAN:     "#ff7b72",  // Coral red
    NONE:        "#ff7b72",  // Coral red
    INDENT:      "#8b949e",  // Gray
    DEDENT:      "#8b949e",  // Gray
  };
  
  const defaultPalette = [
    "#56d364","#3fb950","#58a6ff","#e3b341","#bc8cff",
    "#ffd700","#ff6b9d","#00d4aa","#9d7cd8","#ff9e64",
  ];
  
  const colors = labels.map((label, i) => {
    return colorMap[label] || defaultPalette[i % defaultPalette.length];
  });
  
  // Create labels with counts
  const labelsWithCounts = labels.map((label, i) => `${label} (${values[i]})`);
  
  if (chartInstance) chartInstance.destroy();
  chartInstance = new window.Chart(statsChart, {
    type: "doughnut",
    data: {
      labels: labelsWithCounts,
      datasets: [{
        data: values,
        backgroundColor: colors.map(c => c + "dd"),  // Add transparency
        borderColor:     colors,
        borderWidth: 2,
      }],
    },
    options: {
      responsive: true,
      plugins: {
        legend: {
          position: "right",
          labels: { 
            color: "#e6edf3", 
            font: { size: 11, family: "'Fira Code', monospace" }, 
            boxWidth: 16, 
            padding: 8,
            usePointStyle: true,
            pointStyle: 'circle',
          },
        },
        tooltip: {
          callbacks: {
            label: function(context) {
              const label = labels[context.dataIndex];
              const value = context.parsed;
              const total = context.dataset.data.reduce((a, b) => a + b, 0);
              const percentage = ((value / total) * 100).toFixed(1);
              return `${label}: ${value} (${percentage}%)`;
            }
          }
        }
      },
    },
  });
}

/* ── Helpers ─────────────────────────────────────────────────────────── */
function escHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function displayValue(v) {
  if (!v || v.length === 0) return "(empty)";
  if (v === "\n" || v === "\\n") return "↵";
  if (v.length > 60) return v.slice(0, 57) + "…";
  return v;
}

function resetOutput(keepLoader = false) {
  allTokens = [];
  errorCount = 0;
  tokenBody.innerHTML = "";
  errorList.innerHTML  = '<p class="no-errors">✅ No errors found.</p>';
  statsGrid.innerHTML  = "";
  outputMeta.hidden   = true;
  tabPanels.hidden    = true;
  tabButtons.hidden   = true;
  typeFilter.innerHTML = '<option value="">All types</option>';
  tokenSearch.value    = "";
  if (chartInstance) { chartInstance.destroy(); chartInstance = null; }
}

function showLoading(on) {
  tabPanels.hidden     = true;
  tabButtons.hidden    = true;
  btnAnalyze.disabled  = on;
  btnAnalyze.textContent = on ? "⏳ Analyzing…" : "▶ Analyze";
}

function showApiError(msg) {
  tabPanels.innerHTML = `<div style="padding:3rem;text-align:center;color:var(--danger)">
    <div style="font-size:3rem;margin-bottom:1rem">❌</div>
    <p>${escHtml(msg)}</p>
  </div>`;
  tabPanels.hidden = false;
}

function shakeBtn(btn) {
  btn.classList.add("shake");
  btn.addEventListener("animationend", () => btn.classList.remove("shake"), { once: true });
}

// Add shake animation dynamically
const shakeStyle = document.createElement("style");
shakeStyle.textContent = `
@keyframes shake {
  0%,100%{transform:translateX(0)}
  20%,60%{transform:translateX(-5px)}
  40%,80%{transform:translateX(5px)}
}
.shake{animation:shake .35s ease}`;
document.head.appendChild(shakeStyle);

/* ── Init ────────────────────────────────────────────────────────────── */
updateLineNumbers();
