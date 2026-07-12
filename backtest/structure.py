"""價格結構分析：波段高低點、頭頭高底底高、趨勢線突破"""

from __future__ import annotations

import numpy as np
import pandas as pd


def find_swing_indices(
    highs: np.ndarray,
    lows: np.ndarray,
    *,
    window: int,
) -> tuple[list[int], list[int]]:
    """找出局部波段高點與低點的索引"""
    n = len(highs)
    if n < window * 2 + 1:
        return [], []

    swing_highs: list[int] = []
    swing_lows: list[int] = []
    for i in range(window, n - window):
        seg_h = highs[i - window : i + window + 1]
        seg_l = lows[i - window : i + window + 1]
        if highs[i] >= seg_h.max():
            swing_highs.append(i)
        if lows[i] <= seg_l.min():
            swing_lows.append(i)
    return swing_highs, swing_lows


def _trendline_value(idx1: int, price1: float, idx2: int, price2: float, at_idx: int) -> float:
    if idx2 == idx1:
        return price1
    slope = (price2 - price1) / (idx2 - idx1)
    return price1 + slope * (at_idx - idx1)


def _recent_swings(indices: list[int], prices: np.ndarray, upto: int, *, count: int) -> list[tuple[int, float]]:
    picked: list[tuple[int, float]] = []
    for idx in reversed(indices):
        if idx > upto:
            continue
        picked.append((idx, float(prices[idx])))
        if len(picked) >= count:
            break
    picked.reverse()
    return picked


def _is_higher_highs_lows(highs: list[tuple[int, float]], lows: list[tuple[int, float]]) -> bool:
    if len(highs) < 2 or len(lows) < 2:
        return False
    return highs[-1][1] > highs[-2][1] and lows[-1][1] > lows[-2][1]


def _is_lower_highs_lows(highs: list[tuple[int, float]], lows: list[tuple[int, float]]) -> bool:
    if len(highs) < 2 or len(lows) < 2:
        return False
    return highs[-1][1] < highs[-2][1] and lows[-1][1] < lows[-2][1]


def _near_level(price: float, level: float, tol_pct: float) -> bool:
    if level <= 0:
        return False
    tol = tol_pct / 100.0
    return level * (1 - tol) <= price <= level * (1 + tol)


def generate_hh_hl_pullback_signals(
    df: pd.DataFrame,
    *,
    swing_window: int = 5,
    pullback_tol_pct: float = 2.0,
    max_swing_age: int = 80,
) -> pd.Series:
    """
    頭頭高 + 底底高上升結構確立後，回測前波低點或月線附近轉強時作多。
    """
    n = len(df)
    out = np.zeros(n, dtype=bool)
    if n < swing_window * 2 + 20:
        return pd.Series(out, index=df.index)

    highs = df["High"].to_numpy(dtype=float)
    lows = df["Low"].to_numpy(dtype=float)
    closes = df["Close"].to_numpy(dtype=float)
    opens = df["Open"].to_numpy(dtype=float)
    ma20 = df["MA20"].to_numpy(dtype=float) if "MA20" in df.columns else None

    swing_high_idx, swing_low_idx = find_swing_indices(highs, lows, window=swing_window)
    confirm_lag = swing_window

    for i in range(swing_window * 2 + 2, n):
        confirmed_upto = i - confirm_lag
        recent_highs = _recent_swings(swing_high_idx, highs, confirmed_upto, count=2)
        recent_lows = _recent_swings(swing_low_idx, lows, confirmed_upto, count=2)
        if not _is_higher_highs_lows(recent_highs, recent_lows):
            continue

        last_low_idx, last_low = recent_lows[-1]
        if i - last_low_idx > max_swing_age:
            continue

        touched_support = _near_level(lows[i], last_low, pullback_tol_pct)
        if ma20 is not None and np.isfinite(ma20[i]):
            touched_support = touched_support or _near_level(lows[i], ma20[i], pullback_tol_pct)

        if not touched_support:
            continue

        bullish_turn = closes[i] > opens[i] and closes[i] > closes[i - 1]
        still_uptrend = closes[i] >= last_low and (
            ma20 is None or not np.isfinite(ma20[i]) or closes[i] >= ma20[i] * (1 - pullback_tol_pct / 100)
        )
        if bullish_turn and still_uptrend:
            out[i] = True

    return pd.Series(out, index=df.index)


def generate_downtrend_breakout_signals(
    df: pd.DataFrame,
    *,
    swing_window: int = 5,
    lookback: int = 120,
) -> pd.Series:
    """
    連線近期兩個遞降波段高點形成下降趨勢線，收盤向上突破時作多。
    """
    n = len(df)
    out = np.zeros(n, dtype=bool)
    if n < swing_window * 2 + 10:
        return pd.Series(out, index=df.index)

    highs = df["High"].to_numpy(dtype=float)
    closes = df["Close"].to_numpy(dtype=float)
    swing_high_idx, _ = find_swing_indices(highs, df["Low"].to_numpy(dtype=float), window=swing_window)
    confirm_lag = swing_window

    for i in range(swing_window * 2 + 2, n):
        start = max(0, i - lookback)
        confirmed_upto = i - confirm_lag
        candidates = [idx for idx in swing_high_idx if start <= idx <= confirmed_upto]
        if len(candidates) < 2:
            continue

        recent = candidates[-2:]
        idx1, idx2 = recent[0], recent[1]
        p1, p2 = float(highs[idx1]), float(highs[idx2])
        if p2 >= p1 or idx2 <= idx1:
            continue

        line_prev = _trendline_value(idx1, p1, idx2, p2, i - 1)
        line_now = _trendline_value(idx1, p1, idx2, p2, i)
        if closes[i] > line_now and closes[i - 1] <= line_prev:
            out[i] = True

    return pd.Series(out, index=df.index)


def generate_ll_lh_rally_signals(
    df: pd.DataFrame,
    *,
    swing_window: int = 5,
    rally_tol_pct: float = 2.0,
    max_swing_age: int = 80,
) -> pd.Series:
    """
    頭頭低 + 底底低下降結構確立後，反彈至前波高點或月線壓力轉弱時作空。
    """
    n = len(df)
    out = np.zeros(n, dtype=bool)
    if n < swing_window * 2 + 20:
        return pd.Series(out, index=df.index)

    highs = df["High"].to_numpy(dtype=float)
    lows = df["Low"].to_numpy(dtype=float)
    closes = df["Close"].to_numpy(dtype=float)
    opens = df["Open"].to_numpy(dtype=float)
    ma20 = df["MA20"].to_numpy(dtype=float) if "MA20" in df.columns else None

    swing_high_idx, swing_low_idx = find_swing_indices(highs, lows, window=swing_window)
    confirm_lag = swing_window

    for i in range(swing_window * 2 + 2, n):
        confirmed_upto = i - confirm_lag
        recent_highs = _recent_swings(swing_high_idx, highs, confirmed_upto, count=2)
        recent_lows = _recent_swings(swing_low_idx, lows, confirmed_upto, count=2)
        if not _is_lower_highs_lows(recent_highs, recent_lows):
            continue

        last_high_idx, last_high = recent_highs[-1]
        if i - last_high_idx > max_swing_age:
            continue

        touched_resistance = _near_level(highs[i], last_high, rally_tol_pct)
        if ma20 is not None and np.isfinite(ma20[i]):
            touched_resistance = touched_resistance or _near_level(highs[i], ma20[i], rally_tol_pct)

        if not touched_resistance:
            continue

        bearish_turn = closes[i] < opens[i] and closes[i] < closes[i - 1]
        still_downtrend = closes[i] <= last_high and (
            ma20 is None or not np.isfinite(ma20[i]) or closes[i] <= ma20[i] * (1 + rally_tol_pct / 100)
        )
        if bearish_turn and still_downtrend:
            out[i] = True

    return pd.Series(out, index=df.index)


def generate_uptrend_breakdown_signals(
    df: pd.DataFrame,
    *,
    swing_window: int = 5,
    lookback: int = 120,
) -> pd.Series:
    """
    連線近期兩個遞升波段低點形成上升趨勢線，收盤向下跌破時作空。
    """
    n = len(df)
    out = np.zeros(n, dtype=bool)
    if n < swing_window * 2 + 10:
        return pd.Series(out, index=df.index)

    lows = df["Low"].to_numpy(dtype=float)
    closes = df["Close"].to_numpy(dtype=float)
    _, swing_low_idx = find_swing_indices(df["High"].to_numpy(dtype=float), lows, window=swing_window)
    confirm_lag = swing_window

    for i in range(swing_window * 2 + 2, n):
        start = max(0, i - lookback)
        confirmed_upto = i - confirm_lag
        candidates = [idx for idx in swing_low_idx if start <= idx <= confirmed_upto]
        if len(candidates) < 2:
            continue

        recent = candidates[-2:]
        idx1, idx2 = recent[0], recent[1]
        p1, p2 = float(lows[idx1]), float(lows[idx2])
        if p2 <= p1 or idx2 <= idx1:
            continue

        line_prev = _trendline_value(idx1, p1, idx2, p2, i - 1)
        line_now = _trendline_value(idx1, p1, idx2, p2, i)
        if closes[i] < line_now and closes[i - 1] >= line_prev:
            out[i] = True

    return pd.Series(out, index=df.index)
