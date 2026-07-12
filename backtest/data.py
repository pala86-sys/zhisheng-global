"""台股歷史價格抓取"""

from __future__ import annotations

import json
import ssl
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

import pandas as pd

from services.finmind_client import FinMindApiError, finmind_quota_exhausted, request_finmind
from services.stock_search import lookup_stock, resolve_tw_symbol

_YAHOO_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def finmind_price_to_history(raw: list | None) -> pd.DataFrame:
    if not raw:
        return pd.DataFrame()
    df = pd.DataFrame(raw)
    if df.empty or "date" not in df.columns:
        return pd.DataFrame()

    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").drop_duplicates("date", keep="last").set_index("date")
    rename = {
        "open": "Open",
        "max": "High",
        "min": "Low",
        "close": "Close",
        "Trading_Volume": "Volume",
    }
    for src, dst in rename.items():
        if src in df.columns:
            df[dst] = pd.to_numeric(df[src], errors="coerce")
    needed = ["Open", "High", "Low", "Close", "Volume"]
    if not all(col in df.columns for col in needed):
        return pd.DataFrame()
    return df[needed].dropna(how="any")


def _finmind_history(stock_code: str, *, start: str, end: str) -> pd.DataFrame:
    if finmind_quota_exhausted():
        return pd.DataFrame()
    try:
        raw = request_finmind(
            stock_code,
            "TaiwanStockPrice",
            {"start_date": start, "end_date": end},
        )
        return finmind_price_to_history(raw)
    except Exception:
        return pd.DataFrame()


def _yahoo_chart_history(symbol: str, *, start: str, end: str) -> pd.DataFrame:
    """Yahoo Chart API（stdlib），避開 yfinance SSL 問題"""
    sym = urllib.parse.quote(str(symbol or "").strip())
    if not sym:
        return pd.DataFrame()

    start_dt = datetime.strptime(start, "%Y-%m-%d")
    end_dt = datetime.strptime(end, "%Y-%m-%d")
    p1 = int(start_dt.timestamp())
    p2 = int(end_dt.timestamp()) + 86400

    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
        f"?period1={p1}&period2={p2}&interval=1d"
    )
    req = urllib.request.Request(url, headers={"User-Agent": _YAHOO_UA})
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            data = json.loads(resp.read().decode())
    except Exception:
        return pd.DataFrame()

    result = (data.get("chart") or {}).get("result") or []
    if not result:
        return pd.DataFrame()

    timestamps = result[0].get("timestamp") or []
    quotes = (result[0].get("indicators") or {}).get("quote") or []
    if not timestamps or not quotes:
        return pd.DataFrame()

    q = quotes[0]
    rows = []
    for i, ts in enumerate(timestamps):
        o, h, l, c, v = q["open"][i], q["high"][i], q["low"][i], q["close"][i], q["volume"][i]
        if None in (o, h, l, c):
            continue
        rows.append({
            "date": pd.Timestamp(ts, unit="s"),
            "Open": float(o),
            "High": float(h),
            "Low": float(l),
            "Close": float(c),
            "Volume": float(v or 0),
        })

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows).set_index("date").sort_index()
    return df[["Open", "High", "Low", "Close", "Volume"]]


def _yf_history(symbol: str, *, start: str, end: str) -> pd.DataFrame:
    try:
        import yfinance as yf

        t = yf.Ticker(symbol)
        df = t.history(start=start, end=end, auto_adjust=False)
        if df is None or df.empty:
            return pd.DataFrame()
        out = df.copy()
        out.index = pd.to_datetime(out.index)
        for col in ["Open", "High", "Low", "Close", "Volume"]:
            if col in out.columns:
                out[col] = pd.to_numeric(out[col], errors="coerce")
        return out[["Open", "High", "Low", "Close", "Volume"]].dropna(
            subset=["Open", "High", "Low", "Close"]
        )
    except Exception:
        return pd.DataFrame()


def fetch_ohlcv(
    symbol_input: str,
    *,
    years: int = 3,
) -> tuple[pd.DataFrame, dict]:
    """
    抓取台股 OHLCV。優先 FinMind，其次 Yahoo Chart API，最後 yfinance。
    回傳 (DataFrame, meta)
    """
    yahoo_symbol, stock_code = resolve_tw_symbol(symbol_input)
    if not yahoo_symbol:
        return pd.DataFrame(), {"ok": False, "msg": "請輸入有效的台股代號或名稱"}

    end_dt = datetime.now()
    start_dt = end_dt - timedelta(days=int(years) * 365 + 30)
    start_str = start_dt.strftime("%Y-%m-%d")
    end_str = end_dt.strftime("%Y-%m-%d")

    df = pd.DataFrame()
    source = ""

    df = _yahoo_chart_history(yahoo_symbol, start=start_str, end=end_str)
    if not df.empty:
        source = "Yahoo Chart API"

    if df.empty and stock_code:
        alt = f"{stock_code}.TWO" if yahoo_symbol.endswith(".TW") else f"{stock_code}.TW"
        df = _yahoo_chart_history(alt, start=start_str, end=end_str)
        if not df.empty:
            yahoo_symbol = alt
            source = "Yahoo Chart API"

    if df.empty and stock_code:
        df = _finmind_history(stock_code, start=start_str, end=end_str)
        if not df.empty:
            source = "FinMind"

    if df.empty:
        df = _yf_history(yahoo_symbol, start=start_str, end=end_str)
        if not df.empty:
            source = "Yahoo Finance"

    if df.empty and stock_code:
        alt = f"{stock_code}.TWO" if yahoo_symbol.endswith(".TW") else f"{stock_code}.TW"
        df = _yf_history(alt, start=start_str, end=end_str)
        if not df.empty:
            yahoo_symbol = alt
            source = "Yahoo Finance"

    if df.empty:
        return pd.DataFrame(), {
            "ok": False,
            "msg": f"無法取得 {symbol_input} 的歷史資料，請確認代號是否正確",
        }

    info = lookup_stock(stock_code or symbol_input) if stock_code else lookup_stock(symbol_input)
    stock_name = info.get("stock_name") if info else None
    market = info.get("market") if info else ("tpex" if yahoo_symbol.endswith(".TWO") else "twse")

    return df, {
        "ok": True,
        "symbol": yahoo_symbol,
        "stock_code": stock_code or yahoo_symbol.split(".", 1)[0],
        "stock_name": stock_name,
        "market": market,
        "source": source,
        "bars": len(df),
        "start": str(df.index.min().date()),
        "end": str(df.index.max().date()),
    }
