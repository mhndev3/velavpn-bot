from config.settings import USDT_TOMAN_RATE, TRX_TOMAN_RATE
from services.ui_texts import TF


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

    return TF(
        "price_crypto_block",
        "💵 معادل تقریبی: <b>{usdt} USDT</b>\n🔺 معادل تقریبی: <b>{trx} TRX</b>",
        usdt="{:.2f}".format(usdt), trx="{:.2f}".format(trx),
    )


def payment_price_block(price_toman: int) -> str:
    crypto_text = format_crypto_amounts(price_toman)
    toman_line = TF("price_toman_line", "💰 مبلغ تومانی: <b>{price} تومان</b>",
                    price="{:,}".format(price_toman))
    if crypto_text:
        return toman_line + "\n" + crypto_text
    return toman_line
