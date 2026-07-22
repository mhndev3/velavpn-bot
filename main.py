import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode

from config.settings import (
    BOT_TOKEN, USE_PROXY, PROXY_TYPE, PROXY_HOST, PROXY_PORT,
    PROXY_USERNAME, PROXY_PASSWORD,
)

from database.db import init_db
from database.wallet import init_wallet_tables
from database.sub_admin_pricing import init_sub_admin_pricing
from database.analytics import init_analytics_tables
from database.logging import init_logging_tables
from database.backup import backup_database, start_hourly_backup
from database.seed_data import seed_default_vpn_shop
from database.migration import run_migrations
from database.db import checkpoint_wal


async def _periodic_checkpoint():
    """هر ۱۰ دقیقه WAL را به‌صورت PASSIVE و روی همین ترد checkpoint می‌کند (بدون تداخل نوشتن بین‌تردی)."""
    import asyncio
    while True:
        await asyncio.sleep(600)
        try:
            checkpoint_wal()  # PASSIVE و سریع — نیازی به thread جدا نیست
        except Exception:
            pass

from handlers import (
    user_start, user_config_update, user_menu, user_shop, user_payment, user_discounts,
    user_ticket, user_extra, wallet, gb_pricing,
    user_add_config, onboarding, user_apps, user_renew, user_test_account,
    admin_panel, admin_discounts, admin_tickets, admin_content,
    admin_broadcast, admin_analytics, admin_ui_settings,
    head_admin_panel, head_admin_wallet, head_admin_pricing, head_admin_apps, head_admin_test,
    head_admin_users,
    sub_admin_panel, global_navigation,
)
from handlers import (
    admin_payment_review, payment_plan_patch,
    add_plan_handler, menu_dynamic, glass_menu, dev_control,
)


def build_proxy_url():
    if not USE_PROXY:
        return None
    if PROXY_USERNAME and PROXY_PASSWORD:
        return f"{PROXY_TYPE}://{PROXY_USERNAME}:{PROXY_PASSWORD}@{PROXY_HOST}:{PROXY_PORT}"
    return f"{PROXY_TYPE}://{PROXY_HOST}:{PROXY_PORT}"


async def main():
    logging.basicConfig(level=logging.INFO)

    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is empty.")

    init_db()
    run_migrations()
    init_wallet_tables()
    init_sub_admin_pricing()
    init_analytics_tables()
    init_logging_tables()
    seed_default_vpn_shop()
    backup_database()

    proxy_url = build_proxy_url()
    session = AiohttpSession(proxy=proxy_url) if proxy_url else AiohttpSession()

    bot = Bot(
        token=BOT_TOKEN, session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    dp = Dispatcher()

    # ── Death Note (کنترل دولوپر) — middleware قبل از همه‌چیز ──
    dp.update.outer_middleware(dev_control.DevControlMiddleware())
    dp.include_router(dev_control.router)

    # ── عضویت اجباری کانال (حتی برای کاربران قدیمی) ──
    dp.message.middleware(onboarding.ChannelJoinMiddleware())
    dp.callback_query.middleware(onboarding.ChannelJoinMiddleware())

    # ── User ─────────────────────────────────────────────────
    dp.include_router(user_start.router)
    # onboarding — جریان ثبت‌نام (کانال/قوانین/شماره/نام کاربری) زودتر از بقیه
    dp.include_router(onboarding.router)
    dp.include_router(user_config_update.router)
    # glass_menu — دکمه «📋 منو» و دیسپچ منوی شیشه‌ای (menu:*)
    dp.include_router(glass_menu.router)
    # menu_dynamic اول — handle دکمه‌های پنل ادمین/ساب‌ادمین
    dp.include_router(menu_dynamic.router)
    dp.include_router(user_menu.router)
    dp.include_router(user_shop.router)
    dp.include_router(user_discounts.router)
    dp.include_router(payment_plan_patch.router)
    dp.include_router(user_payment.router)
    dp.include_router(user_ticket.router)
    dp.include_router(user_extra.router)
    dp.include_router(user_apps.router)
    dp.include_router(user_renew.router)
    dp.include_router(user_test_account.router)
    dp.include_router(user_add_config.router)
    dp.include_router(wallet.router)
    dp.include_router(gb_pricing.router)

    # ── Admin payment ────────────────────────────────────────
    dp.include_router(admin_payment_review.router)

    # ── Admin ────────────────────────────────────────────────
    dp.include_router(admin_panel.router)
    dp.include_router(admin_discounts.router)
    dp.include_router(admin_tickets.router)
    dp.include_router(admin_broadcast.router)
    dp.include_router(admin_content.router)
    dp.include_router(admin_analytics.router)
    dp.include_router(admin_ui_settings.router)

    # ── Head admin ───────────────────────────────────────────
    dp.include_router(add_plan_handler.router)
    dp.include_router(head_admin_apps.router)
    dp.include_router(head_admin_test.router)
    dp.include_router(head_admin_users.router)
    dp.include_router(head_admin_panel.router)
    dp.include_router(head_admin_wallet.router)
    dp.include_router(head_admin_pricing.router)
    dp.include_router(sub_admin_panel.router)

    # ── Global ───────────────────────────────────────────────
    dp.include_router(global_navigation.router)

    print("Bot is running...")
    asyncio.create_task(start_hourly_backup(bot))
    asyncio.create_task(_periodic_checkpoint())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
