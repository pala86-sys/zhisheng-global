"""FinMind API 請求（Token、節流、避免 4xx 重試）"""

import os
import time

import requests

from services.http_client import get_http_session

FINMIND_API = "https://api.finmindtrade.com/api/v4/data"
_LAST_REQUEST_AT = 0.0
_MIN_INTERVAL = 0.4
_MIN_INTERVAL_WITH_TOKEN = 0.12
_quota_exhausted = False


class FinMindApiError(RuntimeError):
    def __init__(self, message: str, *, status: int | None = None, http_status: int | None = None):
        super().__init__(message)
        self.status = status
        self.http_status = http_status


def finmind_quota_exhausted() -> bool:
    return _quota_exhausted


def finmind_token() -> str:
    return os.environ.get("FINMIND_TOKEN", "").strip()


def finmind_headers() -> dict[str, str]:
    token = finmind_token()
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


def _throttle() -> None:
    global _LAST_REQUEST_AT
    interval = _MIN_INTERVAL_WITH_TOKEN if finmind_token() else _MIN_INTERVAL
    now = time.monotonic()
    wait = interval - (now - _LAST_REQUEST_AT)
    if wait > 0:
        time.sleep(wait)
    _LAST_REQUEST_AT = time.monotonic()


def _parse_finmind_response(response: requests.Response) -> list | None:
    global _quota_exhausted

    http_status = response.status_code
    try:
        payload = response.json()
    except ValueError:
        payload = {}

    api_status = payload.get("status")
    msg = str(payload.get("msg") or f"HTTP {http_status}")

    if http_status in (401, 402, 403) or api_status in (401, 402, 403):
        if http_status in (402, 403) or api_status in (402, 403):
            _quota_exhausted = True
        raise FinMindApiError(
            msg,
            status=api_status if isinstance(api_status, int) else None,
            http_status=http_status,
        )

    response.raise_for_status()

    if api_status != 200:
        raise FinMindApiError(
            msg,
            status=api_status if isinstance(api_status, int) else None,
            http_status=http_status,
        )

    return payload.get("data") or None


def _request_once(params: dict, *, timeout: int) -> list | None:
    if _quota_exhausted:
        raise FinMindApiError("FinMind 配額用盡或 IP 暫封", status=402)

    _throttle()
    session = get_http_session()
    response = session.get(
        FINMIND_API,
        params=params,
        headers=finmind_headers(),
        timeout=timeout,
    )
    return _parse_finmind_response(response)


def request_finmind(stock_code: str, dataset: str, extra_params: dict) -> list | None:
    params = {"dataset": dataset, "data_id": stock_code, **extra_params}
    last_error: Exception | None = None

    for attempt in range(3):
        try:
            return _request_once(params, timeout=30)
        except FinMindApiError:
            raise
        except requests.RequestException as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(1.5 ** attempt)

    assert last_error is not None
    raise last_error
