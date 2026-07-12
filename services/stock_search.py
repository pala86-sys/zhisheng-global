"""台股代號 / 名稱搜尋"""

import json
import re
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
BUNDLED_STOCK_LIST = DATA_DIR / "stock_list.json"
MARKET_LABEL = {"twse": "上市", "tpex": "上櫃"}


def load_bundled_stock_list() -> list[dict]:
    if not BUNDLED_STOCK_LIST.exists():
        return []
    try:
        payload = json.loads(BUNDLED_STOCK_LIST.read_text(encoding="utf-8"))
        return payload.get("stocks") or []
    except Exception:
        return []


def lookup_stock(stock_id: str) -> dict | None:
    code = str(stock_id or "").strip().upper()
    if "." in code:
        code = code.split(".", 1)[0]
    if not code:
        return None
    for stock in load_bundled_stock_list():
        if stock.get("stock_id") == code:
            return stock
    return None


def search_stocks(query: str, *, limit: int = 12) -> list[dict]:
    q = (query or "").strip()
    if not q:
        return []

    stocks = load_bundled_stock_list()
    results: list[dict] = []
    q_upper = q.upper()

    for stock in stocks:
        stock_id = str(stock.get("stock_id", ""))
        stock_name = str(stock.get("stock_name", ""))
        market = stock.get("market", "twse")
        label = MARKET_LABEL.get(market, market)

        if q_upper in stock_id.upper() or q in stock_name:
            results.append({
                "stock_id": stock_id,
                "stock_name": stock_name,
                "market": market,
                "market_label": label,
                "display": f"{stock_id} {stock_name}（{label}）",
            })
        if len(results) >= limit:
            break

    return results


def resolve_tw_symbol(raw: str) -> tuple[str, str | None]:
    """解析輸入為 Yahoo 代碼與純數字股號。支援 2330、2330.TW、台積電 等。"""
    text = (raw or "").strip().upper()
    if not text:
        return "", None

    if re.fullmatch(r"\d{4,6}(\.(TW|TWO))?", text):
        if "." in text:
            return text, text.split(".", 1)[0]
        return f"{text}.TW", text

    if re.fullmatch(r"\d{4,6}", text):
        return f"{text}.TW", text

    stocks = load_bundled_stock_list()
    for stock in stocks:
        name = str(stock.get("stock_name", ""))
        stock_id = str(stock.get("stock_id", ""))
        market = stock.get("market", "twse")
        suffix = ".TWO" if market == "tpex" else ".TW"
        if text == name or text in name:
            return f"{stock_id}{suffix}", stock_id

    return text, None
