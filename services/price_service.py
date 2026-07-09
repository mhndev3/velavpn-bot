from config.settings import USDT_TOMAN_RATE, TRX_TOMAN_RATE


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def crypto_amounts(price_toman: int) -> dict:
    price = int(price_toman or 0)
    usdt_rate = _safe_float(USDT_TOMAN_RATE, 0)
    trx_rate = _safe_float(TRX_TOMAN_RATE, 0)

    usdt = price / usdt_rate if usdt_rate > 0 else 0
    trx = price / trx_rate if trx_rate > 0 else 0

    return {
        "usdt": usdt,
        "trx": trx,
        "usdt_rate": usdt_rate,
        "trx_rate": trx_rate,
    }


def format_crypto_amounts(price_toman: int) -> str:
    data = crypto_amounts(price_toman)
    usdt = data["usdt"]
    trx = data["trx"]

    if usdt <= 0 or trx <= 0:
        return ""

    return (
        f"💵 معادل تقریبی: <b>{usdt:.2f} USDT</b>\n"
        f"🔺 معادل تقریبی: <b>{trx:.2f} TRX</b>"
    )


def payment_price_block(price_toman: int) -> str:
    crypto_text = format_crypto_amounts(price_toman)
    if crypto_text:
        return (
            f"💰 مبلغ تومانی: <b>{price_toman:,} تومان</b>\n"
            f"{crypto_text}"
        )
    return f"💰 مبلغ تومانی: <b>{price_toman:,} تومان</b>"
