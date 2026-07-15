"""台股策略回測 API 伺服器"""

import logging
import traceback
from pathlib import Path

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, model_validator

log = logging.getLogger(__name__)

from backtest.engine import run_backtest, run_ma_pair_scan
from backtest.optimize import run_optimize
from backtest.strategies import CATEGORY_LABELS, SIDE_LABELS, list_strategies
from services.seed_list import add_seed_email, list_seed_emails
from services.stock_search import search_stocks

ROOT = Path(__file__).resolve().parent
WEB_DIR = ROOT / "web"

app = FastAPI(title="智勝全球 · 策略回測", version="1.0.0")

_seed_hits: dict[str, list[float]] = {}


def _client_ip(request: Request) -> str:
    forwarded = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    if forwarded:
        return forwarded
    if request.client:
        return request.client.host or "unknown"
    return "unknown"


def _seed_rate_limited(ip: str, *, limit: int = 8, window_sec: float = 3600) -> bool:
    import time

    now = time.monotonic()
    hits = [t for t in _seed_hits.get(ip, []) if now - t < window_sec]
    if len(hits) >= limit:
        _seed_hits[ip] = hits
        return True
    hits.append(now)
    _seed_hits[ip] = hits
    return False


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request: Request, exc: RequestValidationError):
    detail = exc.errors()[0].get("msg", "請求參數不正確") if exc.errors() else "請求參數不正確"
    return JSONResponse(status_code=422, content={"ok": False, "msg": detail})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    log.error("Unhandled error on %s\n%s", request.url.path, traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={"ok": False, "msg": "伺服器處理請求時發生錯誤，請稍後再試或聯絡管理員"},
    )


class BacktestRequest(BaseModel):
    symbol: str = Field(..., description="台股代號，如 2330")
    strategy_id: str | None = Field(None, description="單一策略 ID")
    strategy_ids: list[str] | None = Field(None, description="複合策略 ID 列表（AND）")
    years: int = Field(3, ge=1, le=10)
    holding_days: int = Field(20, ge=1, le=120)
    target_pct: float = Field(5.0, ge=0.1, le=50)
    stop_pct: float = Field(3.0, ge=0.1, le=30)
    exit_mode: str | None = Field(None, description="均線配對出場：touch_ma 或 volume_break_ma")
    entry_mode: str | None = Field(None, description="均線配對進場：touch_ma 或 volume_break_ma")

    @model_validator(mode="after")
    def check_strategy(self):
        if self.strategy_ids:
            if len(self.strategy_ids) < 2:
                raise ValueError("複合條件至少需選擇 2 個策略")
            return self
        if not self.strategy_id:
            raise ValueError("請選擇策略或複合條件")
        return self


@app.get("/api/health")
def health():
    return {"ok": True}


class SeedSignupRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=254, description="種子用戶 Email")


@app.post("/api/seed-signup")
def api_seed_signup(req: SeedSignupRequest, request: Request):
    if _seed_rate_limited(_client_ip(request)):
        return {"ok": False, "msg": "提交過於頻繁，請稍後再試"}
    try:
        return add_seed_email(req.email, source="landing")
    except Exception as exc:
        log.error("Seed signup failed\n%s", traceback.format_exc())
        return {"ok": False, "msg": f"無法加入名單：{exc}"}


@app.get("/api/seed-list")
def api_seed_list(token: str = Query("", description="SEED_ADMIN_TOKEN")):
    import os

    expected = (os.environ.get("SEED_ADMIN_TOKEN") or "").strip()
    if not expected or token != expected:
        return JSONResponse(status_code=401, content={"ok": False, "msg": "未授權"})
    rows = list_seed_emails()
    return {"ok": True, "count": len(rows), "emails": rows}


@app.get("/api/strategies")
def get_strategies(
    side: str | None = Query(None, description="buy 或 sell"),
    category: str | None = Query(None, description="technical 或 chips"),
):
    return {
        "strategies": list_strategies(side=side, category=category),
        "sides": [{"id": k, "label": v} for k, v in SIDE_LABELS.items()],
        "categories": [{"id": k, "label": v} for k, v in CATEGORY_LABELS.items()],
    }


@app.get("/api/search")
def api_search(q: str = Query("", max_length=40)):
    return {"results": search_stocks(q)}


class MaPairScanRequest(BaseModel):
    symbol: str = Field(..., description="台股代號，如 2330")
    side: str = Field("buy", description="buy（作多）或 sell（作空）")
    years: int = Field(3, ge=1, le=10)
    max_hold_days: int = Field(120, ge=1, le=240)
    stop_pct: float = Field(3.0, ge=0.1, le=30)
    exit_mode: str = Field("touch_ma", description="touch_ma 或 volume_break_ma")
    entry_mode: str = Field("touch_ma", description="touch_ma 或 volume_break_ma")


@app.post("/api/ma-pair-scan")
def api_ma_pair_scan(req: MaPairScanRequest):
    if req.side not in ("buy", "sell"):
        return {"ok": False, "msg": "策略方向須為 buy 或 sell"}
    return run_ma_pair_scan(
        req.symbol,
        side=req.side,
        years=req.years,
        max_hold_days=req.max_hold_days,
        stop_pct=req.stop_pct,
        exit_mode=req.exit_mode,
        entry_mode=req.entry_mode,
    )


@app.post("/api/backtest")
def api_backtest(req: BacktestRequest):
    try:
        return run_backtest(
            req.symbol,
            req.strategy_id,
            strategy_ids=req.strategy_ids,
            years=req.years,
            holding_days=req.holding_days,
            target_pct=req.target_pct,
            stop_pct=req.stop_pct,
            exit_mode=req.exit_mode,
            entry_mode=req.entry_mode,
        )
    except Exception as exc:
        log.error("Backtest failed for %s\n%s", req.symbol, traceback.format_exc())
        return {"ok": False, "msg": f"回測計算失敗：{exc}"}


class OptimizeRequest(BaseModel):
    symbol: str = Field(..., description="台股代號，如 2330")
    side: str = Field("buy", description="buy（作多）或 sell（作空）")
    years: int = Field(3, ge=1, le=10)
    holding_days: int = Field(20, ge=1, le=120)
    target_pct: float = Field(5.0, ge=0.1, le=50)
    stop_pct: float = Field(3.0, ge=0.1, le=30)
    min_signals: int = Field(3, ge=1, le=30)
    top_n: int = Field(10, ge=1, le=30)
    include_composites: bool = Field(True, description="是否掃描技術面+籌碼面複合條件")
    compare_strategy_id: str | None = Field(None, description="與目前單一策略比較")
    compare_strategy_ids: list[str] | None = Field(None, description="與目前複合策略比較")


@app.post("/api/optimize")
def api_optimize(req: OptimizeRequest):
    if req.side not in ("buy", "sell"):
        return {"ok": False, "msg": "策略方向須為 buy 或 sell"}
    try:
        return run_optimize(
            req.symbol,
            side=req.side,
            years=req.years,
            holding_days=req.holding_days,
            target_pct=req.target_pct,
            stop_pct=req.stop_pct,
            min_signals=req.min_signals,
            top_n=req.top_n,
            include_composites=req.include_composites,
            compare_strategy_id=req.compare_strategy_id,
            compare_strategy_ids=req.compare_strategy_ids,
        )
    except Exception as exc:
        log.error("Optimize failed for %s\n%s", req.symbol, traceback.format_exc())
        return {"ok": False, "msg": f"最佳化計算失敗：{exc}"}


@app.get("/")
def landing():
    return FileResponse(WEB_DIR / "landing.html")


@app.get("/backtest")
def backtest_app():
    return FileResponse(WEB_DIR / "backtest.html")


app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")
