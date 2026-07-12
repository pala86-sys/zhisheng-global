"""三大法人籌碼資料抓取與合併"""

from __future__ import annotations

import json
import ssl
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

import pandas as pd

from services.finmind_client import finmind_quota_exhausted, request_finmind
from services.stock_search import resolve_tw_symbol

_YAHOO_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
FINMIND_API = "https://api.finmindtrade.com/api/v4/data"


def _foreign_net(daily: dict[str, int]) -> int:
    return daily.get("Foreign_Investor", 0) + daily.get("Foreign_Dealer_Self", 0)


def _trust_net(daily: dict[str, int]) -> int:
    return daily.get("Investment_Trust", 0)


def _dealer_net(daily: dict[str, int]) -> int:
    return daily.get("Dealer_self", 0) + daily.get("Dealer_Hedging", 0)


def _fetch_chips_urllib(stock_code: str, *, start: str, end: str) -> list | None:
    params = {
        "dataset": "TaiwanStockInstitutionalInvestorsBuySell",
        "data_id": stock_code,
        "start_date": start,
        "end_date": end,
    }
    url = f"{FINMIND_API}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": _YAHOO_UA})
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=60) as resp:
            payload = json.loads(resp.read().decode())
        if payload.get("status") != 200:
            return None
        return payload.get("data") or []
    except Exception:
        return None


def _fetch_chips_requests(stock_code: str, *, start: str, end: str) -> list | None:
    if finmind_quota_exhausted():
        return None
    try:
        return request_finmind(
            stock_code,
            "TaiwanStockInstitutionalInvestorsBuySell",
            {"start_date": start, "end_date": end},
        )
    except Exception:
        return None


def fetch_institutional_data(stock_code: str, *, start: str, end: str) -> pd.DataFrame:
    """將 FinMind 三大法人資料轉為每日買賣超 DataFrame（單位：張）"""
    raw = _fetch_chips_urllib(stock_code, start=start, end=end)
    if not raw:
        raw = _fetch_chips_requests(stock_code, start=start, end=end)
    if not raw:
        return pd.DataFrame()

    by_date: dict[str, dict[str, int]] = {}
    for item in raw:
        date = item.get("date")
        name = item.get("name")
        if not date or not name:
            continue
        buy = int(item.get("buy") or 0)
        sell = int(item.get("sell") or 0)
        by_date.setdefault(date, {})[name] = buy - sell

    if not by_date:
        return pd.DataFrame()

    rows = []
    for date in sorted(by_date.keys()):
        daily = by_date[date]
        foreign = _foreign_net(daily) // 1000
        trust = _trust_net(daily) // 1000
        dealer = _dealer_net(daily) // 1000
        total = foreign + trust + dealer
        rows.append({
            "date": pd.to_datetime(date),
            "Foreign_Net": foreign,
            "Trust_Net": trust,
            "Dealer_Net": dealer,
            "Total_Net": total,
        })

    df = pd.DataFrame(rows).set_index("date").sort_index()
    return df


def merge_chips_with_prices(price_df: pd.DataFrame, chips_df: pd.DataFrame) -> pd.DataFrame:
    """將籌碼欄位合併至價格 DataFrame（以交易日對齊）"""
    if price_df.empty or chips_df.empty:
        return price_df
    out = price_df.copy()
    out.index = pd.to_datetime(out.index).normalize()
    chips = chips_df.copy()
    chips.index = pd.to_datetime(chips.index).normalize()
    merged = out.join(chips, how="left")
    for col in ("Foreign_Net", "Trust_Net", "Dealer_Net", "Total_Net"):
        if col in merged.columns:
            merged[col] = merged[col].fillna(0).astype(int)
    return merged


def fetch_chips_for_symbol(symbol_input: str, *, years: int) -> tuple[pd.DataFrame, dict]:
    _, stock_code = resolve_tw_symbol(symbol_input)
    if not stock_code:
        return pd.DataFrame(), {"ok": False, "msg": "籌碼策略需要有效的台股代號"}

    end_dt = datetime.now()
    start_dt = end_dt - timedelta(days=int(years) * 365 + 30)
    start_str = start_dt.strftime("%Y-%m-%d")
    end_str = end_dt.strftime("%Y-%m-%d")

    df = fetch_institutional_data(stock_code, start=start_str, end=end_str)
    if df.empty:
        return pd.DataFrame(), {
            "ok": False,
            "msg": "無法取得三大法人籌碼資料，請稍後再試",
        }

    return df, {
        "ok": True,
        "source": "FinMind 籌碼",
        "bars": len(df),
        "start": str(df.index.min().date()),
        "end": str(df.index.max().date()),
    }
