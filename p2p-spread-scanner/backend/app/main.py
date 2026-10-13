from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from datetime import datetime, timezone
from typing import Literal

import httpx
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="P2P Spread Scanner API", version="0.2.0")

# Local development only; replace with your deployed Mini App origin in production.
allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in allowed_origins if origin.strip()],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)

BYBIT_BASE_URL = os.getenv("BYBIT_BASE_URL", "https://api.bybit.com").rstrip("/")
BYBIT_API_KEY = os.getenv("BYBIT_API_KEY", "").strip()
BYBIT_API_SECRET = os.getenv("BYBIT_API_SECRET", "").strip()
BYBIT_RECV_WINDOW = os.getenv("BYBIT_RECV_WINDOW", "5000")
# Payment method IDs are account/market dependent. Populate from the official API
# response for the payment method(s) you intend to allow. Empty means no bank-only
# guarantee, so the API returns a warning and the UI must say so.
BYBIT_BANK_PAYMENT_IDS = {
    item.strip() for item in os.getenv("BYBIT_BANK_PAYMENT_IDS", "").split(",") if item.strip()
}
REQUEST_TIMEOUT = float(os.getenv("BYBIT_REQUEST_TIMEOUT_SECONDS", "12"))

class Opportunity(BaseModel):
    id: str
    asset: str
    fiat: str
    buy_exchange: str
    sell_exchange: str
    buy_price: float
    sell_price: float
    buy_ad_min_fiat: float
    buy_ad_max_fiat: float
    sell_ad_min_fiat: float
    sell_ad_max_fiat: float
    buy_payment_methods: list[str]
    sell_payment_methods: list[str]
    buy_advertiser_completion_pct: float | None = None
    sell_advertiser_completion_pct: float | None = None
    buy_advertiser_recent_orders: int | None = None
    sell_advertiser_recent_orders: int | None = None
    remaining_crypto: float
    source_updated_at: str
    source_mode: Literal["live"] = "live"

class ScanResponse(BaseModel):
    mode: Literal["live", "unavailable"]
    updated_at: str
    opportunities: list[Opportunity]
    message: str
    warnings: list[str] = []

class ApiUnavailable(Exception):
    pass

def _sign(timestamp: str, body: str) -> str:
    """Bybit V5 signature: timestamp + apiKey + recvWindow + JSON body."""
    payload = timestamp + BYBIT_API_KEY + BYBIT_RECV_WINDOW + body
    return hmac.new(
        BYBIT_API_SECRET.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

async def fetch_bybit_ads(token_id: str, currency_id: str, side: int) -> list[dict]:
    if not BYBIT_API_KEY or not BYBIT_API_SECRET:
        raise ApiUnavailable(
            "Не настроены BYBIT_API_KEY и BYBIT_API_SECRET. "
            "Для официального P2P API Bybit требуется API-ключ и статус General Advertiser или выше."
        )

    body_obj = {
        "tokenId": token_id,
        "currencyId": currency_id,
        "side": str(side),
        "page": "1",
        "size": "100",
    }
    body = json.dumps(body_obj, separators=(",", ":"), ensure_ascii=False)
    timestamp = str(int(time.time() * 1000))
    headers = {
        "X-BAPI-API-KEY": BYBIT_API_KEY,
        "X-BAPI-TIMESTAMP": timestamp,
        "X-BAPI-RECV-WINDOW": BYBIT_RECV_WINDOW,
        "X-BAPI-SIGN": _sign(timestamp, body),
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        try:
            response = await client.post(
                f"{BYBIT_BASE_URL}/v5/p2p/item/online",
                content=body.encode("utf-8"),
                headers=headers,
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ApiUnavailable(f"Bybit API недоступен: {type(exc).__name__}") from exc

    if payload.get("ret_code") != 0:
        # Do not leak headers, signatures, or credentials in error messages.
        code = payload.get("ret_code", "unknown")
        msg = str(payload.get("ret_msg", "API error"))[:160]
        raise ApiUnavailable(f"Bybit API отклонил запрос (код {code}): {msg}")

    return payload.get("result", {}).get("items", []) or []

def _num(value, default=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default

def _completion(ad: dict) -> float | None:
    value = ad.get("recentExecuteRate")
    if value in (None, ""):
        return None
    parsed = _num(value, -1)
    if parsed < 0:
        return None
    # The API has historically returned this as a percentage-like value; preserve
    # the supplied numeric scale and do not fabricate a rate when it is absent.
    return parsed

def _payment_ids(ad: dict) -> set[str]:
    return {str(value) for value in (ad.get("payments") or [])}

def _normalise_ad(ad: dict) -> dict:
    return {
        "id": str(ad.get("id", "")),
        "price": _num(ad.get("price")),
        "min": _num(ad.get("minAmount")),
        "max": _num(ad.get("maxAmount")),
        "qty": _num(ad.get("lastQuantity")),
        "payments": _payment_ids(ad),
        "completion": _completion(ad),
        "recent_orders": int(_num(ad.get("recentOrderNum"), 0)),
        "online": ad.get("isOnline") is True,
    }

@app.get("/api/health")
def health():
    configured = bool(BYBIT_API_KEY and BYBIT_API_SECRET)
    return {
        "status": "ok",
        "provider": "Bybit P2P official API",
        "credentials_configured": configured,
        "advertiser_access_note": "Bybit P2P API requires General Advertiser status or above.",
    }

@app.get("/api/opportunities", response_model=ScanResponse)
async def opportunities(
    asset: str = Query("USDT", pattern="^(USDT|BTC)$"),
    fiat: str = Query("RUB", pattern="^RUB$"),
    capital: float = Query(50000, gt=0, le=100000000),
):
    now = datetime.now(timezone.utc).isoformat()
    warnings: list[str] = []
    if not BYBIT_BANK_PAYMENT_IDS:
        warnings.append(
            "Не задан BYBIT_BANK_PAYMENT_IDS: банковские переводы нельзя надёжно отфильтровать. "
            "Результаты не следует считать проверенными по способу оплаты."
        )

    try:
        # Bybit ad side is the advertiser's side. A user buying crypto needs
        # sell-side ads (side=1); a user selling crypto needs buy-side ads (side=0).
        raw_sell_ads, raw_buy_ads = await __import__("asyncio").gather(
            fetch_bybit_ads(asset, fiat, 1),
            fetch_bybit_ads(asset, fiat, 0),
        )
    except ApiUnavailable as exc:
        return ScanResponse(
            mode="unavailable",
            updated_at=now,
            opportunities=[],
            message=str(exc),
            warnings=warnings,
        )

    # If bank method IDs have been configured, keep only ads containing one of them.
    # Without configured IDs, do not silently pretend the ads are bank-transfer-only.
    def eligible(raw: list[dict]) -> list[dict]:
        result = []
        for item in raw:
            ad = _normalise_ad(item)
            if not ad["online"] or ad["price"] <= 0 or ad["qty"] <= 0:
                continue
            if BYBIT_BANK_PAYMENT_IDS and not (ad["payments"] & BYBIT_BANK_PAYMENT_IDS):
                continue
            result.append(ad)
        return result

    sell_ads = eligible(raw_sell_ads)  # user buys crypto from these ads
    buy_ads = eligible(raw_buy_ads)    # user sells crypto to these ads
    rows: list[Opportunity] = []

    # Match each buy-side and sell-side ad. Feasible size is constrained by
    # capital, remaining inventory, and the fiat min/max ranges of both ads.
    for sell_ad in sell_ads:
        for buy_ad in buy_ads:
            buy_price = sell_ad["price"]
            sell_price = buy_ad["price"]
            if sell_price <= buy_price:
                continue
            qty = min(
                capital / buy_price,
                sell_ad["qty"],
                buy_ad["qty"],
                sell_ad["max"] / buy_price if sell_ad["max"] > 0 else 0,
                buy_ad["max"] / sell_price if buy_ad["max"] > 0 else 0,
            )
            if qty <= 0:
                continue
            spent = qty * buy_price
            received = qty * sell_price
            if spent < sell_ad["min"] or received < buy_ad["min"]:
                continue
            rows.append(Opportunity(
                id=f"bybit-{sell_ad['id']}-{buy_ad['id']}",
                asset=asset,
                fiat=fiat,
                buy_exchange="Bybit P2P",
                sell_exchange="Bybit P2P",
                buy_price=buy_price,
                sell_price=sell_price,
                buy_ad_min_fiat=sell_ad["min"],
                buy_ad_max_fiat=sell_ad["max"],
                sell_ad_min_fiat=buy_ad["min"],
                sell_ad_max_fiat=buy_ad["max"],
                buy_payment_methods=sorted(sell_ad["payments"]),
                sell_payment_methods=sorted(buy_ad["payments"]),
                buy_advertiser_completion_pct=sell_ad["completion"],
                sell_advertiser_completion_pct=buy_ad["completion"],
                buy_advertiser_recent_orders=sell_ad["recent_orders"],
                sell_advertiser_recent_orders=buy_ad["recent_orders"],
                remaining_crypto=qty,
                source_updated_at=now,
                source_mode="live",
            ))

    rows.sort(key=lambda row: row.sell_price / row.buy_price - 1, reverse=True)
    return ScanResponse(
        mode="live",
        updated_at=now,
        opportunities=rows,
        message="Данные получены из официального Bybit P2P API.",
        warnings=warnings,
    )
