"""關鍵 K 棒型態訊號"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _parts(df: pd.DataFrame) -> tuple[pd.Series, ...]:
    o, c, h, l = df["Open"], df["Close"], df["High"], df["Low"]
    body_top = np.maximum(o, c)
    body_bottom = np.minimum(o, c)
    body = body_top - body_bottom
    rng = h - l
    upper = h - body_top
    lower = body_bottom - l
    return body, rng, upper, lower, body_top, body_bottom, o, c


def _avg_body(df: pd.DataFrame) -> pd.Series:
    return (df["Close"] - df["Open"]).abs().rolling(20, min_periods=5).mean()


def _effective_body(body: pd.Series, avg_body: pd.Series, rng: pd.Series) -> pd.Series:
    body_ref = avg_body.fillna(rng * 0.15)
    min_body = np.maximum(body_ref * 0.08, rng * 0.03)
    return np.maximum(body, min_body)


def _uptrend(df: pd.DataFrame) -> pd.Series:
    close = df["Close"]
    ma20 = df["MA20"] if "MA20" in df.columns else close
    up = close >= close.shift(5) * 1.01
    if "MA20" in df.columns:
        up = up & (close > ma20)
    return up.fillna(False)


def _downtrend(df: pd.DataFrame) -> pd.Series:
    close = df["Close"]
    ma20 = df["MA20"] if "MA20" in df.columns else close
    down = close <= close.shift(5) * 0.99
    if "MA20" in df.columns:
        down = down & (close < ma20)
    return down.fillna(False)


def _hammer_shape(df: pd.DataFrame) -> pd.Series:
    body, rng, upper, lower, _, _, _, _ = _parts(df)
    eff = _effective_body(body, _avg_body(df), rng)
    return (rng > 0) & (lower >= eff * 2) & (upper <= eff * 0.7)


def _shooting_star_shape(df: pd.DataFrame) -> pd.Series:
    body, rng, upper, lower, _, _, _, _ = _parts(df)
    eff = _effective_body(body, _avg_body(df), rng)
    return (rng > 0) & (upper >= eff * 2) & (lower <= eff * 0.7)


def _is_doji(df: pd.DataFrame) -> pd.Series:
    body, rng, _, _, _, _, _, _ = _parts(df)
    ab = _avg_body(df)
    body_ref = ab.fillna(rng * 0.15)
    return body <= np.maximum(body_ref * 0.12, rng * 0.08)


def generate_hammer_signals(df: pd.DataFrame) -> pd.Series:
    """錘子線：下跌趨勢中長下影，多方反攻"""
    return _hammer_shape(df) & _downtrend(df)


def generate_inverted_hammer_signals(df: pd.DataFrame) -> pd.Series:
    """倒錘線：下跌趨勢中長上影，可能止跌"""
    return _shooting_star_shape(df) & _downtrend(df)


def generate_dragonfly_doji_signals(df: pd.DataFrame) -> pd.Series:
    """蜻蜓十字：下影長、實體極小，低檔止跌參考"""
    body, rng, upper, lower, _, _, _, _ = _parts(df)
    doji = _is_doji(df)
    shape = (lower >= rng * 0.55) & (upper <= rng * 0.15)
    return doji & shape & (_downtrend(df) | (df["Close"] <= df["Close"].shift(5)))


def generate_morning_star_signals(df: pd.DataFrame) -> pd.Series:
    """晨星：長黑 → 小實體 → 長紅反彈"""
    o, c = df["Open"], df["Close"]
    body, rng, _, _, _, _, _, _ = _parts(df)
    ab = _avg_body(df).fillna(body)

    prev_bear = c.shift(2) < o.shift(2)
    prev_long = body.shift(2) >= ab.shift(2) * 1.0
    star_small = body.shift(1) <= ab.shift(1) * 0.5
    curr_bull = c > o
    curr_long = body >= ab * 1.0
    recover = c >= (o.shift(2) + c.shift(2)) / 2

    out = prev_bear & prev_long & star_small & curr_bull & curr_long & recover
    return out.fillna(False)


def generate_bullish_harami_signals(df: pd.DataFrame) -> pd.Series:
    """多方孕線：前日長黑，當日小紅完全含於前日實體內"""
    o, c = df["Open"], df["Close"]
    body, _, _, _, body_top, body_bottom, _, _ = _parts(df)
    ab = _avg_body(df).fillna(body)

    prev_bear = c.shift(1) < o.shift(1)
    prev_long = body.shift(1) >= ab.shift(1) * 1.0
    curr_bull = c > o
    curr_small = body <= body.shift(1) * 0.6
    inside = (body_top <= body_top.shift(1)) & (body_bottom >= body_bottom.shift(1))

    return (prev_bear & prev_long & curr_bull & curr_small & inside).fillna(False)


def generate_bullish_engulfing_signals(df: pd.DataFrame) -> pd.Series:
    """長紅吞噬：陽線實體完全吞噬前一根陰線實體"""
    o, c = df["Open"], df["Close"]
    body, _, _, _, body_top, body_bottom, _, _ = _parts(df)
    prev_o, prev_c = o.shift(1), c.shift(1)
    prev_body_top = np.maximum(prev_o, prev_c)
    prev_body_bottom = np.minimum(prev_o, prev_c)

    is_green = c > o
    prev_red = prev_c < prev_o
    engulf = (body_top >= prev_body_top) & (body_bottom <= prev_body_bottom)
    return (is_green & prev_red & engulf & (body > body.shift(1))).fillna(False)


def generate_shooting_star_signals(df: pd.DataFrame) -> pd.Series:
    """射擊之星：上漲趨勢中長上影，高檔賣壓"""
    return _shooting_star_shape(df) & _uptrend(df)


def generate_hanging_man_signals(df: pd.DataFrame) -> pd.Series:
    """吊人線：上漲趨勢中錘子型態，留意回檔"""
    return _hammer_shape(df) & _uptrend(df)


def generate_gravestone_doji_signals(df: pd.DataFrame) -> pd.Series:
    """墓碑十字：上影長、實體極小，高檔轉弱參考"""
    body, rng, upper, lower, _, _, _, _ = _parts(df)
    doji = _is_doji(df)
    shape = (upper >= rng * 0.55) & (lower <= rng * 0.15)
    return doji & shape & (_uptrend(df) | (df["Close"] >= df["Close"].shift(5)))


def generate_evening_star_signals(df: pd.DataFrame) -> pd.Series:
    """暮星：長紅 → 小實體 → 長黑回落"""
    o, c = df["Open"], df["Close"]
    body, rng, _, _, _, _, _, _ = _parts(df)
    ab = _avg_body(df).fillna(body)

    prev_bull = c.shift(2) > o.shift(2)
    prev_long = body.shift(2) >= ab.shift(2) * 1.0
    star_small = body.shift(1) <= ab.shift(1) * 0.5
    curr_bear = c < o
    curr_long = body >= ab * 1.0
    drop = c <= (o.shift(2) + c.shift(2)) / 2

    out = prev_bull & prev_long & star_small & curr_bear & curr_long & drop
    return out.fillna(False)


def generate_bearish_harami_signals(df: pd.DataFrame) -> pd.Series:
    """空方孕線：前日長紅，當日小黑完全含於前日實體內"""
    o, c = df["Open"], df["Close"]
    body, _, _, _, body_top, body_bottom, _, _ = _parts(df)
    ab = _avg_body(df).fillna(body)

    prev_bull = c.shift(1) > o.shift(1)
    prev_long = body.shift(1) >= ab.shift(1) * 1.0
    curr_bear = c < o
    curr_small = body <= body.shift(1) * 0.6
    inside = (body_top <= body_top.shift(1)) & (body_bottom >= body_bottom.shift(1))

    return (prev_bull & prev_long & curr_bear & curr_small & inside).fillna(False)


def generate_bearish_engulfing_signals(df: pd.DataFrame) -> pd.Series:
    """長黑吞噬：陰線實體完全吞噬前一根陽線實體"""
    o, c = df["Open"], df["Close"]
    body, _, _, _, body_top, body_bottom, _, _ = _parts(df)
    prev_o, prev_c = o.shift(1), c.shift(1)
    prev_body_top = np.maximum(prev_o, prev_c)
    prev_body_bottom = np.minimum(prev_o, prev_c)

    is_red = c < o
    prev_green = prev_c > prev_o
    engulf = (body_top >= prev_body_top) & (body_bottom <= prev_body_bottom)
    return (is_red & prev_green & engulf & (body > body.shift(1))).fillna(False)
