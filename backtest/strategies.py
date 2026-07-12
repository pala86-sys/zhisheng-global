"""策略定義與訊號產生（技術面 + 籌碼面，作多 + 作空）"""

from __future__ import annotations

from dataclasses import dataclass

from backtest.candles import (
    generate_bearish_engulfing_signals,
    generate_bearish_harami_signals,
    generate_bullish_engulfing_signals,
    generate_bullish_harami_signals,
    generate_dragonfly_doji_signals,
    generate_evening_star_signals,
    generate_gravestone_doji_signals,
    generate_hammer_signals,
    generate_hanging_man_signals,
    generate_inverted_hammer_signals,
    generate_morning_star_signals,
    generate_shooting_star_signals,
)
from backtest.structure import (
    generate_downtrend_breakout_signals,
    generate_hh_hl_pullback_signals,
    generate_ll_lh_rally_signals,
    generate_uptrend_breakdown_signals,
)

import pandas as pd


@dataclass(frozen=True)
class StrategyDef:
    id: str
    name: str
    description: str
    side: str  # buy | sell
    category: str  # technical | chips
    params: dict


STRATEGIES: dict[str, StrategyDef] = {
    # ── 技術面 · 作多 ──
    "golden_cross": StrategyDef(
        id="golden_cross", name="均線黃金交叉（MA20×MA60）", side="buy", category="technical",
        description="20 日均線（月線）向上穿越 60 日均線（季線）時作多",
        params={"short_ma": 20, "long_ma": 60},
    ),
    "ma_pullback_5": StrategyDef(
        id="ma_pullback_5", name="均線回踩 MA5", side="buy", category="technical",
        description="股價回落至 5 日均線附近（±1.5%）後轉強時作多",
        params={"ma_days": 5, "tolerance_pct": 1.5},
    ),
    "ma_pullback_10": StrategyDef(
        id="ma_pullback_10", name="均線回踩 MA10", side="buy", category="technical",
        description="股價回落至 10 日均線附近（±1.5%）後轉強時作多",
        params={"ma_days": 10, "tolerance_pct": 1.5},
    ),
    "ma_pullback_20": StrategyDef(
        id="ma_pullback_20", name="均線回踩 MA20", side="buy", category="technical",
        description="股價回落至 20 日均線（月線）附近（±1.5%）後轉強時作多",
        params={"ma_days": 20, "tolerance_pct": 1.5},
    ),
    "ma_pullback_60": StrategyDef(
        id="ma_pullback_60", name="均線回踩 MA60", side="buy", category="technical",
        description="股價回落至 60 日均線（季線）附近（±1.5%）後轉強時作多",
        params={"ma_days": 60, "tolerance_pct": 1.5},
    ),
    "macd_above_zero": StrategyDef(
        id="macd_above_zero", name="MACD 0 軸之上", side="buy", category="technical",
        description="DIF 向上穿越 0 軸時作多",
        params={},
    ),
    "kd_golden_cross": StrategyDef(
        id="kd_golden_cross", name="KD 黃金交叉（K×D）", side="buy", category="technical",
        description="K 線向上穿越 D 線時作多",
        params={},
    ),
    "kd_oversold": StrategyDef(
        id="kd_oversold", name="KD 超賣反彈", side="buy", category="technical",
        description="K 值低於 20 且 K 向上穿越 D 時作多",
        params={"oversold": 20},
    ),
    "hammer_line": StrategyDef(
        id="hammer_line", name="錘子線", side="buy", category="technical",
        description="下跌趨勢中出現長下影錘子線，多方反攻訊號",
        params={},
    ),
    "inverted_hammer": StrategyDef(
        id="inverted_hammer", name="倒錘線", side="buy", category="technical",
        description="下跌趨勢中出現長上影倒錘，可能止跌反彈",
        params={},
    ),
    "dragonfly_doji": StrategyDef(
        id="dragonfly_doji", name="蜻蜓十字", side="buy", category="technical",
        description="低檔出現下影極長、實體極小的蜻蜓十字，止跌參考",
        params={},
    ),
    "morning_star": StrategyDef(
        id="morning_star", name="晨星", side="buy", category="technical",
        description="長黑 → 小實體 → 長紅的三根 K 棒反轉組合",
        params={},
    ),
    "bullish_harami": StrategyDef(
        id="bullish_harami", name="多方孕線", side="buy", category="technical",
        description="前日長黑後，當日小紅完全孕育於前日實體內",
        params={},
    ),
    "bullish_engulfing": StrategyDef(
        id="bullish_engulfing", name="長紅吞噬", side="buy", category="technical",
        description="陽線實體完全吞噬前一根陰線實體時作多",
        params={},
    ),
    "breakout_20": StrategyDef(
        id="breakout_20", name="20 日突破", side="buy", category="technical",
        description="收盤價突破「前 20 日最高價」（非月線 MA20）；需創新高才觸發",
        params={"lookback": 20},
    ),
    "volume_surge": StrategyDef(
        id="volume_surge", name="放量長紅", side="buy", category="technical",
        description="長紅 K 棒且成交量達 20 日均量 1.8 倍以上時作多",
        params={"vol_mult": 1.8},
    ),
    "hh_hl_pullback": StrategyDef(
        id="hh_hl_pullback", name="頭頭高底底高回檔", side="buy", category="technical",
        description="上升結構（頭頭高、底底高）確立後，回測前波低點或月線支撐轉強時作多",
        params={"swing_window": 5, "pullback_tol_pct": 2.0, "max_swing_age": 80},
    ),
    "downtrend_breakout": StrategyDef(
        id="downtrend_breakout", name="突破下降趨勢線", side="buy", category="technical",
        description="連線近期遞降波段高點形成下降趨勢線，收盤向上突破時作多",
        params={"swing_window": 5, "lookback": 120},
    ),
    # ── 技術面 · 作空 ──
    "death_cross": StrategyDef(
        id="death_cross", name="均線死亡交叉（MA20×MA60）", side="sell", category="technical",
        description="20 日均線（月線）向下穿越 60 日均線（季線）時作空",
        params={"short_ma": 20, "long_ma": 60},
    ),
    "ma_rejection": StrategyDef(
        id="ma_rejection", name="均線壓力", side="sell", category="technical",
        description="股價反彈至均線附近（±容許範圍）後回落時作空",
        params={"ma_days": 20, "tolerance_pct": 1.5},
    ),
    "macd_below_zero": StrategyDef(
        id="macd_below_zero", name="MACD 0 軸之下", side="sell", category="technical",
        description="DIF 向下穿越 0 軸時作空",
        params={},
    ),
    "kd_death_cross": StrategyDef(
        id="kd_death_cross", name="KD 死亡交叉（K×D）", side="sell", category="technical",
        description="K 線向下穿越 D 線時作空",
        params={},
    ),
    "kd_overbought": StrategyDef(
        id="kd_overbought", name="KD 超買回落", side="sell", category="technical",
        description="K 值高於 80 且 K 向下穿越 D 時作空",
        params={"overbought": 80},
    ),
    "shooting_star": StrategyDef(
        id="shooting_star", name="射擊之星", side="sell", category="technical",
        description="上漲趨勢中出現長上影射擊之星，高檔賣壓浮現",
        params={},
    ),
    "hanging_man": StrategyDef(
        id="hanging_man", name="吊人線", side="sell", category="technical",
        description="上漲趨勢中出現錘子型吊人線，留意回檔風險",
        params={},
    ),
    "gravestone_doji": StrategyDef(
        id="gravestone_doji", name="墓碑十字", side="sell", category="technical",
        description="高檔出現上影極長、實體極小的墓碑十字，轉弱參考",
        params={},
    ),
    "evening_star": StrategyDef(
        id="evening_star", name="暮星", side="sell", category="technical",
        description="長紅 → 小實體 → 長黑的三根 K 棒反轉組合",
        params={},
    ),
    "bearish_harami": StrategyDef(
        id="bearish_harami", name="空方孕線", side="sell", category="technical",
        description="前日長紅後，當日小黑完全孕育於前日實體內",
        params={},
    ),
    "bearish_engulfing": StrategyDef(
        id="bearish_engulfing", name="長黑吞噬", side="sell", category="technical",
        description="陰線實體完全吞噬前一根陽線實體時作空",
        params={},
    ),
    "breakdown_20": StrategyDef(
        id="breakdown_20", name="20 日跌破", side="sell", category="technical",
        description="收盤價跌破前 20 日最低價時作空",
        params={"lookback": 20},
    ),
    "volume_surge_bear": StrategyDef(
        id="volume_surge_bear", name="放量長黑", side="sell", category="technical",
        description="長黑 K 棒且成交量達 20 日均量 1.8 倍以上時作空",
        params={"vol_mult": 1.8},
    ),
    "ll_lh_rally": StrategyDef(
        id="ll_lh_rally", name="頭頭低底底低反彈", side="sell", category="technical",
        description="下降結構（頭頭低、底底低）確立後，反彈至前波高點或月線壓力轉弱時作空",
        params={"swing_window": 5, "rally_tol_pct": 2.0, "max_swing_age": 80},
    ),
    "uptrend_breakdown": StrategyDef(
        id="uptrend_breakdown", name="跌破上升趨勢線", side="sell", category="technical",
        description="連線近期遞升波段低點形成上升趨勢線，收盤向下跌破時作空",
        params={"swing_window": 5, "lookback": 120},
    ),
    # ── 籌碼面 · 作多 ──
    "foreign_buy_streak": StrategyDef(
        id="foreign_buy_streak", name="外資連續買超", side="buy", category="chips",
        description="外資連續 N 日買超時作多",
        params={"days": 3},
    ),
    "trust_buy_streak": StrategyDef(
        id="trust_buy_streak", name="投信連續買超", side="buy", category="chips",
        description="投信連續 N 日買超時作多",
        params={"days": 3},
    ),
    "institutional_buy_streak": StrategyDef(
        id="institutional_buy_streak", name="法人合計連續買超", side="buy", category="chips",
        description="三大法人合計連續 N 日買超時作多",
        params={"days": 3},
    ),
    "foreign_trust_buy": StrategyDef(
        id="foreign_trust_buy", name="外資投信同步買超", side="buy", category="chips",
        description="外資與投信同日皆買超時作多",
        params={},
    ),
    "foreign_large_buy": StrategyDef(
        id="foreign_large_buy", name="外資大量買超", side="buy", category="chips",
        description="外資單日買超超過近 5 日平均的 2 倍時作多",
        params={"mult": 2.0, "avg_days": 5},
    ),
    # ── 籌碼面 · 作空 ──
    "foreign_sell_streak": StrategyDef(
        id="foreign_sell_streak", name="外資連續賣超", side="sell", category="chips",
        description="外資連續 N 日賣超時作空",
        params={"days": 3},
    ),
    "trust_sell_streak": StrategyDef(
        id="trust_sell_streak", name="投信連續賣超", side="sell", category="chips",
        description="投信連續 N 日賣超時作空",
        params={"days": 3},
    ),
    "institutional_sell_streak": StrategyDef(
        id="institutional_sell_streak", name="法人合計連續賣超", side="sell", category="chips",
        description="三大法人合計連續 N 日賣超時作空",
        params={"days": 3},
    ),
    "foreign_trust_sell": StrategyDef(
        id="foreign_trust_sell", name="外資投信同步賣超", side="sell", category="chips",
        description="外資與投信同日皆賣超時作空",
        params={},
    ),
    "foreign_large_sell": StrategyDef(
        id="foreign_large_sell", name="外資大量賣超", side="sell", category="chips",
        description="外資單日賣超超過近 5 日平均絕對值的 2 倍時作空",
        params={"mult": 2.0, "avg_days": 5},
    ),
}

from backtest.ma_pair import build_ma_pair_strategy_defs

STRATEGIES.update(build_ma_pair_strategy_defs())

CATEGORY_LABELS = {"technical": "技術面", "chips": "籌碼面", "composite": "複合", "ma_pair": "均線配對"}
SIDE_LABELS = {"buy": "作多", "sell": "作空"}


@dataclass(frozen=True)
class CompositeStrategy:
    """多策略 AND 複合條件"""

    id: str
    name: str
    description: str
    side: str
    category: str
    strategy_ids: tuple[str, ...]


def build_composite_strategy(strategy_ids: list[str]) -> CompositeStrategy | tuple[None, str]:
    """組合多個策略為複合條件（須同方向）"""
    ids = [s for s in dict.fromkeys(strategy_ids) if s]
    if len(ids) < 2:
        return None, "複合條件至少需選擇 2 個策略"

    defs = []
    side = None
    for sid in ids:
        if sid not in STRATEGIES:
            return None, f"未知策略: {sid}"
        sdef = STRATEGIES[sid]
        if side is None:
            side = sdef.side
        elif sdef.side != side:
            return None, "複合條件內的策略方向須一致（皆作多或皆作空）"
        defs.append(sdef)

    name = " + ".join(d.name for d in defs)
    description = "；".join(f"{d.name}：{d.description}" for d in defs)
    has_chips = any(d.category == "chips" for d in defs)
    category = "composite" if len({d.category for d in defs}) > 1 else defs[0].category

    return CompositeStrategy(
        id="composite:" + "+".join(ids),
        name=name,
        description=description,
        side=side or "buy",
        category=category,
        strategy_ids=tuple(ids),
    ), ""


def needs_chips_data(strategy_ids: list[str]) -> bool:
    return any(STRATEGIES[sid].category == "chips" for sid in strategy_ids if sid in STRATEGIES)


def generate_combined_signals(df: pd.DataFrame, strategy_ids: list[str]) -> pd.Series:
    """多策略訊號 AND 合併"""
    if df.empty or not strategy_ids:
        return pd.Series(dtype=bool)

    combined: pd.Series | None = None
    for sid in strategy_ids:
        part = generate_signals(df, sid)
        combined = part if combined is None else (combined & part)
    return combined.fillna(False) if combined is not None else pd.Series(False, index=df.index)


def list_strategies(*, side: str | None = None, category: str | None = None) -> list[dict]:
    items = []
    for s in STRATEGIES.values():
        if side and s.side != side:
            continue
        if category and s.category != category:
            continue
        items.append({
            "id": s.id,
            "name": s.name,
            "description": s.description,
            "side": s.side,
            "side_label": SIDE_LABELS[s.side],
            "category": s.category,
            "category_label": CATEGORY_LABELS[s.category],
            "params": s.params,
        })
    return items


def _consecutive_streak(series: pd.Series, *, positive: bool, days: int) -> pd.Series:
    """連續 N 日買超（positive=True）或賣超（positive=False）"""
    if positive:
        mask = series > 0
    else:
        mask = series < 0
    streak = mask.astype(int).groupby((~mask).cumsum()).cumsum()
    return streak >= days


def generate_signals(df: pd.DataFrame, strategy_id: str, *, params: dict | None = None) -> pd.Series:
    if df.empty:
        return pd.Series(dtype=bool)

    if strategy_id not in STRATEGIES:
        raise ValueError(f"未知策略: {strategy_id}")

    p = {**STRATEGIES[strategy_id].params, **(params or {})}
    out = pd.Series(False, index=df.index)

    # ── 技術面作多 ──
    if strategy_id == "golden_cross":
        s, l = int(p["short_ma"]), int(p["long_ma"])
        ma_s, ma_l = df[f"MA{s}"], df[f"MA{l}"]
        out = (ma_s.shift(1) <= ma_l.shift(1)) & (ma_s > ma_l)

    elif strategy_id in ("ma_pullback_5", "ma_pullback_10", "ma_pullback_20", "ma_pullback_60"):
        days = int(p["ma_days"])
        tol = float(p["tolerance_pct"]) / 100.0
        ma, close = df[f"MA{days}"], df["Close"]
        out = (close >= ma * (1 - tol)) & (close <= ma * (1 + tol)) & (close > ma.shift(1))

    elif strategy_id == "macd_above_zero":
        dif = df["MACD"]
        out = (dif.shift(1) <= 0) & (dif > 0)

    elif strategy_id == "kd_golden_cross":
        k, d = df["K"], df["D"]
        out = (k.shift(1) <= d.shift(1)) & (k > d)

    elif strategy_id == "kd_oversold":
        threshold = float(p["oversold"])
        k, d = df["K"], df["D"]
        out = (k.shift(1) < threshold) & (k.shift(1) <= d.shift(1)) & (k > d)

    elif strategy_id == "hammer_line":
        out = generate_hammer_signals(df)

    elif strategy_id == "inverted_hammer":
        out = generate_inverted_hammer_signals(df)

    elif strategy_id == "dragonfly_doji":
        out = generate_dragonfly_doji_signals(df)

    elif strategy_id == "morning_star":
        out = generate_morning_star_signals(df)

    elif strategy_id == "bullish_harami":
        out = generate_bullish_harami_signals(df)

    elif strategy_id == "bullish_engulfing":
        out = generate_bullish_engulfing_signals(df)

    elif strategy_id == "breakout_20":
        lookback = int(p.get("lookback", 20))
        out = df["Close"] > df["High"].rolling(lookback).max().shift(1)

    elif strategy_id == "volume_surge":
        mult = float(p.get("vol_mult", 1.8))
        out = (df["Close"] > df["Open"]) & (df["Volume"] >= df["VOL_MA20"] * mult)

    elif strategy_id == "hh_hl_pullback":
        out = generate_hh_hl_pullback_signals(
            df,
            swing_window=int(p.get("swing_window", 5)),
            pullback_tol_pct=float(p.get("pullback_tol_pct", 2.0)),
            max_swing_age=int(p.get("max_swing_age", 80)),
        )

    elif strategy_id == "downtrend_breakout":
        out = generate_downtrend_breakout_signals(
            df,
            swing_window=int(p.get("swing_window", 5)),
            lookback=int(p.get("lookback", 120)),
        )

    # ── 技術面作空 ──
    elif strategy_id == "death_cross":
        s, l = int(p["short_ma"]), int(p["long_ma"])
        ma_s, ma_l = df[f"MA{s}"], df[f"MA{l}"]
        out = (ma_s.shift(1) >= ma_l.shift(1)) & (ma_s < ma_l)

    elif strategy_id == "ma_rejection":
        days = int(p["ma_days"])
        tol = float(p["tolerance_pct"]) / 100.0
        ma, close = df[f"MA{days}"], df["Close"]
        near_ma = (close >= ma * (1 - tol)) & (close <= ma * (1 + tol))
        out = near_ma & (close < close.shift(1)) & (close.shift(1) >= ma.shift(1))

    elif strategy_id == "macd_below_zero":
        dif = df["MACD"]
        out = (dif.shift(1) >= 0) & (dif < 0)

    elif strategy_id == "kd_death_cross":
        k, d = df["K"], df["D"]
        out = (k.shift(1) >= d.shift(1)) & (k < d)

    elif strategy_id == "kd_overbought":
        threshold = float(p["overbought"])
        k, d = df["K"], df["D"]
        out = (k.shift(1) > threshold) & (k.shift(1) >= d.shift(1)) & (k < d)

    elif strategy_id == "shooting_star":
        out = generate_shooting_star_signals(df)

    elif strategy_id == "hanging_man":
        out = generate_hanging_man_signals(df)

    elif strategy_id == "gravestone_doji":
        out = generate_gravestone_doji_signals(df)

    elif strategy_id == "evening_star":
        out = generate_evening_star_signals(df)

    elif strategy_id == "bearish_harami":
        out = generate_bearish_harami_signals(df)

    elif strategy_id == "bearish_engulfing":
        out = generate_bearish_engulfing_signals(df)

    elif strategy_id == "breakdown_20":
        lookback = int(p.get("lookback", 20))
        out = df["Close"] < df["Low"].rolling(lookback).min().shift(1)

    elif strategy_id == "volume_surge_bear":
        mult = float(p.get("vol_mult", 1.8))
        out = (df["Close"] < df["Open"]) & (df["Volume"] >= df["VOL_MA20"] * mult)

    elif strategy_id == "ll_lh_rally":
        out = generate_ll_lh_rally_signals(
            df,
            swing_window=int(p.get("swing_window", 5)),
            rally_tol_pct=float(p.get("rally_tol_pct", 2.0)),
            max_swing_age=int(p.get("max_swing_age", 80)),
        )

    elif strategy_id == "uptrend_breakdown":
        out = generate_uptrend_breakdown_signals(
            df,
            swing_window=int(p.get("swing_window", 5)),
            lookback=int(p.get("lookback", 120)),
        )

    # ── 籌碼面 ──
    elif strategy_id == "foreign_buy_streak":
        days = int(p["days"])
        out = _consecutive_streak(df["Foreign_Net"], positive=True, days=days)

    elif strategy_id == "trust_buy_streak":
        days = int(p["days"])
        out = _consecutive_streak(df["Trust_Net"], positive=True, days=days)

    elif strategy_id == "institutional_buy_streak":
        days = int(p["days"])
        out = _consecutive_streak(df["Total_Net"], positive=True, days=days)

    elif strategy_id == "foreign_trust_buy":
        out = (df["Foreign_Net"] > 0) & (df["Trust_Net"] > 0)

    elif strategy_id == "foreign_large_buy":
        mult, avg_days = float(p["mult"]), int(p["avg_days"])
        avg = df["Foreign_Net"].clip(lower=0).rolling(avg_days).mean()
        out = (df["Foreign_Net"] > 0) & (df["Foreign_Net"] >= avg * mult)

    elif strategy_id == "foreign_sell_streak":
        days = int(p["days"])
        out = _consecutive_streak(df["Foreign_Net"], positive=False, days=days)

    elif strategy_id == "trust_sell_streak":
        days = int(p["days"])
        out = _consecutive_streak(df["Trust_Net"], positive=False, days=days)

    elif strategy_id == "institutional_sell_streak":
        days = int(p["days"])
        out = _consecutive_streak(df["Total_Net"], positive=False, days=days)

    elif strategy_id == "foreign_trust_sell":
        out = (df["Foreign_Net"] < 0) & (df["Trust_Net"] < 0)

    elif strategy_id == "foreign_large_sell":
        mult, avg_days = float(p["mult"]), int(p["avg_days"])
        avg = df["Foreign_Net"].clip(upper=0).abs().rolling(avg_days).mean()
        out = (df["Foreign_Net"] < 0) & (df["Foreign_Net"].abs() >= avg * mult)

    else:
        raise ValueError(f"未知策略: {strategy_id}")

    return out.fillna(False)
