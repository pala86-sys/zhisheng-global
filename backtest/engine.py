"""回測引擎：計算策略勝率與績效"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from backtest.chart_data import build_chart_payload
from backtest.chips import fetch_chips_for_symbol, merge_chips_with_prices
from backtest.data import fetch_ohlcv
from backtest.indicators import add_indicators
from backtest.ma_pair import (
    generate_ma_pair_entry_signals,
    ma_pair_trade_to_result,
    parse_ma_pair_id,
    scan_ma_pairs,
    simulate_ma_pair_trades,
)
from backtest.strategies import (
    SIDE_LABELS,
    STRATEGIES,
    CompositeStrategy,
    StrategyDef,
    build_composite_strategy,
    generate_combined_signals,
    generate_signals,
    needs_chips_data,
)

HORIZONS: list[tuple[str, int]] = [
    ("短期", 10),
    ("中期", 20),
    ("長期", 60),
]


@dataclass
class TradeResult:
    entry_date: str
    entry_price: float
    exit_date: str
    exit_price: float
    return_pct: float
    is_win: bool
    exit_reason: str


def _evaluate_trade(
    df: pd.DataFrame,
    entry_idx: int,
    *,
    side: str,
    holding_days: int,
    target_pct: float,
    stop_pct: float,
) -> TradeResult | None:
    if entry_idx >= len(df) - 1:
        return None

    entry_price = float(df.iloc[entry_idx]["Close"])
    if entry_price <= 0:
        return None

    is_sell = side == "sell"

    if is_sell:
        target_price = entry_price * (1 - target_pct / 100)
        stop_price = entry_price * (1 + stop_pct / 100)
    else:
        target_price = entry_price * (1 + target_pct / 100)
        stop_price = entry_price * (1 - stop_pct / 100)

    end_idx = min(entry_idx + holding_days, len(df) - 1)
    exit_price = float(df.iloc[end_idx]["Close"])
    exit_reason = "持有期滿"
    is_win = (exit_price < entry_price) if is_sell else (exit_price > entry_price)

    for j in range(entry_idx + 1, end_idx + 1):
        row = df.iloc[j]
        high = float(row["High"])
        low = float(row["Low"])
        close = float(row["Close"])

        if is_sell:
            hit_target = low <= target_price
            hit_stop = high >= stop_price
        else:
            hit_target = high >= target_price
            hit_stop = low <= stop_price

        if hit_target and hit_stop:
            exit_price = stop_price
            is_win = False
            exit_reason = "觸及停損"
            end_idx = j
            break
        if hit_stop:
            exit_price = stop_price
            is_win = False
            exit_reason = "觸及停損"
            end_idx = j
            break
        if hit_target:
            exit_price = target_price
            is_win = True
            exit_reason = "觸及停利"
            end_idx = j
            break

        if j == end_idx:
            exit_price = close
            is_win = (close < entry_price) if is_sell else (close > entry_price)
            exit_reason = "持有期滿"

    if is_sell:
        ret = (entry_price / exit_price - 1) * 100
    else:
        ret = (exit_price / entry_price - 1) * 100

    return TradeResult(
        entry_date=str(df.index[entry_idx].date()),
        entry_price=round(entry_price, 2),
        exit_date=str(df.index[end_idx].date()),
        exit_price=round(exit_price, 2),
        return_pct=round(ret, 2),
        is_win=is_win,
        exit_reason=exit_reason,
    )


def _collect_signal_indices(
    signals: pd.Series,
    *,
    min_gap_days: int,
) -> list[int]:
    indices: list[int] = []
    last_entry = -min_gap_days - 1
    for i in range(len(signals)):
        if not bool(signals.iloc[i]):
            continue
        if i - last_entry < min_gap_days:
            continue
        indices.append(i)
        last_entry = i
    return indices


def _trades_at_indices(
    df: pd.DataFrame,
    indices: list[int],
    *,
    side: str,
    holding_days: int,
    target_pct: float,
    stop_pct: float,
) -> list[TradeResult]:
    trades: list[TradeResult] = []
    for i in indices:
        trade = _evaluate_trade(
            df,
            i,
            side=side,
            holding_days=holding_days,
            target_pct=target_pct,
            stop_pct=stop_pct,
        )
        if trade:
            trades.append(trade)
    return trades


def _summarize_trades(trades: list[TradeResult]) -> dict:
    if not trades:
        return {
            "total_signals": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0.0,
            "avg_return_pct": 0.0,
            "avg_win_pct": 0.0,
            "avg_loss_pct": 0.0,
            "best_return_pct": 0.0,
            "worst_return_pct": 0.0,
        }

    returns = [t.return_pct for t in trades]
    wins = [t for t in trades if t.is_win]
    losses = [t for t in trades if not t.is_win]
    return {
        "total_signals": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(len(wins) / len(trades) * 100, 1),
        "avg_return_pct": round(float(np.mean(returns)), 2),
        "avg_win_pct": round(float(np.mean([t.return_pct for t in wins])), 2) if wins else 0.0,
        "avg_loss_pct": round(float(np.mean([t.return_pct for t in losses])), 2) if losses else 0.0,
        "best_return_pct": round(max(returns), 2),
        "worst_return_pct": round(min(returns), 2),
    }


def _build_horizon_stats(
    df: pd.DataFrame,
    indices: list[int],
    *,
    side: str,
    target_pct: float,
    stop_pct: float,
    custom_days: int | None = None,
) -> list[dict]:
    horizons = list(HORIZONS)
    if custom_days and custom_days not in {d for _, d in horizons}:
        horizons.append(("自訂", custom_days))

    stats: list[dict] = []
    for label, days in horizons:
        trades = _trades_at_indices(
            df,
            indices,
            side=side,
            holding_days=days,
            target_pct=target_pct,
            stop_pct=stop_pct,
        )
        summary = _summarize_trades(trades)
        stats.append({"label": label, "days": days, **summary})
    return stats


def _build_today_info(
    df: pd.DataFrame,
    signals: pd.Series,
    horizon_stats: list[dict],
    *,
    side_label: str,
) -> dict:
    latest_idx = len(df) - 1
    latest_date = str(df.index[latest_idx].date())
    latest_price = round(float(df.iloc[latest_idx]["Close"]), 2)
    has_signal = bool(signals.iloc[latest_idx])

    base = {
        "date": latest_date,
        "price": latest_price,
        "has_signal": has_signal,
        "side_label": side_label,
    }

    if has_signal:
        base["message"] = f"今日（{latest_date}）出現{side_label}訊號，以下為此策略歷史勝率參考"
    else:
        base["message"] = f"今日（{latest_date}）未出現{side_label}訊號"
    base["horizons"] = horizon_stats
    return base


def _strategy_payload(strategy: StrategyDef | CompositeStrategy) -> dict:
    payload = {
        "id": strategy.id,
        "name": strategy.name,
        "description": strategy.description,
        "side": strategy.side,
        "side_label": SIDE_LABELS[strategy.side],
        "category": strategy.category,
        "is_composite": isinstance(strategy, CompositeStrategy),
    }
    if isinstance(strategy, CompositeStrategy):
        payload["components"] = [
            {"id": sid, "name": STRATEGIES[sid].name, "description": STRATEGIES[sid].description}
            for sid in strategy.strategy_ids
        ]
    return payload


def _chart_category(strategy: StrategyDef | CompositeStrategy) -> str:
    if isinstance(strategy, CompositeStrategy):
        return "chips" if needs_chips_data(list(strategy.strategy_ids)) else "technical"
    return strategy.category


def _build_response(
    strategy: StrategyDef | CompositeStrategy,
    meta: dict,
    params: dict,
    enriched: pd.DataFrame,
    trades: list[TradeResult],
    horizon_stats: list[dict],
    today_info: dict,
    *,
    msg: str = "",
    is_ma_pair: bool = False,
) -> dict:
    summary = _summarize_trades(trades)
    side_label = SIDE_LABELS[strategy.side]
    entry_label = "進場日"
    exit_label = "離場日"

    result = {
        "ok": True,
        "symbol": meta["symbol"],
        "stock_code": meta["stock_code"],
        "stock_name": meta.get("stock_name"),
        "strategy": _strategy_payload(strategy),
        "params": params,
        "data": meta,
        "summary": summary,
        "horizons": horizon_stats,
        "today": today_info,
        "labels": {"entry": entry_label, "exit": exit_label, "entry_price": "進場價", "exit_price": "離場價"},
        "chart": build_chart_payload(
            enriched,
            trades,
            side=strategy.side,
            category=_chart_category(strategy),
        ),
        "trades": [
            {
                "entry_date": t.entry_date,
                "entry_price": t.entry_price,
                "exit_date": t.exit_date,
                "exit_price": t.exit_price,
                "return_pct": t.return_pct,
                "is_win": t.is_win,
                "exit_reason": t.exit_reason,
            }
            for t in trades[-30:]
        ],
    }
    if msg:
        result["msg"] = msg
    return result


def _resolve_strategy(
    strategy_id: str | None,
    strategy_ids: list[str] | None,
) -> StrategyDef | CompositeStrategy | dict:
    if strategy_ids:
        composite, err = build_composite_strategy(strategy_ids)
        if err:
            return {"ok": False, "msg": err}
        assert composite is not None
        return composite

    if not strategy_id or strategy_id not in STRATEGIES:
        return {"ok": False, "msg": "請選擇有效的策略"}
    return STRATEGIES[strategy_id]


def run_backtest(
    symbol: str,
    strategy_id: str | None = None,
    *,
    strategy_ids: list[str] | None = None,
    years: int = 3,
    holding_days: int = 20,
    target_pct: float = 5.0,
    stop_pct: float = 3.0,
    min_gap_days: int = 5,
    exit_mode: str | None = None,
    entry_mode: str | None = None,
) -> dict:
    strategy = _resolve_strategy(strategy_id, strategy_ids)
    if isinstance(strategy, dict):
        return strategy

    params = {
        "years": years,
        "holding_days": holding_days,
        "target_pct": target_pct,
        "stop_pct": stop_pct,
    }
    if isinstance(strategy, CompositeStrategy):
        params["strategy_ids"] = list(strategy.strategy_ids)
    if exit_mode:
        params["exit_mode"] = exit_mode
    if entry_mode:
        params["entry_mode"] = entry_mode

    df, meta = fetch_ohlcv(symbol, years=years)
    if not meta.get("ok"):
        return meta

    if len(df) < 80:
        return {"ok": False, "msg": "歷史資料不足，至少需要約 80 個交易日"}

    enriched = add_indicators(df)

    need_chips = (
        needs_chips_data(list(strategy.strategy_ids))
        if isinstance(strategy, CompositeStrategy)
        else strategy.category == "chips"
    )

    if need_chips:
        chips_df, chips_meta = fetch_chips_for_symbol(symbol, years=years)
        if not chips_meta.get("ok"):
            return chips_meta
        enriched = merge_chips_with_prices(enriched, chips_df)
        meta["chips_source"] = chips_meta.get("source")
        if enriched["Foreign_Net"].abs().sum() == 0:
            return {"ok": False, "msg": "籌碼資料與股價無法對齊，請換檔股票或縮短回測年數"}

    if isinstance(strategy, CompositeStrategy):
        signals = generate_combined_signals(enriched, list(strategy.strategy_ids))
    elif isinstance(strategy, StrategyDef) and parse_ma_pair_id(strategy.id):
        parsed = parse_ma_pair_id(strategy.id)
        assert parsed is not None
        side, entry_ma, exit_ma = parsed
        signals = generate_ma_pair_entry_signals(
            enriched, entry_ma, side=side, entry_mode=entry_mode or "touch_ma"
        )
    else:
        signals = generate_signals(enriched, strategy.id)

    signal_indices = _collect_signal_indices(signals, min_gap_days=min_gap_days)

    is_ma_pair = isinstance(strategy, StrategyDef) and bool(parse_ma_pair_id(strategy.id))
    if is_ma_pair:
        parsed = parse_ma_pair_id(strategy.id)
        assert parsed is not None
        side, entry_ma, exit_ma = parsed
        raw_trades = simulate_ma_pair_trades(
            enriched,
            entry_ma,
            exit_ma,
            side=side,
            entry_mode=entry_mode or "touch_ma",
            exit_mode=exit_mode or "touch_ma",
            max_hold_days=holding_days,
            stop_pct=stop_pct,
            min_gap_days=1,
        )
        trades = [ma_pair_trade_to_result(t) for t in raw_trades]
    else:
        trades = _trades_at_indices(
            enriched,
            signal_indices,
            side=strategy.side,
            holding_days=holding_days,
            target_pct=target_pct,
            stop_pct=stop_pct,
        )

    horizon_stats = _build_horizon_stats(
        enriched,
        signal_indices,
        side=strategy.side,
        target_pct=target_pct,
        stop_pct=stop_pct,
        custom_days=holding_days,
    ) if not is_ma_pair else []

    side_label = SIDE_LABELS[strategy.side]
    today_info = _build_today_info(
        enriched,
        signals,
        horizon_stats,
        side_label=side_label,
    )

    no_signal_msg = f"回測期間內未出現符合條件的{side_label}訊號"

    return _build_response(
        strategy,
        meta,
        params,
        enriched,
        trades,
        horizon_stats,
        today_info,
        msg=no_signal_msg if not trades else "",
        is_ma_pair=is_ma_pair,
    )


def run_ma_pair_scan(
    symbol: str,
    *,
    side: str = "buy",
    years: int = 3,
    max_hold_days: int = 120,
    stop_pct: float = 3.0,
    min_gap_days: int = 5,
    exit_mode: str = "touch_ma",
    entry_mode: str = "touch_ma",
) -> dict:
    if side not in ("buy", "sell"):
        return {"ok": False, "msg": "策略方向須為 buy 或 sell"}

    df, meta = fetch_ohlcv(symbol, years=years)
    if not meta.get("ok"):
        return meta
    if len(df) < 80:
        return {"ok": False, "msg": "歷史資料不足，至少需要約 80 個交易日"}

    enriched = add_indicators(df)
    rankings = scan_ma_pairs(
        enriched,
        side=side,
        max_hold_days=max_hold_days,
        stop_pct=stop_pct,
        min_gap_days=1,
        exit_mode=exit_mode,
        entry_mode=entry_mode,
    )

    return {
        "ok": True,
        "symbol": meta["symbol"],
        "stock_code": meta["stock_code"],
        "stock_name": meta.get("stock_name"),
        "side": side,
        "side_label": SIDE_LABELS[side],
        "params": {
            "years": years,
            "max_hold_days": max_hold_days,
            "stop_pct": stop_pct,
            "exit_mode": exit_mode,
            "entry_mode": entry_mode,
        },
        "data": meta,
        "rankings": rankings,
    }
