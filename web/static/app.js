const symbolInput = document.getElementById("symbol-input");

const suggestionsEl = document.getElementById("suggestions");

const strategySelect = document.getElementById("strategy-select");

const strategyDesc = document.getElementById("strategy-desc");

const runBtn = document.getElementById("run-btn");
const optimizeBtn = document.getElementById("optimize-btn");
const optimizeResultsEl = document.getElementById("optimize-results");
const optimizeCloseBtn = document.getElementById("optimize-close");

const statusEl = document.getElementById("status");

const resultsEl = document.getElementById("results");

const sideToggle = document.getElementById("side-toggle");
const categoryToggle = document.getElementById("category-toggle");
const modeToggle = document.getElementById("mode-toggle");
const categoryField = document.getElementById("category-field");
const singleStrategyWrap = document.getElementById("single-strategy-wrap");
const compositeStrategyWrap = document.getElementById("composite-strategy-wrap");
const maPairWrap = document.getElementById("ma-pair-wrap");
const maEntrySelect = document.getElementById("ma-entry-select");
const maExitSelect = document.getElementById("ma-exit-select");
const maEntryMode = document.getElementById("ma-entry-mode");
const maExitMode = document.getElementById("ma-exit-mode");
const maPairScanBtn = document.getElementById("ma-pair-scan-btn");
const maPairResultsEl = document.getElementById("ma-pair-results");
const maPairCloseBtn = document.getElementById("ma-pair-close");
const targetField = document.getElementById("target-field");
const compositeList = document.getElementById("composite-list");
const compositeDesc = document.getElementById("composite-desc");

let allStrategies = [];
let currentSide = "buy";
let currentCategory = "technical";
let currentMode = "single";
let chartInstance = null;

let uiTooltipEl = null;

function ensureTooltipEl() {
  if (!uiTooltipEl) {
    uiTooltipEl = document.createElement("div");
    uiTooltipEl.id = "ui-tooltip";
    uiTooltipEl.className = "ui-tooltip hidden";
    document.body.appendChild(uiTooltipEl);
  }
  return uiTooltipEl;
}

function escTip(text) {
  return String(text || "")
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/</g, "&lt;");
}

function showTooltip(e) {
  const text = e.currentTarget.getAttribute("data-tip");
  if (!text) return;
  const tip = ensureTooltipEl();
  tip.textContent = text;
  tip.classList.remove("hidden");
  moveTooltip(e);
}

function moveTooltip(e) {
  const tip = uiTooltipEl;
  if (!tip || tip.classList.contains("hidden")) return;
  const pad = 14;
  const rect = tip.getBoundingClientRect();
  let x = e.clientX + pad;
  let y = e.clientY + pad;
  if (x + rect.width > window.innerWidth - 8) {
    x = e.clientX - rect.width - pad;
  }
  if (y + rect.height > window.innerHeight - 8) {
    y = e.clientY - rect.height - pad;
  }
  tip.style.left = `${Math.max(8, x)}px`;
  tip.style.top = `${Math.max(8, y)}px`;
}

function hideTooltip() {
  uiTooltipEl?.classList.add("hidden");
}

function bindTooltips(root = document) {
  const nodes =
    root instanceof Element && root.hasAttribute("data-tip")
      ? [root, ...root.querySelectorAll("[data-tip]")]
      : [...root.querySelectorAll("[data-tip]")];
  nodes.forEach((el) => {
    if (el.dataset.tipBound === "1") return;
    if (!el.getAttribute("data-tip")) return;
    el.dataset.tipBound = "1";
    el.addEventListener("mouseenter", showTooltip);
    el.addEventListener("mousemove", moveTooltip);
    el.addEventListener("mouseleave", hideTooltip);
  });
}

function setTip(el, text) {
  if (!el) return;
  if (text) {
    el.setAttribute("data-tip", text);
    bindTooltips(el);
  } else {
    el.removeAttribute("data-tip");
  }
}



function setActiveToggle(group, attr, value) {
  group.querySelectorAll(".toggle-btn, .chip").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset[attr] === value);
  });
}

async function parseApiResponse(res) {
  const text = await res.text();
  try {
    return { data: JSON.parse(text), error: null };
  } catch {
    const brief = text.trim().slice(0, 80);
    const hint =
      res.status >= 500 || brief.startsWith("Internal")
        ? "伺服器內部錯誤，請稍後再試或重新整理頁面"
        : `HTTP ${res.status} 回應格式錯誤`;
    return { data: null, error: `${hint}${brief ? `：${brief}` : ""}` };
  }
}



async function loadStrategies() {

  const res = await fetch("/api/strategies");

  const data = await res.json();

  allStrategies = data.strategies || [];

  renderStrategyOptions();

}



function renderStrategyOptions() {
  const filtered = allStrategies.filter(
    (s) => s.side === currentSide && s.category === currentCategory
  );
  strategySelect.innerHTML = filtered.length
    ? filtered
        .map(
          (s) =>
            `<option value="${s.id}" title="${escTip(s.description)}">${s.name}</option>`
        )
        .join("")
    : '<option value="">（無可用策略）</option>';
  updateStrategyDesc();
  renderCompositeList();
}

function renderCompositeList() {
  const filtered = allStrategies.filter((s) => s.side === currentSide);
  const groups = [
    { key: "technical", label: "技術面" },
    { key: "chips", label: "籌碼面" },
  ];

  compositeList.innerHTML = groups
    .map(({ key, label }) => {
      const items = filtered.filter((s) => s.category === key);
      if (!items.length) return "";
      return items
        .map(
          (s) => `
        <label class="composite-item" data-tip="${escTip(s.description)}">
          <input type="checkbox" name="composite" value="${s.id}" />
          <span class="composite-item-text">
            <span class="composite-item-name">${s.name}</span>
            <span class="composite-item-cat">${label}</span>
          </span>
        </label>`
        )
        .join("");
    })
    .join("");

  compositeList.querySelectorAll("input[type=checkbox]").forEach((el) => {
    el.addEventListener("change", () => {
      updateCompositeDesc();
      markResultsStale();
    });
  });
  bindTooltips(compositeList);
  updateCompositeDesc();
}

function getSelectedCompositeIds() {
  return [...compositeList.querySelectorAll("input[type=checkbox]:checked")].map(
    (el) => el.value
  );
}

function updateCompositeDesc() {
  const ids = getSelectedCompositeIds();
  if (!ids.length) {
    compositeDesc.textContent = "";
    return;
  }
  const names = ids
    .map((id) => allStrategies.find((s) => s.id === id)?.name)
    .filter(Boolean);
  compositeDesc.textContent = `已選：${names.join(" + ")}`;
}

function getMaPairStrategyId() {
  const entry = maEntrySelect.value;
  const exit = maExitSelect.value;
  if (entry === exit) return null;
  return `ma_pair_${currentSide}_${entry}_${exit}`;
}

function getMaPairEntryMode() {
  return maEntryMode?.value || "touch_ma";
}

function getMaPairExitMode() {
  return maExitMode?.value || "touch_ma";
}

function updateMaPairLabels() {
  const isBuy = currentSide === "buy";
  const entryMa = maEntrySelect.value;
  const exitMa = maExitSelect.value;

  document.getElementById("ma-entry-label").textContent = isBuy ? "買入均線" : "放空均線";
  document.getElementById("ma-exit-label").textContent = isBuy ? "賣出均線" : "回補均線";

  const entryTouch = maEntryMode.querySelector('[value="touch_ma"]');
  const entryVol = maEntryMode.querySelector('[value="volume_break_ma"]');
  const exitTouch = maExitMode.querySelector('[value="touch_ma"]');
  const exitVol = maExitMode.querySelector('[value="volume_break_ma"]');

  if (isBuy) {
    entryTouch.textContent = `觸及買入 MA${entryMa}`;
    entryVol.textContent = `帶量站上 MA${entryMa}`;
    exitTouch.textContent = `觸及賣出 MA${exitMa}`;
    exitVol.textContent = `帶量跌破 MA${exitMa}`;
  } else {
    entryTouch.textContent = `觸及放空 MA${entryMa}`;
    entryVol.textContent = `帶量跌破 MA${entryMa}`;
    exitTouch.textContent = `觸及回補 MA${exitMa}`;
    exitVol.textContent = `帶量站上 MA${exitMa}`;
  }

  const entryDesc =
    getMaPairEntryMode() === "touch_ma"
      ? `觸及 MA${entryMa}（±1.5%）`
      : `成交量 ≥ 20 日均量 1.5 倍且收盤站上 MA${entryMa}`;
  const exitDesc =
    getMaPairExitMode() === "touch_ma"
      ? `觸及 MA${exitMa}（±1.5%）`
      : isBuy
        ? `帶量且收盤跌破 MA${exitMa}`
        : `帶量且收盤站上 MA${exitMa}`;

  document.querySelector(".ma-pair-note").textContent =
    `進場：${entryDesc} · 出場：${exitDesc} · 假跌破後 5 日內站回可再進場 · 「最長持有」為逾時平倉`;
}

function setMode(mode) {
  currentMode = mode;
  setActiveToggle(modeToggle, "mode", mode);
  const isComposite = mode === "composite";
  const isMaPair = mode === "ma_pair";
  categoryField.classList.toggle("hidden", isComposite || isMaPair);
  singleStrategyWrap.classList.toggle("hidden", isComposite || isMaPair);
  compositeStrategyWrap.classList.toggle("hidden", !isComposite);
  maPairWrap.classList.toggle("hidden", !isMaPair);
  optimizeBtn.classList.toggle("hidden", isMaPair);
  maPairScanBtn.classList.toggle("hidden", !isMaPair);
  targetField.classList.toggle("hidden", isMaPair);
  document.getElementById("holding-label").textContent = "最高持有天數";
  if (isComposite) renderCompositeList();
  if (isMaPair) updateMaPairLabels();
}



function updateStrategyDesc() {
  const current = allStrategies.find((s) => s.id === strategySelect.value);
  strategyDesc.textContent = current ? current.description : "";
  setTip(strategySelect, current?.description || "");
}



sideToggle.addEventListener("click", (e) => {
  const btn = e.target.closest(".toggle-btn");
  if (!btn) return;
  currentSide = btn.dataset.side;
  setActiveToggle(sideToggle, "side", currentSide);
  renderStrategyOptions();
  updateMaPairLabels();
  markResultsStale();
});

modeToggle.addEventListener("click", (e) => {
  const btn = e.target.closest(".toggle-btn");
  if (!btn) return;
  setMode(btn.dataset.mode);
  markResultsStale();
});

categoryToggle.addEventListener("click", (e) => {

  const btn = e.target.closest(".toggle-btn");

  if (!btn) return;

  currentCategory = btn.dataset.category;

  setActiveToggle(categoryToggle, "category", currentCategory);

  renderStrategyOptions();
  markResultsStale();

});



strategySelect.addEventListener("change", () => {
  updateStrategyDesc();
  markResultsStale();
});



symbolInput.addEventListener("input", () => {

  clearTimeout(searchTimer);

  const q = symbolInput.value.trim();

  if (!q) {

    suggestionsEl.classList.add("hidden");

    suggestionsEl.innerHTML = "";

    return;

  }

  searchTimer = setTimeout(async () => {

    const res = await fetch(`/api/search?q=${encodeURIComponent(q)}`);

    const data = await res.json();

    renderSuggestions(data.results || []);

  }, 200);

});



function renderSuggestions(results) {

  if (!results.length) {

    suggestionsEl.classList.add("hidden");

    return;

  }

  suggestionsEl.innerHTML = results

    .map((r) => `<button type="button" data-id="${r.stock_id}">${r.display}</button>`)

    .join("");

  suggestionsEl.classList.remove("hidden");

  suggestionsEl.querySelectorAll("button").forEach((btn) => {

    btn.addEventListener("click", () => {

      symbolInput.value = btn.dataset.id;

      suggestionsEl.classList.add("hidden");
      markResultsStale();

    });

  });

}



document.addEventListener("click", (e) => {

  if (!suggestionsEl.contains(e.target) && e.target !== symbolInput) {

    suggestionsEl.classList.add("hidden");

  }

});



function showStatus(msg, type = "info") {

  statusEl.textContent = msg;

  statusEl.className = `status ${type}`;

  statusEl.classList.remove("hidden");

}



function hideStatus() {

  statusEl.classList.add("hidden");

}



function formatPct(v) {

  const n = Number(v);

  if (!Number.isFinite(n)) return "—";

  const sign = n > 0 ? "+" : "";

  return `${sign}${n.toFixed(2)}%`;

}



function winRateColor(rate) {
  if (!Number.isFinite(rate) || rate === 0) return "var(--muted)";
  return rate >= 60 ? "var(--bull)" : rate >= 50 ? "var(--warn)" : "var(--bear)";
}

function renderHorizons(data) {
  const panel = document.getElementById("today-panel");
  const horizons = (data.horizons || []).filter((h) => h.label !== "自訂");
  if (!horizons.length) {
    panel.classList.add("hidden");
    return;
  }
  const title = document.getElementById("today-title");
  const message = document.getElementById("today-message");
  const grid = document.getElementById("horizon-grid");
  const today = data.today || {};

  panel.classList.remove("hidden", "today-active");
  panel.classList.toggle("today-active", !!today.has_signal);

  title.textContent = today.has_signal
    ? `今日${data.strategy.side_label}訊號 · ${today.price}`
    : "短中長期歷史勝率";

  message.textContent = today.message || "";

  grid.innerHTML = horizons
    .map((h) => {
      const rateText = h.total_signals ? `${h.win_rate}%` : "—";
      const rateStyle = `color:${winRateColor(h.win_rate)}`;
      return `
        <div class="horizon-card${today.has_signal ? " horizon-card-active" : ""}">
          <div class="horizon-label">${h.label}（${h.days}日）</div>
          <div class="horizon-rate" style="${rateStyle}">${rateText}</div>
          <div class="horizon-meta">${h.wins} 勝 / ${h.losses} 敗 · 共 ${h.total_signals} 次</div>
          <div class="horizon-return">平均 ${formatPct(h.avg_return_pct)}</div>
        </div>`;
    })
    .join("");
}

function renderResults(data) {

  const name = data.stock_name

    ? `${data.stock_code} ${data.stock_name}`

    : data.stock_code;

  document.getElementById("stock-title").textContent = name;



  let meta = `${data.data.start} ~ ${data.data.end} · ${data.data.bars} 根 K 線 · ${data.data.source}`;

  if (data.data.chips_source) meta += ` · ${data.data.chips_source}`;

  document.getElementById("stock-meta").textContent = meta;



  const sideTag = data.strategy.side_label;
  const catTag = data.strategy.is_composite
    ? "複合"
    : data.strategy.category === "chips"
      ? "籌碼"
      : data.strategy.category === "ma_pair"
        ? "均線配對"
        : "技術";
  document.getElementById("strategy-badge").textContent =
    `${sideTag} · ${catTag} · ${data.strategy.name}`;



  const labels = data.labels || {};

  document.getElementById("th-entry-date").textContent = labels.entry || "進場日";

  document.getElementById("th-entry-price").textContent = labels.entry_price || "進場價";

  document.getElementById("th-exit-date").textContent = labels.exit || "出場日";
  document.getElementById("th-exit-price").textContent = labels.exit_price || "離場價";



  const s = data.summary;

  const winRateEl = document.getElementById("win-rate");

  winRateEl.textContent = s.total_signals ? `${s.win_rate}%` : "—";

  winRateEl.style.color =
    s.win_rate >= 60 ? "var(--bull)" : s.win_rate >= 50 ? "var(--warn)" : "var(--bear)";



  document.getElementById("total-signals").textContent = s.total_signals;

  document.getElementById("win-loss").textContent = `${s.wins} / ${s.losses}`;

  document.getElementById("avg-return").textContent = formatPct(s.avg_return_pct);

  document.getElementById("avg-win").textContent = formatPct(s.avg_win_pct);

  document.getElementById("avg-loss").textContent = formatPct(s.avg_loss_pct);
  document.getElementById("stats-extra").classList.remove("hidden");

  renderHorizons(data);

  const isSell = data.strategy.side === "sell";

  const winLabel = isSell ? "成功" : "獲利";

  const lossLabel = isSell ? "失敗" : "虧損";

  const noSignal = `回測期間內未出現符合條件的${sideTag}訊號`;



  const tbody = document.querySelector("#trades-table tbody");

  if (!data.trades.length) {

    tbody.innerHTML = `<tr><td colspan="7" class="muted">${noSignal}</td></tr>`;

  } else {

    tbody.innerHTML = data.trades

      .map(

        (t) => `

      <tr>

        <td>${t.entry_date}</td>

        <td>${t.entry_price}</td>

        <td>${t.exit_date}</td>

        <td>${t.exit_price}</td>

        <td class="${t.return_pct >= 0 ? "tag-win" : "tag-loss"}">${formatPct(t.return_pct)}</td>

        <td class="${t.is_win ? "tag-win" : "tag-loss"}">${t.is_win ? winLabel : lossLabel}</td>

        <td>${t.exit_reason}</td>

      </tr>`

      )

      .join("");

  }



  resultsEl.classList.remove("hidden");

  if (chartInstance && chartInstance.destroy) chartInstance.destroy();
  const chartEl = document.getElementById("chart-container");
  if (data.chart && window.BacktestChart) {
    requestAnimationFrame(() => {
      chartInstance = BacktestChart.mount(chartEl, {
        bars: data.chart.bars,
        markers: data.chart.markers,
        show_chips: data.chart.show_chips,
        defaultDays: data.chart.default_days,
      });
    });
  } else if (chartEl) {
    chartEl.innerHTML = "";
  }
}



function getBacktestFormBody() {
  const symbol = symbolInput.value.trim();
  const body = {
    symbol,
    years: Number(document.getElementById("years-select").value),
    holding_days: Number(document.getElementById("holding-input").value),
    target_pct: Number(document.getElementById("target-input").value),
    stop_pct: Number(document.getElementById("stop-input").value),
  };

  if (currentMode === "composite") {
    const ids = getSelectedCompositeIds();
    if (ids.length < 2) {
      return { error: "複合條件至少需選擇 2 個策略" };
    }
    body.strategy_ids = ids;
  } else if (currentMode === "ma_pair") {
    const sid = getMaPairStrategyId();
    if (!sid) {
      return { error: "買入均線與賣出均線不可相同" };
    }
    body.strategy_id = sid;
    body.entry_mode = getMaPairEntryMode();
    body.exit_mode = getMaPairExitMode();
  } else {
    if (!strategySelect.value) {
      return { error: "請選擇策略" };
    }
    body.strategy_id = strategySelect.value;
  }

  if (!symbol) {
    return { error: "請輸入股票代號或名稱" };
  }

  return { body };
}

let optimizeSort = "score";
let optimizeFilter = "qualified";
let optimizePayload = null;
let optimizeRadarInstance = null;

function clearOptimizeResults() {
  optimizeResultsEl.classList.add("hidden");
  optimizePayload = null;
  if (optimizeRadarInstance?.destroy) optimizeRadarInstance.destroy();
  optimizeRadarInstance = null;
  const pick = document.getElementById("optimize-pick");
  if (pick) pick.textContent = "";
  const compare = document.getElementById("optimize-compare");
  if (compare) {
    compare.classList.add("hidden");
    compare.innerHTML = "";
  }
  const compareTh = document.getElementById("optimize-compare-th");
  if (compareTh) compareTh.classList.add("hidden");
  const tbody = document.querySelector("#optimize-table tbody");
  if (tbody) tbody.innerHTML = "";
  optimizeResultsEl._displayRows = null;
}

function invalidateBacktestResults() {
  resultsEl.classList.add("hidden");
  if (chartInstance?.destroy) chartInstance.destroy();
  chartInstance = null;
}

function clearMaPairResults() {
  maPairResultsEl.classList.add("hidden");
  const tbody = document.querySelector("#ma-pair-table tbody");
  if (tbody) tbody.innerHTML = "";
  maPairResultsEl._displayRows = null;
}

function markResultsStale() {
  clearOptimizeResults();
  clearMaPairResults();
  invalidateBacktestResults();
}

function bindFormStaleListeners() {
  const paramIds = ["years-select", "holding-input", "target-input", "stop-input"];
  paramIds.forEach((id) => {
    document.getElementById(id)?.addEventListener("input", markResultsStale);
    document.getElementById(id)?.addEventListener("change", markResultsStale);
  });
  maEntrySelect?.addEventListener("change", () => {
    updateMaPairLabels();
    markResultsStale();
  });
  maExitSelect?.addEventListener("change", () => {
    updateMaPairLabels();
    markResultsStale();
  });
  maEntryMode?.addEventListener("change", () => {
    updateMaPairLabels();
    markResultsStale();
  });
  maExitMode?.addEventListener("change", () => {
    updateMaPairLabels();
    markResultsStale();
  });
  symbolInput.addEventListener("change", markResultsStale);
}

function formatDelta(value, { suffix = "", digits = 1 } = {}) {
  if (!Number.isFinite(value)) return "—";
  if (value === 0) return `<span class="delta-neutral">0${suffix}</span>`;
  const sign = value > 0 ? "+" : "";
  const cls = value > 0 ? "delta-positive" : "delta-negative";
  return `<span class="${cls}">${sign}${value.toFixed(digits)}${suffix}</span>`;
}

function getComparePayload() {
  const form = getBacktestFormBody();
  if (form.error) return null;
  if (form.body.strategy_ids?.length >= 2) {
    const defs = form.body.strategy_ids
      .map((id) => allStrategies.find((s) => s.id === id))
      .filter(Boolean);
    if (!defs.length || defs.some((d) => d.side !== currentSide)) return null;
    return { compare_strategy_ids: form.body.strategy_ids };
  }
  if (!form.body.strategy_id) return null;
  const strategy = allStrategies.find((s) => s.id === form.body.strategy_id);
  if (!strategy || strategy.side !== currentSide) return null;
  return { compare_strategy_id: form.body.strategy_id };
}

function compareDelta(row, baseline) {
  if (!baseline || !row) return null;
  const s = row.summary || {};
  const b = baseline.summary || {};
  return {
    score: (row.composite_score || 0) - (baseline.composite_score || 0),
    win_rate: (s.win_rate || 0) - (b.win_rate || 0),
    signals: (s.total_signals || 0) - (b.total_signals || 0),
    avg_return: (s.avg_return_pct || 0) - (b.avg_return_pct || 0),
  };
}

function buildRadarSeries(data, rows) {
  const series = [];
  const baseline = data.baseline;
  if (baseline) {
    series.push({ ...baseline, short_label: "目前策略" });
  }
  const picks = rows.filter((r) => r.composite_score >= 0).slice(0, baseline ? 3 : 4);
  picks.forEach((row, idx) => {
    series.push({ ...row, short_label: `TOP ${idx + 1}` });
  });
  return series;
}

function getFilteredOptimizeRows(data) {
  const p = data.params || {};
  const minSignals = p.min_signals || 3;
  let rows = [...(data.rankings || [])];

  if (optimizeFilter === "qualified") {
    rows = rows.filter((r) => r.composite_score >= 0);
  } else if (optimizeFilter === "single") {
    rows = rows.filter((r) => !r.is_composite);
  } else if (optimizeFilter === "composite") {
    rows = rows.filter((r) => r.is_composite);
  }

  rows.sort((a, b) => {
    const sa = a.summary || {};
    const sb = b.summary || {};
    if (optimizeSort === "win_rate") {
      return (sb.win_rate || 0) - (sa.win_rate || 0) || (sb.total_signals || 0) - (sa.total_signals || 0);
    }
    if (optimizeSort === "signals") {
      return (sb.total_signals || 0) - (sa.total_signals || 0) || (b.composite_score || 0) - (a.composite_score || 0);
    }
    return (b.composite_score || 0) - (a.composite_score || 0) || (sb.total_signals || 0) - (sa.total_signals || 0);
  });

  return { rows, minSignals, years: p.years || 3 };
}

function applyOptimizedStrategy(row, { runAfter = false } = {}) {
  if (!row) return;
  applyOptimizedStrategyForm(row);
  if (runAfter) {
    showStatus(`已套用「${row.name}」，正在回測…`, "info");
    runBacktest();
    return;
  }
  showStatus(`已套用「${row.name}」，可點「開始回測」查看詳情`, "info");
}

function applyOptimizedStrategyForm(row) {
  if (row.is_composite && row.strategy_ids?.length) {
    setMode("composite");
    compositeList.querySelectorAll("input[type=checkbox]").forEach((el) => {
      el.checked = row.strategy_ids.includes(el.value);
    });
    updateCompositeDesc();
    return;
  }
  if (!row.strategy_id) return;
  const strategy = allStrategies.find((s) => s.id === row.strategy_id);
  if (!strategy) return;
  setMode("single");
  currentCategory = strategy.category;
  setActiveToggle(categoryToggle, "category", currentCategory);
  renderStrategyOptions();
  strategySelect.value = row.strategy_id;
  updateStrategyDesc();
}

function renderOptimizeCompare(data, rows) {
  const el = document.getElementById("optimize-compare");
  const compareTh = document.getElementById("optimize-compare-th");
  const baseline = data.baseline;

  if (!baseline) {
    el.classList.add("hidden");
    el.innerHTML = "";
    compareTh.classList.add("hidden");
    if (data.compare_error) {
      el.classList.remove("hidden");
      el.textContent = data.compare_error;
    }
    return;
  }

  compareTh.classList.remove("hidden");
  el.classList.remove("hidden");
  const bs = baseline.summary || {};
  const best = rows.find((r) => r.composite_score >= 0) || data.best;
  const delta = best ? compareDelta(best, baseline) : null;
  const scoreText = baseline.composite_score >= 0 ? baseline.composite_score : "—";

  let html = `基準 <b data-tip="${escTip(baseline.description || baseline.name)}">${baseline.name}</b>：綜合 ${scoreText} · 勝率 ${bs.win_rate}% · ${bs.total_signals} 次`;
  if (delta && best) {
    html += ` → 最佳 <b data-tip="${escTip(best.description || best.name)}">${best.name}</b>：綜合 ${formatDelta(delta.score)} · 勝率 ${formatDelta(delta.win_rate, { suffix: "%", digits: 1 })} · 訊號 ${formatDelta(delta.signals, { suffix: " 次", digits: 0 })}`;
  }
  el.innerHTML = html;
  bindTooltips(el);
}

function renderOptimizeRadar(data, rows) {
  const el = document.getElementById("optimize-radar");
  if (optimizeRadarInstance?.destroy) optimizeRadarInstance.destroy();
  optimizeRadarInstance = null;
  if (!window.OptimizeViz) return;

  const p = data.params || {};
  const series = buildRadarSeries(data, rows);
  optimizeRadarInstance = OptimizeViz.mount(el, {
    series,
    years: p.years || 3,
    minSignals: p.min_signals || 3,
  });
}

function renderOptimizePick(data, rows) {
  const el = document.getElementById("optimize-pick");
  const best = rows.find((r) => r.composite_score >= 0) || data.best;
  if (!best) {
    el.textContent = "尚無達進場門檻的策略，可改篩選「全部」查看";
    return;
  }
  const s = best.summary || {};
  el.innerHTML = `建議 <b data-tip="${escTip(best.description || best.name)}">${best.name}</b> · 綜合 ${best.composite_score} · 勝率 ${s.win_rate}% · ${s.total_signals} 次 · <button type="button" class="btn-link pick-apply" data-tip="套用並回測">套用</button>`;
  el.querySelector(".pick-apply")?.addEventListener("click", () => {
    applyOptimizedStrategy(best, { runAfter: true });
  });
  bindTooltips(el);
}

function renderOptimizeTable(data, rows) {
  const tbody = document.querySelector("#optimize-table tbody");
  const colSpan = data.baseline ? 8 : 7;
  if (!rows.length) {
    tbody.innerHTML = `<tr><td colspan="${colSpan}" class="muted">此篩選條件下無結果</td></tr>`;
    return;
  }

  tbody.innerHTML = rows
    .map((row, idx) => {
      const s = row.summary || {};
      const rateText = s.total_signals ? `${s.win_rate}%` : "—";
      const scoreText = row.composite_score >= 0 ? row.composite_score : "—";
      const qualified = row.composite_score >= 0;
      const baseline = data.baseline;
      const delta = baseline ? compareDelta(row, baseline) : null;
      const deltaCol = baseline
        ? `<td>${delta ? formatDelta(delta.score) : "—"}</td>`
        : "";

      return `
      <tr class="${idx === 0 && qualified && optimizeSort === "score" ? "is-best" : ""}">
        <td>${idx + 1}</td>
        <td><span data-tip="${escTip(row.description || row.name)}">${row.name}</span></td>
        <td>${s.total_signals || 0}</td>
        <td style="color:${winRateColor(s.win_rate)}">${rateText}</td>
        <td class="${s.avg_return_pct >= 0 ? "tag-win" : "tag-loss"}">${formatPct(s.avg_return_pct)}</td>
        <td>${scoreText}</td>
        ${deltaCol}
        <td><button type="button" class="btn-link apply-btn" data-index="${idx}">套用</button></td>
      </tr>`;
    })
    .join("");

  optimizeResultsEl._displayRows = rows;
  bindTooltips(tbody);
}

function refreshOptimizeView() {
  if (!optimizePayload) return;
  const { rows } = getFilteredOptimizeRows(optimizePayload);
  renderOptimizePick(optimizePayload, rows);
  renderOptimizeCompare(optimizePayload, rows);
  renderOptimizeRadar(optimizePayload, rows);
  renderOptimizeTable(optimizePayload, rows);
}

function renderOptimizeResults(data) {
  optimizePayload = data;
  const name = data.stock_name
    ? `${data.stock_code} ${data.stock_name}`
    : data.stock_code;
  const p = data.params || {};

  document.getElementById("optimize-title").textContent =
    `${name} · ${data.side_label}策略最佳化`;
  document.getElementById("optimize-meta").textContent =
    `${data.data.start} ~ ${data.data.end} · 持有 ${p.holding_days} 日 · 停利 ${p.target_pct}% / 停損 ${p.stop_pct}% · 掃描 ${data.tested_count} 組 · 可進場 ${data.qualified_count ?? 0} 組`;

  refreshOptimizeView();

  optimizeResultsEl.classList.remove("hidden");
  bindTooltips(optimizeResultsEl);
  optimizeResultsEl.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

async function runBacktest() {
  const form = getBacktestFormBody();
  if (form.error) {
    showStatus(form.error, "error");
    return;
  }

  runBtn.disabled = true;
  showStatus("回測計算中，請稍候…");
  clearOptimizeResults();
  clearMaPairResults();
  resultsEl.classList.add("hidden");

  try {
    const res = await fetch("/api/backtest", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(form.body),
    });

    const { data, error } = await parseApiResponse(res);
    if (error) {
      showStatus(`連線失敗：${error}`, "error");
      return;
    }

    if (!data.ok) {
      showStatus(data.msg || "回測失敗", "error");
      return;
    }

    hideStatus();
    renderResults(data);
    if (data.msg) showStatus(data.msg, "info");
  } catch (err) {
    showStatus(`連線失敗：${err.message}`, "error");
  } finally {
    runBtn.disabled = false;
  }
}

async function runOptimize() {
  const symbol = symbolInput.value.trim();
  if (!symbol) {
    showStatus("請輸入股票代號或名稱", "error");
    return;
  }

  const years = Number(document.getElementById("years-select").value);
  const body = {
    symbol,
    side: currentSide,
    years,
    holding_days: Number(document.getElementById("holding-input").value),
    target_pct: Number(document.getElementById("target-input").value),
    stop_pct: Number(document.getElementById("stop-input").value),
    min_signals: Math.max(3, Math.round(years * 4)),
    top_n: 10,
    include_composites: true,
    ...getComparePayload(),
  };

  runBtn.disabled = true;
  optimizeBtn.disabled = true;
  invalidateBacktestResults();
  showStatus(`正在掃描所有${currentSide === "buy" ? "作多" : "作空"}策略，請稍候…`);

  try {
    const res = await fetch("/api/optimize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const { data, error } = await parseApiResponse(res);
    if (error) {
      showStatus(`連線失敗：${error}`, "error");
      return;
    }

    if (!data.ok) {
      showStatus(data.msg || "最佳化失敗", "error");
      return;
    }

    hideStatus();
    renderOptimizeResults(data);
    if (data.msg) showStatus(data.msg, "info");
  } catch (err) {
    showStatus(`連線失敗：${err.message}`, "error");
  } finally {
    runBtn.disabled = false;
    optimizeBtn.disabled = false;
  }
}

async function runMaPairScan() {
  const symbol = symbolInput.value.trim();
  if (!symbol) {
    showStatus("請輸入股票代號或名稱", "error");
    return;
  }

  const years = Number(document.getElementById("years-select").value);
  const body = {
    symbol,
    side: currentSide,
    years,
    max_hold_days: Number(document.getElementById("holding-input").value),
    stop_pct: Number(document.getElementById("stop-input").value),
    exit_mode: getMaPairExitMode(),
    entry_mode: getMaPairEntryMode(),
  };

  runBtn.disabled = true;
  maPairScanBtn.disabled = true;
  invalidateBacktestResults();
  clearOptimizeResults();
  showStatus("正在掃描均線配對組合…");

  try {
    const res = await fetch("/api/ma-pair-scan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!data.ok) {
      showStatus(data.msg || "掃描失敗", "error");
      return;
    }
    hideStatus();
    renderMaPairResults(data);
  } catch (err) {
    showStatus(`連線失敗：${err.message}`, "error");
  } finally {
    runBtn.disabled = false;
    maPairScanBtn.disabled = false;
  }
}

function renderMaPairResults(data) {
  const name = data.stock_name
    ? `${data.stock_code} ${data.stock_name}`
    : data.stock_code;
  const p = data.params || {};
  document.getElementById("ma-pair-title").textContent =
    `${name} · ${data.side_label}均線配對`;
  document.getElementById("ma-pair-meta").textContent =
    `${data.data.start} ~ ${data.data.end} · 最長持有 ${p.max_hold_days} 日 · 停損 ${p.stop_pct}% · 共 ${data.rankings.length} 組`;

  const tbody = document.querySelector("#ma-pair-table tbody");
  tbody.innerHTML = data.rankings
    .map((row, idx) => {
      const s = row.summary || {};
      const rateText = s.total_signals ? `${s.win_rate}%` : "—";
      return `
      <tr>
        <td>${idx + 1}</td>
        <td>${row.name || `MA${row.entry_ma} → MA${row.exit_ma}`}</td>
        <td>${s.total_signals || 0}</td>
        <td style="color:${winRateColor(s.win_rate)}">${rateText}</td>
        <td class="${s.avg_return_pct >= 0 ? "tag-win" : "tag-loss"}">${formatPct(s.avg_return_pct)}</td>
        <td><button type="button" class="btn-link ma-pair-apply" data-index="${idx}">回測</button></td>
      </tr>`;
    })
    .join("");

  maPairResultsEl._displayRows = data.rankings;
  maPairResultsEl.classList.remove("hidden");
  maPairResultsEl.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function applyMaPairRow(row) {
  if (!row) return;
  setMode("ma_pair");
  maEntrySelect.value = String(row.entry_ma);
  maExitSelect.value = String(row.exit_ma);
  if (row.entry_mode) maEntryMode.value = row.entry_mode;
  if (row.exit_mode) maExitMode.value = row.exit_mode;
  updateMaPairLabels();
  runBacktest();
}

runBtn.addEventListener("click", runBacktest);
optimizeBtn.addEventListener("click", runOptimize);
maPairScanBtn.addEventListener("click", runMaPairScan);
maPairCloseBtn.addEventListener("click", () => clearMaPairResults());
document.querySelector("#ma-pair-table tbody").addEventListener("click", (e) => {
  const btn = e.target.closest(".ma-pair-apply");
  if (!btn) return;
  const row = maPairResultsEl._displayRows?.[Number(btn.dataset.index)];
  applyMaPairRow(row);
});

optimizeCloseBtn.addEventListener("click", () => {
  clearOptimizeResults();
});

document.querySelector("#optimize-sort").addEventListener("click", (e) => {
  const btn = e.target.closest(".chip");
  if (!btn) return;
  optimizeSort = btn.dataset.sort;
  setActiveToggle(document.getElementById("optimize-sort"), "sort", optimizeSort);
  refreshOptimizeView();
});

document.querySelector("#optimize-filter").addEventListener("click", (e) => {
  const btn = e.target.closest(".chip");
  if (!btn) return;
  optimizeFilter = btn.dataset.filter;
  setActiveToggle(document.getElementById("optimize-filter"), "filter", optimizeFilter);
  refreshOptimizeView();
});

document.querySelector("#optimize-table tbody").addEventListener("click", (e) => {
  const btn = e.target.closest(".apply-btn");
  if (!btn) return;
  const idx = Number(btn.dataset.index);
  const row = optimizeResultsEl._displayRows?.[idx];
  if (!row) return;
  applyOptimizedStrategy(row, { runAfter: true });
});

loadStrategies()
  .then(() => {
    setMode("single");
    updateMaPairLabels();
    bindFormStaleListeners();
    bindTooltips(document);
  })
  .catch((err) => {
    showStatus(`無法載入策略清單：${err.message}`, "error");
  });


