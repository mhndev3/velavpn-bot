"""
onboarding.py — جریان ثبت‌نام کاربر جدید (فقط سمت یوزر):
  ۱) عضویت اجباری در کانال‌ها  ۲) پذیرش قوانین  ۳) تأیید شماره تلفن  ۴) نام کاربری
همهٔ متن‌ها/دکمه‌ها از «تنظیمات UI» قابل‌ویرایش‌اند (با پشتیبانی ایموجی پریمیوم در متن‌ها).
"""
from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from database.db import (
    get_required_channels, get_user, set_user_field, is_onboarding_done,
)
from services.ui_texts import T
from services.ui_render import answer_ui

router = Router()


class OnboardingStates(StatesGroup):
    waiting_username = State()


# ── متن‌ها/دکمه‌های پیش‌فرض (قابل‌ویرایش از پنل) ─────────────
DEF = {
    "onb_join_text": "🔒 برای استفاده از ربات، ابتدا باید در کانال‌های ما عضو شوید.\n\nپس از عضویت در همهٔ کانال‌ها، روی «عضو شدم» بزنید.",
    "onb_join_btn": "✅ عضو شدم",
    "onb_notjoined": "❌ هنوز در همهٔ کانال‌ها عضو نشده‌اید.",
    "onb_rules_text": "📜 قوانین استفاده از خدمات ما\n\n۱- به اطلاعیه‌هایی که داخل کانال گذاشته می‌شود حتماً توجه کنید.\n۲- در صورتی که اطلاعیه‌ای در مورد قطعی در کانال گذاشته نشده به اکانت پشتیبانی پیام دهید.\n۳- سرویس‌ها را از طریق پیامک ارسال نکنید؛ برای ارسال می‌توانید از طریق ایمیل ارسال کنید.",
    "onb_rules_btn": "✅ قوانین را می‌پذیرم",
    "onb_phone_text": "📱 شماره موبایل خود را با دکمهٔ زیر به اشتراک بگذارید تا ثبت‌نام شما تأیید شود و بتوانید از ربات استفاده کنید.",
    "onb_phone_btn": "📱 ارسال شماره تلفن",
    "onb_username_text": "👤 لطفاً یک نام کاربری برای حساب خود انتخاب کنید و ارسال کنید.",
    "onb_done_text": "✅ ثبت‌نام شما کامل شد! خوش آمدید.",
}


def _t(key):
    return T(key, DEF.get(key, ""))


def _join_kb():
    rows = []
    for ch in get_required_channels():
        title = ch.get("title") or ch.get("chat_id") or "کانال"
        url = ch.get("url") or ""
        if url:
            rows.append([InlineKeyboardButton(text="📢 " + title, url=url)])
    rows.append([InlineKeyboardButton(text=_t("onb_join_btn"), callback_data="onb:checkjoin")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _rules_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=_t("onb_rules_btn"), callback_data="onb:accept_rules")]
    ])


def _phone_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=_t("onb_phone_btn"), request_contact=True)]],
        resize_keyboard=True, one_time_keyboard=True,
    )


async def _is_member_all(bot, uid: int) -> bool:
    """آیا کاربر در همهٔ کانال‌های اجباری عضو است؟ (اگر کانالی نباشد → True)"""
    channels = get_required_channels()
    if not channels:
        return True
    for ch in channels:
        cid = ch.get("chat_id")
        if not cid:
            continue
        try:
            m = await bot.get_chat_member(chat_id=cid, user_id=uid)
            if m.status in ("left", "kicked"):
                return False
        except Exception:
            # اگر بات نتواند بررسی کند (مثلاً ادمین کانال نیست) از آن کانال صرف‌نظر می‌شود
            continue
    return True


async def advance_onboarding(msg: Message, uid: int, state: FSMContext, bot) -> bool:
    """
    مرحلهٔ بعدیِ لازم را نشان می‌دهد. اگر همهٔ مراحل کامل باشد، onboarding را
    تمام‌شده علامت می‌زند و True برمی‌گرداند (یعنی «منو را نشان بده»).
    """
    # 1) قوانین (اولین مرحله)
    u = get_user(uid) or {}
    if not u.get("rules_accepted"):
        await answer_ui(msg, "onb_rules_text", DEF["onb_rules_text"], reply_markup=_rules_kb())
        return False
    # 2) عضویت کانال
    if not await _is_member_all(bot, uid):
        await answer_ui(msg, "onb_join_text", DEF["onb_join_text"], reply_markup=_join_kb())
        return False
    # 3) شماره تلفن
    if not (u.get("phone") or "").strip():
        await answer_ui(msg, "onb_phone_text", DEF["onb_phone_text"], reply_markup=_phone_kb())
        return False
    # 4) نام کاربری
    if not (u.get("custom_username") or "").strip():
        await state.set_state(OnboardingStates.waiting_username)
        await answer_ui(msg, "onb_username_text", DEF["onb_username_text"],
                        reply_markup=ReplyKeyboardRemove())
        return False
    # تمام
    set_user_field(uid, "onboarding_done", 1)
    await state.clear()
    return True


async def _finish_and_menu(msg: Message, uid: int, state: FSMContext):
    set_user_field(uid, "onboarding_done", 1)
    await state.clear()
    from handlers.glass_menu import send_user_menu
    await answer_ui(msg, "onb_done_text", DEF["onb_done_text"], reply_markup=ReplyKeyboardRemove())
    # پیام خوش‌آمد (همان صفحه‌ای که /start نشان می‌دهد) — قابل ویرایش از پنل
    try:
        from services.content_media_service import send_content_page
        await send_content_page(
            message=msg,
            key="start_message",
            fallback_text=("سلام 👋\n\nامروز تمامی خدمات فعال و آماده سرویس‌دهی است."),
        )
    except Exception:
        pass
    await send_user_menu(msg, uid)


@router.callback_query(F.data == "onb:checkjoin")
async def onb_checkjoin(cb: CallbackQuery, state: FSMContext):
    if not await _is_member_all(cb.bot, cb.from_user.id):
        return await cb.answer(_t("onb_notjoined"), show_alert=True)
    await cb.answer()
    try:
        await cb.message.delete()
    except Exception:
        pass
    done = await advance_onboarding(cb.message, cb.from_user.id, state, cb.bot)
    if done:
        await _finish_and_menu(cb.message, cb.from_user.id, state)


@router.callback_query(F.data == "onb:accept_rules")
async def onb_accept_rules(cb: CallbackQuery, state: FSMContext):
    set_user_field(cb.from_user.id, "rules_accepted", 1)
    await cb.answer()
    try:
        await cb.message.delete()
    except Exception:
        pass
    done = await advance_onboarding(cb.message, cb.from_user.id, state, cb.bot)
    if done:
        await _finish_and_menu(cb.message, cb.from_user.id, state)


@router.message(F.contact)
async def onb_contact(msg: Message, state: FSMContext):
    # فقط اگر هنوز شماره ثبت نشده (در جریان ثبت‌نام)
    u = get_user(msg.from_user.id) or {}
    if (u.get("phone") or "").strip():
        return
    phone = msg.contact.phone_number if msg.contact else ""
    set_user_field(msg.from_user.id, "phone", phone)
    done = await advance_onboarding(msg, msg.from_user.id, state, msg.bot)
    if done:
        await _finish_and_menu(msg, msg.from_user.id, state)


@router.message(OnboardingStates.waiting_username)
async def onb_username(msg: Message, state: FSMContext):
    uname = (msg.text or "").strip()
    if not uname or len(uname) > 32:
        return await msg.answer("❌ نام کاربری نامعتبر است. یک نام کوتاه‌تر بفرست.")
    set_user_field(msg.from_user.id, "custom_username", uname)
    await _finish_and_menu(msg, msg.from_user.id, state)


# ── Middleware: عضویت اجباری کانال برای همه (حتی کاربران قدیمی) ──
import time as _time
from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery as _CB

_member_cache = {}  # uid -> expiry ts (فقط برای عضوهای تاییدشده کش می‌شود)


class ChannelJoinMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        user = data.get("event_from_user")
        if user is None:
            return await handler(event, data)
        uid = user.id
        # ادمین‌ها و ساب‌ادمین‌ها مستثنا
        try:
            from database.db import is_head_admin, get_sub_admin
            if is_head_admin(uid) or get_sub_admin(uid):
                return await handler(event, data)
        except Exception:
            pass
        # کال‌بک‌های خود جریان ثبت‌نام آزادند تا دکمهٔ «عضو شدم» کار کند
        if isinstance(event, _CB) and (event.data or "").startswith("onb:"):
            return await handler(event, data)
        # اگر هنوز قوانین را نپذیرفته، مانع نشو تا اول صفحهٔ قوانین نمایش داده شود
        try:
            _u = get_user(uid) or {}
            if not _u.get("rules_accepted"):
                return await handler(event, data)
        except Exception:
            pass
        channels = get_required_channels()
        if not channels:
            return await handler(event, data)
        now = _time.time()
        if _member_cache.get(uid, 0) > now:
            return await handler(event, data)
        bot = data.get("bot")
        try:
            ok = await _is_member_all(bot, uid)
        except Exception:
            ok = True  # اگر بررسی ممکن نبود، مانع نشو
        if ok:
            _member_cache[uid] = now + 120  # عضویت را ۲ دقیقه کش کن
            return await handler(event, data)
        # عضو نیست → صفحهٔ جوین را نشان بده و جلوی ادامه را بگیر
        try:
            if isinstance(event, _CB):
                await event.answer()
                target = event.message
            else:
                target = event
            await answer_ui(target, "onb_join_text", DEF["onb_join_text"], reply_markup=_join_kb())
        except Exception:
            pass
        return  # بلاک
