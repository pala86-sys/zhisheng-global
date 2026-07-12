"""一鍵策略最佳化：掃描單一策略與跨類複合條件，依綜合分排名（勝率 + 訊號頻率）"""

from __future__ import annotations

from backtest.chips import fetch_chips_for_symbol, merge_chips_with_prices
from backtest.data import fetch_ohlcv
from backtest.engine import (
    _build_horizon_stats,
    _collect_signal_indices,
    _summarize_trades,
    _trades_at_indices,
)
from backtest.indicators import add_indicators
from backtest.strategies import (
    CATEGORY_LABELS,
    SIDE_LABELS,
    STRATEGIES,
    build_composite_strategy,
    generate_combined_signals,
    generate_signals,
)


def _evaluate_candidate(
    enriched,
    *,
    strategy_ids: list[str],
    side: str,
    holding_days: int,
    target_pct: float,
    stop_pct: float,
    min_gap_days: int = 5,
) -> dict:
    if len(strategy_ids) == 1:
        signals = generate_signals(enriched, strategy_ids[0])
        sdef = STRATEGIES[strategy_ids[0]]
        name = sdef.name
        category = sdef.category
        description = sdef.description
        is_composite = False
    else:
        composite, err = build_composite_strategy(strategy_ids)
        if err or composite is None:
            return {"ok": False, "msg": err or "複合策略無效"}
        signals = generate_combined_signals(enriched, strategy_ids)
        name = composite.name
        category = "composite"
        description = composite.description
        is_composite = True

    indices = _collect_signal_indices(signals, min_gap_days=min_gap_days)
    trades = _trades_at_indices(
        enriched,
        indices,
        side=side,
        holding_days=holding_days,
        target_pct=target_pct,
        stop_pct=stop_pct,
    )
    summary = _summarize_trades(trades)
    horizons = _build_horizon_stats(
        enriched,
        indices,
        side=side,
        target_pct=target_pct,
        stop_pct=stop_pct,
        custom_days=holding_days,
    )
    short = next((h for h in horizons if h["days"] == 10), None)

    return {
        "ok": True,
        "strategy_id": strategy_ids[0] if len(strategy_ids) == 1 else None,
        "strategy_ids": list(strategy_ids) if is_composite else None,
        "name": name,
        "category": category,
        "category_label": CATEGORY_LABELS.get(category, "複合"),
        "description": description,
        "is_composite": is_composite,
        "summary": summary,
        "short_win_rate": short["win_rate"] if short else 0.0,
        "short_signals": short["total_signals"] if short else 0,
    }


def _default_min_signals(years: int) -> int:
    """依回測年數估算最低合理訊號數（約每年 4 次）"""
    return max(3, round(years * 4))


def _composite_score(summary: dict, *, years: int, min_signals: int) -> float:
    """
    綜合分：勝率為主，但訊號過少會打折（避免 2～3 次就 100% 勝率排第一）。
    理想頻率約每年 6 次進場機會。
    """
    n = summary["total_signals"]
    if n < min_signals:
        return -1.0

    win = float(summary["win_rate"])
    ret = float(summary["avg_return_pct"])
    baseline = max(float(min_signals), years * 6.0)
    freq_ratio = min(1.0, n / baseline)

    win_part = win * (0.45 + 0.55 * freq_ratio)
    ret_bonus = max(-5.0, min(5.0, ret)) * 0.5
    return round(win_part + ret_bonus, 1)


def _attach_score(row: dict, *, years: int, min_signals: int) -> dict:
    row["composite_score"] = _composite_score(row["summary"], years=years, min_signals=min_signals)
    return row


def _evaluate_baseline(
    enriched,
    *,
    compare_strategy_id: str | None,
    compare_strategy_ids: list[str] | None,
    side: str,
    holding_days: int,
    target_pct: float,
    stop_pct: float,
    min_gap_days: int,
    years: int,
    min_signals: int,
) -> tuple[dict | None, str | None]:
    ids = list(compare_strategy_ids or [])
    if compare_strategy_id:
        ids = [compare_strategy_id]
    ids = [s for s in dict.fromkeys(ids) if s]
    if not ids:
        return None, None

    for sid in ids:
        if sid not in STRATEGIES:
            return None, f"無法比較：未知策略 {sid}"
        if STRATEGIES[sid].side != side:
            return None, "目前策略方向與最佳化方向不同，無法比較"

    row = _evaluate_candidate(
        enriched,
        strategy_ids=ids,
        side=side,
        holding_days=holding_days,
        target_pct=target_pct,
        stop_pct=stop_pct,
        min_gap_days=min_gap_days,
    )
    if not row.get("ok"):
        return None, row.get("msg", "目前策略無法評估")
    _attach_score(row, years=years, min_signals=min_signals)
    row["is_baseline"] = True
    return row, None


def _rank_key(row: dict) -> tuple:
    return (row.get("composite_score", -1.0), row["summary"]["total_signals"])


def _candidate_ids_for_side(side: str, *, include_composites: bool) -> list[list[str]]:
    singles = [
        sid
        for sid, sdef in STRATEGIES.items()
        if sdef.side == side and sdef.category in ("technical", "chips")
    ]
    candidates: list[list[str]] = [[sid] for sid in singles]

    if not include_composites:
        return candidates

    technical = [sid for sid in singles if STRATEGIES[sid].category == "technical"]
    chips = [sid for sid in singles if STRATEGIES[sid].category == "chips"]
    for tid in technical:
        for cid in chips:
            candidates.append([tid, cid])

    return candidates


def run_optimize(
    symbol: str,
    *,
    side: str = "buy",
    years: int = 3,
    holding_days: int = 20,
    target_pct: float = 5.0,
    stop_pct: float = 3.0,
    min_gap_days: int = 5,
    min_signals: int | None = None,
    top_n: int = 10,
    include_composites: bool = True,
    compare_strategy_id: str | None = None,
    compare_strategy_ids: list[str] | None = None,
) -> dict:
    if side not in SIDE_LABELS:
        return {"ok": False, "msg": "請選擇有效的策略方向（作多或作空）"}

    if min_signals is None:
        min_signals = _default_min_signals(years)

    df, meta = fetch_ohlcv(symbol, years=years)
    if not meta.get("ok"):
        return meta

    if len(df) < 80:
        return {"ok": False, "msg": "歷史資料不足，至少需要約 80 個交易日"}

    enriched = add_indicators(df)

    chips_df, chips_meta = fetch_chips_for_symbol(symbol, years=years)
    if not chips_meta.get("ok"):
        return chips_meta
    enriched = merge_chips_with_prices(enriched, chips_df)
    meta["chips_source"] = chips_meta.get("source")
    if enriched["Foreign_Net"].abs().sum() == 0:
        return {"ok": False, "msg": "籌碼資料與股價無法對齊，請換檔股票或縮短回測年數"}

    baseline, compare_error = _evaluate_baseline(
        enriched,
        compare_strategy_id=compare_strategy_id,
        compare_strategy_ids=compare_strategy_ids,
        side=side,
        holding_days=holding_days,
        target_pct=target_pct,
        stop_pct=stop_pct,
        min_gap_days=min_gap_days,
        years=years,
        min_signals=min_signals,
    )

    candidates = _candidate_ids_for_side(side, include_composites=include_composites)
    rows: list[dict] = []
    errors = 0

    for strategy_ids in candidates:
        row = _evaluate_candidate(
            enriched,
            strategy_ids=strategy_ids,
            side=side,
            holding_days=holding_days,
            target_pct=target_pct,
            stop_pct=stop_pct,
            min_gap_days=min_gap_days,
        )
        if not row.get("ok"):
            errors += 1
            continue
        row["composite_score"] = _composite_score(
            row["summary"], years=years, min_signals=min_signals
        )
        rows.append(row)

    rows.sort(key=_rank_key, reverse=True)
    qualified = [r for r in rows if r["composite_score"] >= 0]
    top = rows[:top_n]

    best = qualified[0] if qualified else (rows[0] if rows else None)
    side_label = SIDE_LABELS[side]

    msg = (
        f"已掃描 {len(candidates)} 組{side_label}策略"
        f"（單一 {sum(1 for c in candidates if len(c) == 1)} 組"
        f"{'' if not include_composites else f'、複合 {sum(1 for c in candidates if len(c) > 1)} 組'}）"
        f"。排名綜合勝率與訊號頻率（至少 {min_signals} 次、理想約每年 6 次）"
    )
    if baseline:
        msg += f"。已與目前策略「{baseline['name']}」比較"
    if not qualified:
        msg += "。尚無符合最低訊號數的策略，以下為參考排名"

    return {
        "ok": True,
        "stock_code": meta.get("stock_code", symbol),
        "stock_name": meta.get("stock_name", ""),
        "side": side,
        "side_label": side_label,
        "params": {
            "years": years,
            "holding_days": holding_days,
            "target_pct": target_pct,
            "stop_pct": stop_pct,
            "min_signals": min_signals,
            "include_composites": include_composites,
        },
        "data": {
            "start": str(enriched.index[0].date()),
            "end": str(enriched.index[-1].date()),
            "bars": len(enriched),
            "source": meta.get("source"),
            "chips_source": meta.get("chips_source"),
        },
        "tested_count": len(candidates),
        "qualified_count": len(qualified),
        "best": best,
        "baseline": baseline,
        "compare_error": compare_error,
        "rankings": top,
        "msg": msg,
    }
