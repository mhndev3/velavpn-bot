"""
user_add_config.py — «افزودن کانفیگ من»

کاربر کانفیگ خودش (لینک) یا فقط «نام کانفیگ» را می‌فرستد؛ بات در همهٔ سرورهای
فعال X-UI بر اساس email/نام جستجو می‌کند. اگر کلاینت در پنل موجود بود:
  - به «اشتراک‌های من» اضافه می‌شود (جدول subscriptions + xui_accounts)
  - subId ذخیره می‌شود تا «دریافت کانفیگ آپدیت‌شده» کار کند
  - کاربر می‌تواند وضعیت و حجم باقیمانده را ببیند
پروتکل‌محور است (vless/vmess/trojan/ss/...).
"""
import json
import base64
import urllib.parse
from datetime import datetime

from aiogram import Router
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from database.db import get_active_servers, get_connection, save_xui_account
from handlers.btn_filter import Btn

router = Router()


class AddConfigStates(StatesGroup):
    waiting = State()


_PREFIXES = ("vless://", "trojan://", "ss://", "tuic://", "hysteria://", "hysteria2://")


def _extract_candidates(text: str):
    """
    از ورودی، همهٔ شناسه‌های ممکن برای پیدا کردن کلاینت را برمی‌گرداند:
    نام(#/ps)، UUID، پسوردِ shadowsocks (با هر دو نوع base64 استاندارد و URL-safe).
    این باعث می‌شود لینکی که از اپ کپی شده (فرمت متفاوت) هم شناسایی شود.
    """
    t = (text or "").strip()
    cands = []

    def add(x):
        x = (x or "").strip()
        if x and x not in cands:
            cands.append(x)

    def try_b64(b):
        for v in (b, b.replace("-", "+").replace("_", "/")):
            try:
                pad = "=" * (-len(v) % 4)
                return base64.b64decode(v + pad).decode("utf-8", "ignore")
            except Exception:
                continue
        return ""

    if not t:
        return cands

    if t.startswith("vmess://"):
        dec = try_b64(t[len("vmess://"):].strip())
        try:
            cfg = json.loads(dec)
            add(cfg.get("id"))
            add(cfg.get("ps"))
        except Exception:
            pass
        return cands

    if any(t.startswith(p) for p in _PREFIXES):
        # نام از #fragment
        if "#" in t:
            frag = urllib.parse.unquote(t.split("#", 1)[1]).strip()
            add(frag)
            # اگر remark اینباند جلوی اسم چسبیده باشد (مثل User3-arashtest)،
            # بخش‌های بعدی را هم به‌عنوان کاندید اضافه کن تا با email کلاینت (arashtest) تطبیق بخورد
            if "-" in frag:
                parts = frag.split("-")
                add(parts[-1])
                add("-".join(parts[1:]))
        after = t.split("://", 1)[1]
        cred = after.split("@", 1)[0] if "@" in after else after.split("?", 1)[0].split("#", 1)[0]
        add(cred)  # UUID برای vless/trojan
        # ss: userinfo ممکن است base64(method:password) یا plain «method:password» باشد
        dec = try_b64(cred)
        if ":" in dec:
            userinfo = dec.split("@", 1)[0]  # حالت legacy: method:password@host
            if ":" in userinfo:
                add(userinfo.split(":", 1)[1])  # پسورد
        elif ":" in cred:
            add(cred.split(":", 1)[1])  # plain method:password (بدون base64)
        return cands

    add(t)  # متن خام = نام
    return cands


@router.message(Btn("btn_addcfg", "➕ افزودن کانفیگ من"))
async def add_config_start(msg: Message, state: FSMContext):
    await state.clear()
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    await msg.answer(
        "➕ افزودن کانفیگ من\n\n"
        "اگر قبلاً کانفیگ گرفته‌ای ولی در «اشتراک‌های من» نیست، "
        "کانفیگ (لینک کامل) یا فقط «نام کانفیگ» را بفرست تا پیدا و اضافه‌اش کنم.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ بازگشت", callback_data="u:menu")]
        ]),
    )
    await state.set_state(AddConfigStates.waiting)


@router.message(AddConfigStates.waiting)
async def add_config_search(msg: Message, state: FSMContext):
    queries = _extract_candidates(msg.text or "")
    name = queries[0] if queries else ""
    if not queries:
        await state.clear()
        return await msg.answer("❌ نام کانفیگ خوانده نشد. لینک کامل یا نام دقیق کانفیگ را بفرست.")
    await state.clear()
    await msg.answer("⏳ در حال جستجوی کانفیگ در سرورها...")

    from services.xui_service import XUIClient
    found = None
    any_login = False
    servers = get_active_servers()
    if not servers:
        return await msg.answer("❌ فعلاً سروری تنظیم نشده. با پشتیبانی تماس بگیر.")

    for server in servers:
        c = XUIClient(server)
        try:
            ok, _ = await c.login()
            if not ok:
                continue
            any_login = True
            for q in queries:
                res = await c.find_client_by_email(q)
                if res:
                    inbound = res["inbound"]
                    client = res["client"]
                    display = str(client.get("email", "")).strip() or name or q
                    link = c.build_vless_link(
                        inbound, client.get("id", ""), display, client.get("password", "")
                    )
                    found = {"server": server, "inbound": inbound, "client": client,
                             "link": link, "display": display}
                    break
            if found:
                break
        except Exception:
            continue
        finally:
            try:
                await c.close()
            except Exception:
                pass

    if not found:
        if not any_login:
            return await msg.answer(
                "❌ در حال حاضر اتصال به پنل برقرار نشد. کمی بعد دوباره تلاش کن "
                "یا با پشتیبانی تماس بگیر."
            )
        return await msg.answer(
            "❌ کانفیگی با این مشخصات در سرورها پیدا نشد.\n\n"
            "بهتر است «لینک کامل» کانفیگ را بفرستی (نه فقط نام) تا با شناسهٔ داخل لینک دقیق پیدا شود.\n"
            "اگر باز هم پیدا نشد، با پشتیبانی تماس بگیر."
        )

    server = found["server"]
    inbound = found["inbound"]
    client = found["client"]
    email = found["display"]
    sub_id = client.get("subId", "") or client.get("sub_id", "") or ""

    exp_ms = client.get("expiryTime", 0) or 0
    try:
        expires_at = (
            datetime.fromtimestamp(int(exp_ms) / 1000).strftime("%Y-%m-%d %H:%M:%S")
            if exp_ms else ""
        )
    except Exception:
        expires_at = ""
    total = client.get("totalGB", 0) or 0
    try:
        traffic_gb = int(int(total) / (1024 ** 3)) if total else 0
    except Exception:
        traffic_gb = 0

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT id FROM subscriptions WHERE telegram_id=? AND plan_title=? AND status='active'",
            (msg.from_user.id, email),
        )
        if cur.fetchone():
            return await msg.answer("ℹ️ این کانفیگ از قبل در «اشتراک‌های من» شما موجود است.")
        cur.execute(
            """INSERT INTO orders
               (telegram_id, plan_id, service_name, plan_title, price_toman,
                duration_days, status, final_price_toman, referral_processed)
               VALUES (?, 0, 'کانفیگ واردشده', ?, 0, 0, 'imported', 0, 1)""",
            (msg.from_user.id, email),
        )
        order_id = cur.lastrowid
        cur.execute(
            """INSERT INTO subscriptions
               (telegram_id, order_id, service_name, plan_title, duration_days,
                status, expires_at, delivery_text)
               VALUES (?, ?, 'کانفیگ واردشده', ?, 0, 'active', ?, ?)""",
            (msg.from_user.id, order_id, email, expires_at, found["link"] or ""),
        )
        conn.commit()
    finally:
        conn.close()

    try:
        save_xui_account(
            telegram_id=msg.from_user.id, order_id=order_id, server_id=server["id"],
            xui_client_id=client.get("id", ""), xui_inbound_id=inbound.get("id", 0),
            email=email, config_link=found["link"] or "",
            config_type=(inbound.get("protocol", "vless") or "vless"),
            traffic_gb=traffic_gb, expires_at=expires_at, sub_id=sub_id,
        )
    except Exception:
        pass

    await msg.answer(
        "✅ کانفیگ پیدا و به «اشتراک‌های من» اضافه شد.\n"
        "حالا می‌توانی وضعیت، حجم باقیمانده و کانفیگ آپدیت‌شده‌اش را از همان بخش ببینی."
    )
