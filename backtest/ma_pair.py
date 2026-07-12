"""均線配對策略：指定均線買入／賣出（或作空／回補）"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

MA_LINES = (5, 10, 20, 60)
DEFAULT_TOLERANCE_PCT = 1.5
DEFAULT_VOL_MULT = 1.5
RECOVERY_WINDOW_DAYS = 5
DEFAULT_MIN_REENTRY_DAYS = 1

ENTRY_TOUCH = "touch_ma"
ENTRY_VOLUME = "volume_break_ma"
EXIT_TOUCH = "touch_ma"
EXIT_VOLUME = "volume_break_ma"


@dataclass
class MaPairTrade:
    entry_date: str
    entry_price: float
    exit_date: str
    exit_price: float
    return_pct: float
    is_win: bool
    exit_reason: str


def ma_pair_strategy_id(side: str, entry_ma: int, exit_ma: int) -> str:
    return f"ma_pair_{side}_{entry_ma}_{exit_ma}"


def parse_ma_pair_id(strategy_id: str) -> tuple[str, int, int] | None:
    if not strategy_id.startswith("ma_pair_"):
        return None
    parts = strategy_id.split("_")
    if len(parts) != 5:
        return None
    side = parts[2]
    if side not in ("buy", "sell"):
        return None
    try:
        entry_ma, exit_ma = int(parts[3]), int(parts[4])
    except ValueError:
        return None
    if entry_ma not in MA_LINES or exit_ma not in MA_LINES or entry_ma == exit_ma:
        return None
    return side, entry_ma, exit_ma


def is_ma_pair_id(strategy_id: str) -> bool:
    return parse_ma_pair_id(strategy_id) is not None


def _ma_col(days: int) -> str:
    return f"MA{days}"


def _volume_surge(df: pd.DataFrame, *, vol_mult: float = DEFAULT_VOL_MULT) -> pd.Series:
    vol_ma = df["VOL_MA20"] if "VOL_MA20" in df.columns else df["Volume"].rolling(20).mean()
    return (df["Volume"] >= vol_ma * vol_mult).fillna(False)


def generate_touch_entry_signals(
    df: pd.DataFrame,
    entry_ma: int,
    *,
    side: str,
    tolerance_pct: float = DEFAULT_TOLERANCE_PCT,
) -> pd.Series:
    """觸及均線：日內碰線且收盤守住在均線附近"""
    tol = tolerance_pct / 100.0
    ma = df[_ma_col(entry_ma)]
    low, high, close = df["Low"], df["High"], df["Close"]
    band_lo = ma * (1 - tol)
    band_hi = ma * (1 + tol)
    if side == "buy":
        touched = (low <= band_hi) & (low >= band_lo * (1 - tol))
        hold = close >= band_lo
        return (touched & hold).fillna(False)
    touched = (high >= band_lo) & (high <= band_hi * (1 + tol))
    hold = close <= band_hi
    return (touched & hold).fillna(False)


def generate_volume_entry_signals(
    df: pd.DataFrame,
    entry_ma: int,
    *,
    side: str,
    vol_mult: float = DEFAULT_VOL_MULT,
) -> pd.Series:
    """帶量站上／跌破均線"""
    ma = df[_ma_col(entry_ma)]
    close = df["Close"]
    surge = _volume_surge(df, vol_mult=vol_mult)
    if side == "buy":
        cross = (close > ma) & (close.shift(1) <= ma.shift(1))
    else:
        cross = (close < ma) & (close.shift(1) >= ma.shift(1))
    return (surge & cross).fillna(False)


def generate_touch_exit_signals(
    df: pd.DataFrame,
    exit_ma: int,
    *,
    tolerance_pct: float = DEFAULT_TOLERANCE_PCT,
) -> pd.Series:
    """觸及賣出／回補均線（收盤在均線 ± 容許範圍）"""
    tol = tolerance_pct / 100.0
    ma = df[_ma_col(exit_ma)]
    close = df["Close"]
    return ((close >= ma * (1 - tol)) & (close <= ma * (1 + tol))).fillna(False)


def generate_volume_exit_signals(
    df: pd.DataFrame,
    exit_ma: int,
    *,
    side: str,
    vol_mult: float = DEFAULT_VOL_MULT,
) -> pd.Series:
    """帶量跌破／站上均線出場"""
    ma = df[_ma_col(exit_ma)]
    close = df["Close"]
    surge = _volume_surge(df, vol_mult=vol_mult)
    if side == "buy":
        cross = (close < ma) & (close.shift(1) >= ma.shift(1))
    else:
        cross = (close > ma) & (close.shift(1) <= ma.shift(1))
    return (surge & cross).fillna(False)


def generate_ma_pair_entry_signals(
    df: pd.DataFrame,
    entry_ma: int,
    *,
    side: str,
    entry_mode: str = ENTRY_TOUCH,
    tolerance_pct: float = DEFAULT_TOLERANCE_PCT,
    vol_mult: float = DEFAULT_VOL_MULT,
) -> pd.Series:
    if entry_mode == ENTRY_VOLUME:
        return generate_volume_entry_signals(df, entry_ma, side=side, vol_mult=vol_mult)
    return generate_touch_entry_signals(df, entry_ma, side=side, tolerance_pct=tolerance_pct)


def generate_ma_pair_exit_signals(
    df: pd.DataFrame,
    exit_ma: int,
    *,
    side: str,
    exit_mode: str = EXIT_TOUCH,
    tolerance_pct: float = DEFAULT_TOLERANCE_PCT,
    vol_mult: float = DEFAULT_VOL_MULT,
) -> pd.Series:
    if exit_mode == EXIT_VOLUME:
        return generate_volume_exit_signals(df, exit_ma, side=side, vol_mult=vol_mult)
    return generate_touch_exit_signals(df, exit_ma, tolerance_pct=tolerance_pct)


def _entry_exit_labels(
    entry_ma: int,
    exit_ma: int,
    *,
    side: str,
    entry_mode: str,
    exit_mode: str,
) -> tuple[str, str]:
    if side == "buy":
        entry = (
            f"觸及 MA{entry_ma}"
            if entry_mode == ENTRY_TOUCH
            else f"帶量站上 MA{entry_ma}"
        )
        exit_label = (
            f"觸及 MA{exit_ma}"
            if exit_mode == EXIT_TOUCH
            else f"帶量跌破 MA{exit_ma}"
        )
    else:
        entry = (
            f"觸及 MA{entry_ma}"
            if entry_mode == ENTRY_TOUCH
            else f"帶量跌破 MA{entry_ma}"
        )
        exit_label = (
            f"觸及 MA{exit_ma}"
            if exit_mode == EXIT_TOUCH
            else f"帶量站上 MA{exit_ma}"
        )
    return entry, exit_label


def _is_soft_exit(reason: str) -> bool:
    return reason not in ("觸及停損", "持有期滿")


def recovery_reentry_at(
    df: pd.DataFrame,
    idx: int,
    reclaim_ma: int,
    *,
    side: str,
) -> bool:
    """假跌破／假突破後，收盤重新站回均線"""
    if idx <= 0 or reclaim_ma not in MA_LINES:
        return False
    ma = df[_ma_col(reclaim_ma)]
    close = df["Close"]
    if side == "buy":
        return bool((close.iloc[idx] > ma.iloc[idx]) and (close.iloc[idx - 1] <= ma.iloc[idx - 1]))
    return bool((close.iloc[idx] < ma.iloc[idx]) and (close.iloc[idx - 1] >= ma.iloc[idx - 1]))


def simulate_ma_pair_trades(
    df: pd.DataFrame,
    entry_ma: int,
    exit_ma: int,
    *,
    side: str,
    entry_mode: str = ENTRY_TOUCH,
    exit_mode: str = EXIT_TOUCH,
    tolerance_pct: float = DEFAULT_TOLERANCE_PCT,
    vol_mult: float = DEFAULT_VOL_MULT,
    max_hold_days: int = 120,
    min_gap_days: int = DEFAULT_MIN_REENTRY_DAYS,
    stop_pct: float = 3.0,
    recovery_window_days: int = RECOVERY_WINDOW_DAYS,
) -> list[MaPairTrade]:
    if df.empty or entry_ma == exit_ma:
        return []

    entries = generate_ma_pair_entry_signals(
        df,
        entry_ma,
        side=side,
        entry_mode=entry_mode,
        tolerance_pct=tolerance_pct,
        vol_mult=vol_mult,
    )
    exits = generate_ma_pair_exit_signals(
        df,
        exit_ma,
        side=side,
        exit_mode=exit_mode,
        tolerance_pct=tolerance_pct,
        vol_mult=vol_mult,
    )
    _, exit_label = _entry_exit_labels(
        entry_ma, exit_ma, side=side, entry_mode=entry_mode, exit_mode=exit_mode
    )
    is_buy = side == "buy"
    trades: list[MaPairTrade] = []
    last_exit_idx = -min_gap_days - 1
    last_exit_soft = False
    i = 0
    n = len(df)

    while i < n:
        days_since_exit = i - last_exit_idx
        recovery = (
            last_exit_soft
            and 0 < days_since_exit <= recovery_window_days
            and recovery_reentry_at(df, i, exit_ma, side=side)
        )
        normal_entry = bool(entries.iloc[i])

        if recovery:
            pass
        elif not normal_entry:
            i += 1
            continue
        elif days_since_exit < min_gap_days:
            i += 1
            continue

        entry_idx = i
        entry_price = float(df.iloc[entry_idx]["Close"])
        if entry_price <= 0:
            i += 1
            continue

        stop_price = entry_price * (1 - stop_pct / 100) if is_buy else entry_price * (1 + stop_pct / 100)

        end_idx = min(entry_idx + max_hold_days, n - 1)
        exit_idx = end_idx
        exit_price = float(df.iloc[end_idx]["Close"])
        exit_reason = "持有期滿"
        is_win = (exit_price < entry_price) if not is_buy else (exit_price > entry_price)

        for j in range(entry_idx + 1, end_idx + 1):
            row = df.iloc[j]
            low = float(row["Low"])
            high = float(row["High"])
            close = float(row["Close"])

            hit_stop = (low <= stop_price) if is_buy else (high >= stop_price)
            if hit_stop:
                exit_idx = j
                exit_price = stop_price
                exit_reason = "觸及停損"
                is_win = False
                break

            if bool(exits.iloc[j]):
                exit_idx = j
                exit_price = close
                exit_reason = exit_label
                is_win = (exit_price < entry_price) if not is_buy else (exit_price > entry_price)
                break

        ret = (
            (exit_price / entry_price - 1) * 100
            if is_buy
            else (entry_price / exit_price - 1) * 100
        )

        trades.append(
            MaPairTrade(
                entry_date=str(df.index[entry_idx].date()),
                entry_price=round(entry_price, 2),
                exit_date=str(df.index[exit_idx].date()),
                exit_price=round(exit_price, 2),
                return_pct=round(ret, 2),
                is_win=is_win,
                exit_reason=("站回再進 · " if recovery else "") + exit_reason,
            )
        )
        last_exit_idx = exit_idx
        last_exit_soft = _is_soft_exit(exit_reason)
        i = exit_idx + 1

    return trades


def ma_pair_trade_to_result(t: MaPairTrade):
    from backtest.engine import TradeResult

    return TradeResult(
        entry_date=t.entry_date,
        entry_price=t.entry_price,
        exit_date=t.exit_date,
        exit_price=t.exit_price,
        return_pct=t.return_pct,
        is_win=t.is_win,
        exit_reason=t.exit_reason,
    )


def _pair_display_name(
    entry_ma: int,
    exit_ma: int,
    *,
    side: str,
    entry_mode: str,
    exit_mode: str,
) -> str:
    entry, exit_label = _entry_exit_labels(
        entry_ma, exit_ma, side=side, entry_mode=entry_mode, exit_mode=exit_mode
    )
    return f"{entry} → {exit_label}"


def scan_ma_pairs(
    df: pd.DataFrame,
    *,
    side: str,
    max_hold_days: int = 120,
    stop_pct: float = 3.0,
    min_gap_days: int = 5,
    entry_mode: str = ENTRY_TOUCH,
    exit_mode: str = EXIT_TOUCH,
) -> list[dict]:
    from backtest.engine import _summarize_trades

    rows: list[dict] = []
    pairs = [
        (entry, exit_ma)
        for entry in MA_LINES
        for exit_ma in MA_LINES
        if entry != exit_ma
    ]

    for entry, exit_ma in pairs:
        trades = simulate_ma_pair_trades(
            df,
            entry,
            exit_ma,
            side=side,
            entry_mode=entry_mode,
            exit_mode=exit_mode,
            max_hold_days=max_hold_days,
            stop_pct=stop_pct,
            min_gap_days=min_gap_days,
        )
        summary = _summarize_trades([ma_pair_trade_to_result(t) for t in trades])
        rows.append(
            {
                "strategy_id": ma_pair_strategy_id(side, entry, exit_ma),
                "entry_ma": entry,
                "exit_ma": exit_ma,
                "entry_mode": entry_mode,
                "exit_mode": exit_mode,
                "name": _pair_display_name(
                    entry, exit_ma, side=side, entry_mode=entry_mode, exit_mode=exit_mode
                ),
                "summary": summary,
            }
        )
    rows.sort(
        key=lambda r: (
            r["summary"]["avg_return_pct"] if r["summary"]["total_signals"] else -999,
            r["summary"]["win_rate"],
        ),
        reverse=True,
    )
    return rows


def build_ma_pair_strategy_defs() -> dict:
    from backtest.strategies import StrategyDef

    defs: dict = {}
    for side in ("buy", "sell"):
        for entry in MA_LINES:
            for exit_ma in MA_LINES:
                if entry == exit_ma:
                    continue
                sid = ma_pair_strategy_id(side, entry, exit_ma)
                if side == "buy":
                    name = f"均線配對 MA{entry}→MA{exit_ma}"
                    desc = (
                        f"作多：觸及或帶量站上 MA{entry} 進場，"
                        f"觸及或帶量跌破 MA{exit_ma} 出場"
                    )
                else:
                    name = f"均線配對 MA{entry}→MA{exit_ma}"
                    desc = (
                        f"作空：觸及或帶量跌破 MA{entry} 進場，"
                        f"觸及或帶量站上 MA{exit_ma} 回補"
                    )
                defs[sid] = StrategyDef(
                    id=sid,
                    name=name,
                    description=desc,
                    side=side,
                    category="ma_pair",
                    params={
                        "entry_ma": entry,
                        "exit_ma": exit_ma,
                        "tolerance_pct": DEFAULT_TOLERANCE_PCT,
                    },
                )
    return defs
