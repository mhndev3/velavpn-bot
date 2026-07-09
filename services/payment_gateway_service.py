"""
payment_gateway_service.py
سرویس پرداخت آنلاین — ZarinPal و IDPay
ادمین از پنل خودش درگاه اضافه می‌کنه و API key می‌ده
"""
import aiohttp
from database.db import get_gateway, get_default_gateway, log_gateway


SUPPORTED_GATEWAYS = {
    "zarinpal": "زرین‌پال",
    "idpay":    "آیدی‌پی",
    "card":     "کارت به کارت (دستی)",
    "crypto":   "ارز دیجیتال (دستی)",
}


def gateway_type_label(gateway_type: str) -> str:
    return SUPPORTED_GATEWAYS.get(gateway_type, gateway_type)


# ─── ZarinPal ────────────────────────────────────────────────
async def zarinpal_request(merchant_id: str, amount_toman: int,
                           callback_url: str, description: str) -> dict:
    """درخواست پرداخت زرین‌پال — برمی‌گردونه {authority, payment_url} یا {error}"""
    url = "https://api.zarinpal.com/pg/v4/payment/request.json"
    payload = {
        "merchant_id": merchant_id,
        "amount": amount_toman * 10,  # ریال
        "callback_url": callback_url,
        "description": description,
    }
    try:
        async with aiohttp.ClientSession() as session:
            resp = await session.post(url, json=payload,
                                      timeout=aiohttp.ClientTimeout(total=15))
            data = await resp.json()
            if data.get("data", {}).get("code") == 100:
                authority = data["data"]["authority"]
                return {
                    "authority": authority,
                    "payment_url": f"https://www.zarinpal.com/pg/StartPay/{authority}",
                }
            errors = data.get("errors", {})
            return {"error": str(errors.get("message", "خطای ناشناخته زرین‌پال"))}
    except Exception as e:
        return {"error": str(e)}


async def zarinpal_verify(merchant_id: str, authority: str,
                          amount_toman: int) -> dict:
    """تایید پرداخت زرین‌پال — برمی‌گردونه {ref_id} یا {error}"""
    url = "https://api.zarinpal.com/pg/v4/payment/verify.json"
    payload = {
        "merchant_id": merchant_id,
        "authority": authority,
        "amount": amount_toman * 10,
    }
    try:
        async with aiohttp.ClientSession() as session:
            resp = await session.post(url, json=payload,
                                      timeout=aiohttp.ClientTimeout(total=15))
            data = await resp.json()
            code = data.get("data", {}).get("code")
            if code in (100, 101):
                return {"ref_id": str(data["data"]["ref_id"])}
            return {"error": f"کد {code} — پرداخت تایید نشد"}
    except Exception as e:
        return {"error": str(e)}


# ─── IDPay ───────────────────────────────────────────────────
async def idpay_request(api_key: str, order_id: int,
                        amount_toman: int, callback_url: str,
                        name: str = "", phone: str = "") -> dict:
    """درخواست پرداخت آیدی‌پی"""
    url = "https://api.idpay.ir/v1.1/payment"
    headers = {"X-API-KEY": api_key, "X-SANDBOX": "0"}
    payload = {
        "order_id": str(order_id),
        "amount": amount_toman * 10,
        "name": name,
        "phone": phone,
        "mail": "",
        "desc": f"سفارش #{order_id}",
        "callback": callback_url,
    }
    try:
        async with aiohttp.ClientSession() as session:
            resp = await session.post(url, json=payload, headers=headers,
                                      timeout=aiohttp.ClientTimeout(total=15))
            data = await resp.json()
            if resp.status == 201 and data.get("id") and data.get("link"):
                return {"authority": data["id"], "payment_url": data["link"]}
            return {"error": data.get("message", "خطای ناشناخته آیدی‌پی")}
    except Exception as e:
        return {"error": str(e)}


async def idpay_verify(api_key: str, order_id: int, transaction_id: str) -> dict:
    """تایید پرداخت آیدی‌پی"""
    url = "https://api.idpay.ir/v1.1/payment/verify"
    headers = {"X-API-KEY": api_key, "X-SANDBOX": "0"}
    payload = {"id": transaction_id, "order_id": str(order_id)}
    try:
        async with aiohttp.ClientSession() as session:
            resp = await session.post(url, json=payload, headers=headers,
                                      timeout=aiohttp.ClientTimeout(total=15))
            data = await resp.json()
            if data.get("status") in (100, 101):
                return {"ref_id": str(data.get("track_id", transaction_id))}
            return {"error": data.get("message", "تایید ناموفق")}
    except Exception as e:
        return {"error": str(e)}


# ─── Unified Gateway Interface ────────────────────────────────
async def initiate_payment(gateway_id: int, order_id: int,
                           amount_toman: int, description: str = "") -> dict:
    """
    شروع پرداخت با درگاه مشخص.
    برمی‌گردونه: {payment_url, authority} یا {error}
    """
    gw = get_gateway(gateway_id)
    if not gw:
        return {"error": "درگاه پیدا نشد"}

    gtype = gw["gateway_type"]
    callback = gw.get("callback_url", "")

    if gtype == "zarinpal":
        result = await zarinpal_request(
            merchant_id=gw["merchant_id"],
            amount_toman=amount_toman,
            callback_url=callback,
            description=description or f"سفارش #{order_id}",
        )

    elif gtype == "idpay":
        result = await idpay_request(
            api_key=gw["api_key"],
            order_id=order_id,
            amount_toman=amount_toman,
            callback_url=callback,
        )

    else:
        return {"error": f"نوع درگاه '{gtype}' پشتیبانی نمی‌شود"}

    status = "initiated" if "payment_url" in result else "failed"
    log_gateway(
        order_id=order_id,
        gateway_id=gateway_id,
        ref_id=result.get("authority", ""),
        amount=amount_toman,
        status=status,
        raw_response=str(result),
    )
    return result


async def verify_payment(gateway_id: int, order_id: int,
                         authority: str, amount_toman: int) -> dict:
    """
    تایید پرداخت.
    برمی‌گردونه: {ref_id} یا {error}
    """
    gw = get_gateway(gateway_id)
    if not gw:
        return {"error": "درگاه پیدا نشد"}

    gtype = gw["gateway_type"]

    if gtype == "zarinpal":
        result = await zarinpal_verify(
            merchant_id=gw["merchant_id"],
            authority=authority,
            amount_toman=amount_toman,
        )
    elif gtype == "idpay":
        result = await idpay_verify(
            api_key=gw["api_key"],
            order_id=order_id,
            transaction_id=authority,
        )
    else:
        return {"error": "نوع درگاه پشتیبانی نمی‌شود"}

    status = "verified" if "ref_id" in result else "verify_failed"
    log_gateway(
        order_id=order_id,
        gateway_id=gateway_id,
        ref_id=result.get("ref_id", authority),
        amount=amount_toman,
        status=status,
        raw_response=str(result),
    )
    return result
