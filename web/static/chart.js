/**
 * 回測 K 線圖（台股紅漲綠跌 + 策略訊號標記）
 */
window.BacktestChart = (function () {
  const UP = "#ef5350";
  const DOWN = "#26a69a";
  const BG = "#0d1422";
  const PANEL = "#121a2b";
  const GRID = "#243049";
  const TEXT = "#8b97ad";
  const CROSS = "#5b8cff";
  const MA_COLORS = {
    MA5: "#ffeb3b",
    MA10: "#29b6f6",
    MA20: "#ab47bc",
    MA60: "#e0e0e0",
  };
  const MA_SERIES = [
    { key: "MA5", label: "5日" },
    { key: "MA10", label: "10日" },
    { key: "MA20", label: "20日" },
    { key: "MA60", label: "60日" },
  ];
  const PERIODS = [60, 120, 180, 0];
  const REF_STANDARDS = [60, 120, 180];

  function fmt(v, d = 2) {
    if (v == null || Number.isNaN(v)) return "—";
    return Number(v).toFixed(d);
  }

  function mount(container, options) {
    if (!container) return null;
    const allBars = options.bars || [];
    if (!allBars.length) {
      container.innerHTML = '<p class="muted chart-empty">無 K 線資料</p>';
      return null;
    }

    const markers = options.markers || [];
    const showChips = !!options.show_chips;
    let period = options.defaultDays || 120;
    if (period === 0) period = allBars.length;

    let hoverIndex = -1;
    let chartApi = null;
    let chartHeight = 420;
    let barWidth = 8;
    let userAdjustedWidth = false;
    let refStandard = 60;

    container.innerHTML = "";
    container.classList.add("chart-box");

    const toolbar = document.createElement("div");
    toolbar.className = "chart-toolbar";

    const title = document.createElement("span");
    title.className = "chart-title";
    title.textContent = "K 線圖";

    const legend = document.createElement("span");
    legend.className = "chart-legend";
    legend.innerHTML =
      '<span class="leg-buy">▲ 進場日</span> · <span class="leg-exit">● 離場日</span>';

    const periodGroup = document.createElement("div");
    periodGroup.className = "chart-period-group";

    const probeBar = document.createElement("div");
    probeBar.className = "chart-probe-bar";

    const canvasWrap = document.createElement("div");
    canvasWrap.className = "chart-canvas-wrap";
    const canvas = document.createElement("canvas");
    canvas.className = "chart-canvas";
    canvasWrap.appendChild(canvas);

    toolbar.appendChild(title);
    toolbar.appendChild(periodGroup);
    container.appendChild(toolbar);

    const controls = document.createElement("div");
    controls.className = "chart-controls";

    const heightLabel = document.createElement("label");
    heightLabel.className = "chart-control";
    heightLabel.innerHTML = '高度 <span class="chart-control-val" data-for="height">420</span>px';
    const heightRange = document.createElement("input");
    heightRange.type = "range";
    heightRange.className = "chart-range";
    heightRange.min = "280";
    heightRange.max = "720";
    heightRange.step = "20";
    heightRange.value = String(chartHeight);
    heightLabel.appendChild(heightRange);

    const widthLabel = document.createElement("label");
    widthLabel.className = "chart-control chart-all-only";
    widthLabel.innerHTML = 'K棒寬 <span class="chart-control-val" data-for="width">8</span>px';
    const widthRange = document.createElement("input");
    widthRange.type = "range";
    widthRange.className = "chart-range";
    widthRange.min = "3";
    widthRange.max = "24";
    widthRange.step = "1";
    widthRange.value = String(barWidth);
    widthLabel.appendChild(widthRange);

    const refStandardWrap = document.createElement("div");
    refStandardWrap.className = "chart-ref-standard chart-all-only";
    const refStandardLabel = document.createElement("span");
    refStandardLabel.className = "chart-ref-label";
    refStandardLabel.textContent = "K棒標準";
    refStandardWrap.appendChild(refStandardLabel);
    const refStandardGroup = document.createElement("div");
    refStandardGroup.className = "chart-ref-group";
    const refStandardBtns = {};
    REF_STANDARDS.forEach((d) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "chart-btn";
      btn.textContent = `${d}日`;
      btn.addEventListener("click", () => setRefStandard(d));
      refStandardGroup.appendChild(btn);
      refStandardBtns[d] = btn;
    });
    refStandardWrap.appendChild(refStandardGroup);

    const fitBtn = document.createElement("button");
    fitBtn.type = "button";
    fitBtn.className = "chart-btn chart-fit-btn chart-all-only";
    fitBtn.textContent = "套用標準";
    fitBtn.title = "依所選 K 棒標準重新計算寬度（僅全部週期）";

    controls.appendChild(heightLabel);
    controls.appendChild(refStandardWrap);
    controls.appendChild(widthLabel);
    controls.appendChild(fitBtn);
    container.appendChild(controls);
    container.appendChild(legend);
    container.appendChild(probeBar);
    container.appendChild(canvasWrap);

    const periodBtns = {};
    PERIODS.forEach((d) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "chart-btn";
      btn.textContent = d === 0 ? "全部" : `${d}日`;
      btn.addEventListener("click", () => setPeriod(d));
      periodGroup.appendChild(btn);
      periodBtns[d] = btn;
    });

    function fmtExitDetail(mk, dayClose) {
      const reason = mk.exit_reason || "";
      const isStop = reason.includes("停損");
      let pricePart = fmt(mk.exit_price);
      const close =
        dayClose != null && Number.isFinite(dayClose)
          ? dayClose
          : mk.exit_close != null
            ? mk.exit_close
            : null;
      if (isStop) {
        pricePart = `停損價 ${fmt(mk.exit_price)}`;
        if (close != null && Math.abs(close - mk.exit_price) > 0.01) {
          pricePart += `（收 ${fmt(close)}）`;
        }
      } else if (close != null && Math.abs(close - mk.exit_price) <= 0.01) {
        pricePart = `收 ${fmt(close)}`;
      }
      const reasonShort = reason.replace(/^站回再進 · /, "");
      const reasonPart = reasonShort && !isStop ? ` · ${reasonShort}` : isStop ? " · 停損" : "";
      return `${mk.exit_date} ${pricePart}${reasonPart}`;
    }

    function visibleBars() {
      const n = period === 0 ? allBars.length : Math.min(period, allBars.length);
      return allBars.slice(-n);
    }

    function minPeriodForMarkers() {
      if (!markers.length) return options.defaultDays || 120;
      const dateToIdx = new Map(allBars.map((b, i) => [b.date, i]));
      let firstIdx = allBars.length;
      let matched = 0;
      markers.forEach((m) => {
        for (const d of [m.entry_date, m.exit_date]) {
          const idx = dateToIdx.get(d);
          if (idx !== undefined) {
            matched += 1;
            firstIdx = Math.min(firstIdx, idx);
          }
        }
      });
      if (!matched) return 0;
      return Math.min(allBars.length, allBars.length - firstIdx + 30);
    }

    function countVisibleTrades(bars) {
      const dates = new Set(bars.map((b) => b.date));
      return markers.filter((m) => dates.has(m.entry_date)).length;
    }

    function entryMarkerMap(bars) {
      const dates = new Set(bars.map((b) => b.date));
      const map = new Map();
      markers.forEach((m) => {
        if (dates.has(m.entry_date)) map.set(m.entry_date, m);
      });
      return map;
    }

    function exitMarkerMap(bars) {
      const dates = new Set(bars.map((b) => b.date));
      const map = new Map();
      markers.forEach((m) => {
        if (dates.has(m.exit_date)) map.set(m.exit_date, m);
      });
      return map;
    }

    function updateMarkerHint(bars) {
      const visible = countVisibleTrades(bars);
      if (!markers.length) {
        title.textContent = "K 線圖";
        return;
      }
      title.textContent = `K 線圖（此視窗 ${visible}/${markers.length} 筆）`;
      if (visible === 0) {
        legend.innerHTML =
          `<span class="chart-warn">此週期視窗內無交易（回測共 ${markers.length} 筆，請切換「180日」或「全部」）</span> · ` +
          '<span class="leg-buy">▲ 進場</span> · <span class="leg-exit">● 離場</span>';
      } else {
        legend.innerHTML =
          '<span class="leg-buy">▲ 進場日</span> · <span class="leg-exit">● 離場日</span> · ' +
          '<span class="leg-win">● 獲利</span> · <span class="leg-loss">● 虧損</span>';
      }
    }

    function syncWidthUI() {
      const rounded = Math.round(barWidth * 10) / 10;
      widthRange.value = String(rounded);
      widthLabel.querySelector('[data-for="width"]').textContent = String(rounded);
    }

    /** 60 / 120 / 180 日週期：K 棒自動填滿畫面（原本行為） */
    function autoFitBarWidthForPeriod() {
      const containerW = canvasWrap.clientWidth || 800;
      const plotW = containerW - 72;
      const n = visibleBars().length || 1;
      barWidth = Math.max(3, Math.min(24, plotW / n));
      syncWidthUI();
    }

    /** 全部週期：依所選 60 / 120 / 180 日標準決定 K 棒寬度 */
    function calibrateBarWidthFromReference() {
      const containerW = canvasWrap.clientWidth || 800;
      const plotW = containerW - 72;
      const refCount = Math.min(refStandard, allBars.length) || 1;
      barWidth = Math.max(3, Math.min(24, plotW / refCount));
      syncWidthUI();
    }

    function isAllPeriod() {
      return period === 0;
    }

    function updateAllPeriodControls() {
      const all = isAllPeriod();
      controls.querySelectorAll(".chart-all-only").forEach((el) => {
        el.classList.toggle("hidden", !all);
      });
      widthRange.disabled = !all;
      REF_STANDARDS.forEach((d) => {
        refStandardBtns[d].classList.toggle("chart-btn-active", d === refStandard);
      });
    }

    function applyBarWidthForCurrentPeriod() {
      if (isAllPeriod()) {
        if (!userAdjustedWidth) calibrateBarWidthFromReference();
      } else {
        userAdjustedWidth = false;
        autoFitBarWidthForPeriod();
      }
      updateAllPeriodControls();
    }

    function setRefStandard(d) {
      if (!isAllPeriod()) return;
      refStandard = d;
      userAdjustedWidth = false;
      calibrateBarWidthFromReference();
      updateAllPeriodControls();
      draw();
      requestAnimationFrame(scrollToLatest);
    }

    function updateControlLabels() {
      heightLabel.querySelector('[data-for="height"]').textContent = String(chartHeight);
      widthLabel.querySelector('[data-for="width"]').textContent = String(barWidth);
    }

    function plotCanvasWidth(barCount) {
      const containerW = canvasWrap.clientWidth || 800;
      if (!isAllPeriod()) return containerW;
      return Math.max(containerW, barCount * barWidth + 72);
    }

    function setPeriod(d) {
      period = d === 0 ? 0 : Math.min(d, allBars.length);
      PERIODS.forEach((p) => {
        periodBtns[p].classList.toggle("chart-btn-active", p === d);
      });
      hoverIndex = -1;
      applyBarWidthForCurrentPeriod();
      const bars = visibleBars();
      updateMarkerHint(bars);
      draw();
      updateProbe();
      requestAnimationFrame(scrollToLatest);
    }

    function updateProbe() {
      const bars = visibleBars();
      const idx = hoverIndex >= 0 ? hoverIndex : bars.length - 1;
      const row = bars[idx];
      if (!row) {
        probeBar.textContent = "";
        return;
      }
      const up = row.close >= row.open;
      const color = up ? UP : DOWN;
      let html = `<span class="probe-date">${row.date}</span>
        <span>開 <b style="color:${color}">${fmt(row.open)}</b></span>
        <span>高 <b style="color:${color}">${fmt(row.high)}</b></span>
        <span>低 <b style="color:${color}">${fmt(row.low)}</b></span>
        <span>收 <b style="color:${color}">${fmt(row.close)}</b></span>
        <span>量 ${Math.round(row.volume || 0).toLocaleString("zh-TW")}</span>`;
      MA_SERIES.forEach(({ key, label }) => {
        const maColor = MA_COLORS[key];
        html += ` <span class="probe-ma"><i style="background:${maColor}"></i>${label} <b style="color:${maColor}">${fmt(row[key])}</b></span>`;
      });
      if (showChips && row.foreign_net != null) {
        const fn = row.foreign_net;
        const fc = fn > 0 ? UP : fn < 0 ? DOWN : TEXT;
        html += ` <span>外資 <b style="color:${fc}">${fn > 0 ? "+" : ""}${fn}</b> 張</span>`;
        html += ` <span>投信 <b>${row.trust_net > 0 ? "+" : ""}${row.trust_net}</b> 張</span>`;
      }
      const entryMk = entryMarkerMap(bars).get(row.date);
      const exitMk = exitMarkerMap(bars).get(row.date);
      if (entryMk) {
        const winLabel = entryMk.is_win ? "獲利" : "虧損";
        html += ` <span class="probe-signal probe-entry">▲ 進場 ${fmt(entryMk.entry_price)} · 離場 ${fmtExitDetail(entryMk, row.date === entryMk.exit_date ? row.close : null)} · ${winLabel} ${entryMk.return_pct > 0 ? "+" : ""}${fmt(entryMk.return_pct)}%</span>`;
      }
      if (exitMk && !entryMk) {
        const winLabel = exitMk.is_win ? "獲利" : "虧損";
        html += ` <span class="probe-signal probe-exit">● 離場 ${fmtExitDetail(exitMk, row.close)} · 進場 ${exitMk.entry_date} ${fmt(exitMk.entry_price)} · ${winLabel} ${exitMk.return_pct > 0 ? "+" : ""}${fmt(exitMk.return_pct)}%</span>`;
      }
      probeBar.innerHTML = html;
    }

    function draw() {
      const bars = visibleBars();
      const entryMap = entryMarkerMap(bars);
      const exitMap = exitMarkerMap(bars);
      const w = plotCanvasWidth(bars.length);
      const h = chartHeight;
      const dpr = window.devicePixelRatio || 1;
      canvas.width = Math.round(w * dpr);
      canvas.height = Math.round(h * dpr);
      canvas.style.width = `${w}px`;
      canvas.style.height = `${h}px`;
      canvasWrap.style.overflowX =
        isAllPeriod() && bars.length * barWidth + 72 > (canvasWrap.clientWidth || w) - 1
          ? "auto"
          : "hidden";

      const ctx = canvas.getContext("2d");
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.fillStyle = BG;
      ctx.fillRect(0, 0, w, h);

      if (!bars.length) return;

      const padL = 56;
      const padR = 16;
      const padT = 12;
      const padB = 24;
      const plotW = w - padL - padR;
      const innerH = h - padT - padB;
      const priceH = showChips ? innerH * 0.62 : innerH * 0.72;
      const volH = showChips ? innerH * 0.18 : innerH * 0.28;
      const chipH = showChips ? innerH * 0.2 : 0;

      const priceTop = padT;
      const volTop = priceTop + priceH + 6;
      const chipTop = volTop + volH + 6;

      let minP = Infinity;
      let maxP = -Infinity;
      let maxV = 0;
      let maxChip = 1;
      bars.forEach((b) => {
        minP = Math.min(minP, b.low);
        maxP = Math.max(maxP, b.high);
        maxV = Math.max(maxV, b.volume || 0);
        if (showChips) maxChip = Math.max(maxChip, Math.abs(b.total_net || 0));
      });
      const padPrice = (maxP - minP) * 0.06 || maxP * 0.02 || 1;
      minP -= padPrice;
      maxP += padPrice;

      const n = bars.length;
      const gap = barWidth;
      const candleW = Math.max(2, gap * 0.55);

      function xAt(i) {
        return padL + gap * i + gap / 2;
      }
      function yPrice(p) {
        return priceTop + ((maxP - p) / (maxP - minP)) * priceH;
      }
      function yVol(v) {
        return volTop + volH - (v / maxV) * volH;
      }
      function yChip(v) {
        const mid = chipTop + chipH / 2;
        return mid - (v / maxChip) * (chipH / 2 - 2);
      }

      function drawGrid(y0, hh) {
        ctx.strokeStyle = GRID;
        ctx.lineWidth = 0.5;
        for (let i = 0; i <= 4; i++) {
          const y = y0 + (hh * i) / 4;
          ctx.beginPath();
          ctx.moveTo(padL, y);
          ctx.lineTo(padL + plotW, y);
          ctx.stroke();
        }
      }

      drawGrid(priceTop, priceH);
      if (volH > 0) drawGrid(volTop, volH);

      // MA lines
      MA_SERIES.forEach(({ key }) => {
        ctx.strokeStyle = MA_COLORS[key];
        ctx.lineWidth = 1;
        ctx.beginPath();
        let started = false;
        bars.forEach((b, i) => {
          const v = b[key];
          if (v == null) return;
          const x = xAt(i);
          const y = yPrice(v);
          if (!started) {
            ctx.moveTo(x, y);
            started = true;
          } else ctx.lineTo(x, y);
        });
        ctx.stroke();
      });

      // Candles
      bars.forEach((b, i) => {
        const x = xAt(i);
        const up = b.close >= b.open;
        const color = up ? UP : DOWN;
        const yH = yPrice(b.high);
        const yL = yPrice(b.low);
        const yO = yPrice(b.open);
        const yC = yPrice(b.close);
        ctx.strokeStyle = color;
        ctx.fillStyle = color;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(x, yH);
        ctx.lineTo(x, yL);
        ctx.stroke();
        const top = Math.min(yO, yC);
        const bodyH = Math.max(Math.abs(yC - yO), 1);
        ctx.fillRect(x - candleW / 2, top, candleW, bodyH);
      });

      // Volume
      bars.forEach((b, i) => {
        const up = b.close >= b.open;
        const x = xAt(i);
        const y0 = yVol(0);
        const y1 = yVol(b.volume || 0);
        ctx.fillStyle = up ? UP : DOWN;
        ctx.globalAlpha = 0.75;
        ctx.fillRect(x - candleW / 2, y1, candleW, y0 - y1);
        ctx.globalAlpha = 1;
      });

      // Chips bar chart
      if (showChips && chipH > 0) {
        const midY = chipTop + chipH / 2;
        ctx.strokeStyle = GRID;
        ctx.beginPath();
        ctx.moveTo(padL, midY);
        ctx.lineTo(padL + plotW, midY);
        ctx.stroke();
        bars.forEach((b, i) => {
          const v = b.total_net || 0;
          if (!v) return;
          const x = xAt(i);
          const y = yChip(v);
          ctx.fillStyle = v > 0 ? UP : DOWN;
          ctx.fillRect(x - candleW / 2, Math.min(y, midY), candleW, Math.abs(y - midY));
        });
        ctx.fillStyle = TEXT;
        ctx.font = "10px sans-serif";
        ctx.fillText("法人", padL - 44, chipTop + 10);
      }

      // Entry markers ▲
      const RED = "#ef5350";
      const GREEN = "#26a69a";
      const priceBottom = priceTop + priceH;
      bars.forEach((b, i) => {
        const mk = entryMap.get(b.date);
        if (!mk) return;
        const x = xAt(i);
        const yLow = yPrice(b.low);
        const yHigh = yPrice(b.high);
        const fillColor = mk.side === "buy" ? RED : GREEN;
        const size = Math.max(7, Math.min(10, gap * 0.4));
        ctx.fillStyle = fillColor;
        ctx.strokeStyle = "#ffffff";
        ctx.lineWidth = 1.2;
        ctx.beginPath();
        if (mk.side === "buy") {
          const baseY = Math.min(yLow + size + 4, priceBottom - 2);
          const tipY = baseY - size;
          ctx.moveTo(x, tipY);
          ctx.lineTo(x - size, baseY);
          ctx.lineTo(x + size, baseY);
        } else {
          const baseY = Math.max(yHigh - size - 4, priceTop + 2);
          const tipY = baseY + size;
          ctx.moveTo(x, tipY);
          ctx.lineTo(x - size, baseY);
          ctx.lineTo(x + size, baseY);
        }
        ctx.closePath();
        ctx.fill();
        ctx.stroke();
      });

      // Exit markers ●
      bars.forEach((b, i) => {
        const mk = exitMap.get(b.date);
        if (!mk) return;
        const x = xAt(i);
        const yLow = yPrice(b.low);
        const yHigh = yPrice(b.high);
        const size = Math.max(5, Math.min(8, gap * 0.35));
        const fillColor = mk.is_win
          ? mk.side === "buy"
            ? RED
            : GREEN
          : mk.side === "buy"
            ? GREEN
            : RED;
        const cy = mk.side === "buy" ? Math.max(yHigh - size - 3, priceTop + 2) : Math.min(yLow + size + 3, priceBottom - 2);
        ctx.beginPath();
        ctx.arc(x, cy, size * 0.55, 0, Math.PI * 2);
        ctx.fillStyle = fillColor;
        ctx.strokeStyle = "#ffffff";
        ctx.lineWidth = 1.2;
        ctx.fill();
        ctx.stroke();
      });

      // X-axis labels
      ctx.fillStyle = TEXT;
      ctx.font = "10px sans-serif";
      const step = Math.max(1, Math.floor(n / 6));
      for (let i = 0; i < n; i += step) {
        const label = bars[i].date.slice(5);
        ctx.fillText(label, xAt(i) - 14, h - 6);
      }

      // Y-axis price labels
      for (let i = 0; i <= 4; i++) {
        const p = maxP - ((maxP - minP) * i) / 4;
        const y = priceTop + (priceH * i) / 4;
        ctx.fillText(p.toFixed(0), 4, y + 3);
      }

      // Crosshair
      if (hoverIndex >= 0 && hoverIndex < n) {
        const x = xAt(hoverIndex);
        ctx.strokeStyle = CROSS;
        ctx.globalAlpha = 0.5;
        ctx.setLineDash([4, 4]);
        ctx.beginPath();
        ctx.moveTo(x, padT);
        ctx.lineTo(x, padT + innerH);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.globalAlpha = 1;
      }
    }

    function scrollToLatest() {
      if (canvasWrap.scrollWidth > canvasWrap.clientWidth) {
        canvasWrap.scrollLeft = canvasWrap.scrollWidth - canvasWrap.clientWidth;
      }
    }

    function onMove(offsetX) {
      const bars = visibleBars();
      const padL = 56;
      const x = offsetX - padL;
      const idx = Math.floor((x + barWidth / 2) / barWidth);
      hoverIndex = Math.max(0, Math.min(bars.length - 1, idx));
      draw();
      updateProbe();
    }

    canvas.addEventListener("mousemove", (e) => onMove(e.offsetX));
    canvas.addEventListener("mouseleave", () => {
      hoverIndex = -1;
      draw();
      updateProbe();
    });

    heightRange.addEventListener("input", () => {
      chartHeight = Number(heightRange.value);
      updateControlLabels();
      draw();
    });

    widthRange.addEventListener("input", () => {
      if (!isAllPeriod()) return;
      barWidth = Number(widthRange.value);
      userAdjustedWidth = true;
      updateControlLabels();
      draw();
      requestAnimationFrame(scrollToLatest);
    });

    fitBtn.addEventListener("click", () => {
      if (!isAllPeriod()) return;
      userAdjustedWidth = false;
      calibrateBarWidthFromReference();
      draw();
      requestAnimationFrame(scrollToLatest);
    });

    canvasWrap.addEventListener("scroll", () => {
      if (hoverIndex >= 0) updateProbe();
    });

    const ro = new ResizeObserver(() => {
      applyBarWidthForCurrentPeriod();
      draw();
    });
    ro.observe(canvasWrap);

    function pickInitialPeriod() {
      if (!markers.length) {
        const d = options.defaultDays || 120;
        return d >= allBars.length ? 0 : d;
      }
      // 有訊號時預設顯示全部，確保三角形標記可見
      return 0;
    }

    function boot() {
      updateControlLabels();
      setPeriod(pickInitialPeriod());
    }

    requestAnimationFrame(() => requestAnimationFrame(boot));
    chartApi = { redraw: draw, destroy: () => ro.disconnect() };
    return chartApi;
  }

  return { mount };
})();
