/**
 * 最佳化結果雷達圖：比較目前策略與 Top 推薦
 */
window.OptimizeViz = (function () {
  const AXES = [
    { key: "score", label: "綜合分" },
    { key: "win_rate", label: "勝率" },
    { key: "freq", label: "訊號頻率" },
    { key: "return", label: "平均報酬" },
    { key: "short", label: "短期勝率" },
  ];

  const COLORS = [
    { stroke: "#5b8cff", fill: "rgba(91, 140, 255, 0.18)", dash: [] },
    { stroke: "#f5b942", fill: "rgba(245, 185, 66, 0.15)", dash: [] },
    { stroke: "#3dd68c", fill: "rgba(61, 214, 140, 0.12)", dash: [6, 4] },
    { stroke: "#ab47bc", fill: "rgba(171, 71, 188, 0.12)", dash: [4, 4] },
  ];

  function metrics(row, ctx) {
    const s = row.summary || {};
    const signals = s.total_signals || 0;
    const ideal = Math.max(ctx.minSignals, ctx.years * 6);
    const ret = s.avg_return_pct || 0;
    const retNorm = Math.max(0, Math.min(100, ((ret + ctx.retSpan) / (2 * ctx.retSpan)) * 100));
    return {
      score: Math.max(0, row.composite_score || 0),
      win_rate: s.win_rate || 0,
      freq: ideal > 0 ? Math.min(100, (signals / ideal) * 100) : 0,
      return: retNorm,
      short: row.short_win_rate || 0,
    };
  }

  function mount(container, { series, years, minSignals }) {
    if (!container) return null;
    container.innerHTML = "";
    if (!series?.length) {
      container.innerHTML = '<p class="muted">無可比較的策略資料</p>';
      return null;
    }

    const retSpan = Math.max(
      5,
      ...series.map((r) => Math.abs(r.summary?.avg_return_pct || 0))
    );
    const ctx = { years, minSignals, retSpan };

    const wrap = document.createElement("div");
    wrap.className = "optimize-radar-wrap";
    const canvas = document.createElement("canvas");
    canvas.className = "optimize-radar-canvas";
    const legend = document.createElement("div");
    legend.className = "optimize-radar-legend";
    wrap.appendChild(canvas);
    wrap.appendChild(legend);
    container.appendChild(wrap);

    const normalized = series.map((row, i) => ({
      label: row.short_label || row.name,
      color: COLORS[i % COLORS.length],
      values: AXES.map((a) => metrics(row, ctx)[a.key]),
    }));

    legend.innerHTML = normalized
      .map(
        (s, i) =>
          `<span class="radar-legend-item"><i style="background:${COLORS[i].stroke}"></i>${s.label}</span>`
      )
      .join("");

    function draw() {
      const size = Math.min(container.clientWidth || 360, 420);
      const h = size;
      const w = size;
      const dpr = window.devicePixelRatio || 1;
      canvas.width = Math.round(w * dpr);
      canvas.height = Math.round(h * dpr);
      canvas.style.width = `${w}px`;
      canvas.style.height = `${h}px`;

      const ctx2 = canvas.getContext("2d");
      ctx2.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx2.clearRect(0, 0, w, h);

      const cx = w / 2;
      const cy = h / 2 + 8;
      const radius = Math.min(w, h) * 0.34;
      const n = AXES.length;

      function pointAt(axisIdx, value) {
        const angle = -Math.PI / 2 + (axisIdx * 2 * Math.PI) / n;
        const r = (value / 100) * radius;
        return [cx + Math.cos(angle) * r, cy + Math.sin(angle) * r];
      }

      ctx2.strokeStyle = "#243049";
      ctx2.fillStyle = "#8b97ad";
      ctx2.font = "11px sans-serif";

      for (let ring = 1; ring <= 4; ring++) {
        const rr = (radius * ring) / 4;
        ctx2.beginPath();
        for (let i = 0; i < n; i++) {
          const angle = -Math.PI / 2 + (i * 2 * Math.PI) / n;
          const x = cx + Math.cos(angle) * rr;
          const y = cy + Math.sin(angle) * rr;
          if (i === 0) ctx2.moveTo(x, y);
          else ctx2.lineTo(x, y);
        }
        ctx2.closePath();
        ctx2.stroke();
      }

      for (let i = 0; i < n; i++) {
        const angle = -Math.PI / 2 + (i * 2 * Math.PI) / n;
        ctx2.beginPath();
        ctx2.moveTo(cx, cy);
        ctx2.lineTo(cx + Math.cos(angle) * radius, cy + Math.sin(angle) * radius);
        ctx2.stroke();
        const lx = cx + Math.cos(angle) * (radius + 18);
        const ly = cy + Math.sin(angle) * (radius + 18);
        ctx2.textAlign = "center";
        ctx2.textBaseline = "middle";
        ctx2.fillText(AXES[i].label, lx, ly);
      }

      normalized.forEach((s) => {
        ctx2.beginPath();
        s.values.forEach((v, i) => {
          const [x, y] = pointAt(i, v);
          if (i === 0) ctx2.moveTo(x, y);
          else ctx2.lineTo(x, y);
        });
        ctx2.closePath();
        ctx2.fillStyle = s.color.fill;
        ctx2.fill();
        ctx2.strokeStyle = s.color.stroke;
        ctx2.lineWidth = 2;
        ctx2.setLineDash(s.color.dash);
        ctx2.stroke();
        ctx2.setLineDash([]);
      });
    }

    draw();
    const ro = new ResizeObserver(() => draw());
    ro.observe(container);
    return { destroy: () => ro.disconnect() };
  }

  return { mount };
})();
