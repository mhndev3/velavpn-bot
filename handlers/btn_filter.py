"""
btn_filter.py — فیلتر داینامیک دکمه‌های منوی اصلی

مشکل قبلی: هندلرها متنِ ثابتِ دکمه را match می‌کردند (مثلاً F.text == "⚡ خرید کانفیگ").
وقتی هد‌ادمین از پنل، متن دکمه را عوض می‌کرد (مثلاً «خرید سرویس»)، دیگر هیچ هندلری
آن متن را نمی‌گرفت و دکمه «کار نمی‌کرد».

راه‌حل: این فیلتر، مقدارِ فعلیِ متنِ دکمه را زنده از جدول bot_settings می‌خواند
(get_setting) و علاوه بر آن چند alias/پیش‌فرض هم می‌پذیرد. پس دکمه چه تغییر کرده
باشد چه نه، بدون نیاز به ری‌استارت کار می‌کند.
"""
from aiogram.filters import BaseFilter
from aiogram.types import Message


class Btn(BaseFilter):
    def __init__(self, key: str, *aliases: str):
        self.key = key
        self.aliases = tuple(a for a in aliases if a)

    async def __call__(self, message: Message) -> bool:
        txt = (message.text or "").strip()
        if not txt:
            return False
        candidates = set(a.strip() for a in self.aliases)
        try:
            from database.db import get_setting
            current = (get_setting(self.key, "") or "").strip()
            if current:
                candidates.add(current)
        except Exception:
            pass
        return txt in candidates
