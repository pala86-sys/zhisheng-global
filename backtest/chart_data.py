"""K 線圖資料序列化"""

from __future__ import annotations

import pandas as pd


def _num(value) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    return round(float(value), 4)


def _date_str(idx) -> str:
    return idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)[:10]


def serialize_chart_bars(
    df: pd.DataFrame,
    *,
    max_bars: int = 1500,
    marker_dates: list[str] | None = None,
) -> list[dict]:
    if df is None or df.empty:
        return []

    work = df
    if marker_dates:
        marker_set = set(marker_dates)
        hit_indices = [
            i for i, idx in enumerate(df.index) if _date_str(idx) in marker_set
        ]
        if hit_indices:
            start = max(0, min(hit_indices) - 30)
            work = df.iloc[start:]

    tail = work.tail(max_bars)
    rows: list[dict] = []
    for idx, row in tail.iterrows():
        item = {
            "date": _date_str(idx),
            "open": _num(row.get("Open")),
            "high": _num(row.get("High")),
            "low": _num(row.get("Low")),
            "close": _num(row.get("Close")),
            "volume": _num(row.get("Volume")),
            "MA5": _num(row.get("MA5")),
            "MA10": _num(row.get("MA10")),
            "MA20": _num(row.get("MA20")),
            "MA60": _num(row.get("MA60")),
        }
        if "Foreign_Net" in row.index:
            item["foreign_net"] = _int(row.get("Foreign_Net"))
            item["trust_net"] = _int(row.get("Trust_Net"))
            item["total_net"] = _int(row.get("Total_Net"))
        rows.append(item)
    return rows


def _int(value) -> int:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return 0
    return int(value)


def _close_by_date(df: pd.DataFrame) -> dict[str, float]:
    if df is None or df.empty:
        return {}
    out: dict[str, float] = {}
    for idx, row in df.iterrows():
        close = _num(row.get("Close"))
        if close is None:
            continue
        out[_date_str(idx)] = close
    return out


def serialize_markers(trades: list, *, side: str, close_by_date: dict[str, float] | None = None) -> list[dict]:
    close_by_date = close_by_date or {}
    return [
        {
            "entry_date": t.entry_date,
            "exit_date": t.exit_date,
            "entry_price": t.entry_price,
            "exit_price": t.exit_price,
            "exit_close": close_by_date.get(t.exit_date),
            "side": side,
            "is_win": t.is_win,
            "return_pct": t.return_pct,
            "exit_reason": getattr(t, "exit_reason", ""),
        }
        for t in trades
    ]


def _marker_dates(markers: list[dict]) -> list[str]:
    dates: list[str] = []
    for m in markers:
        if m.get("entry_date"):
            dates.append(m["entry_date"])
        if m.get("exit_date"):
            dates.append(m["exit_date"])
    return dates


def _compute_default_days(bars: list[dict], markers: list[dict]) -> int:
    """預設顯示範圍需涵蓋所有訊號日期"""
    if not bars:
        return 90
    if not markers:
        return min(120, len(bars))

    marker_set = set(_marker_dates(markers))
    indices = [i for i, b in enumerate(bars) if b["date"] in marker_set]
    if not indices:
        return len(bars)

    first = min(indices)
    days_needed = len(bars) - first + 20
    return min(len(bars), max(120, days_needed))


def build_chart_payload(
    df: pd.DataFrame,
    trades: list,
    *,
    side: str,
    category: str,
    max_bars: int = 1500,
) -> dict:
    markers = serialize_markers(trades, side=side, close_by_date=_close_by_date(df))
    marker_dates = _marker_dates(markers)
    bars = serialize_chart_bars(df, max_bars=max_bars, marker_dates=marker_dates)
    default_days = _compute_default_days(bars, markers)
    return {
        "bars": bars,
        "markers": markers,
        "show_chips": category == "chips",
        "default_days": default_days,
    }
