from database.db import get_connection, get_setting


REFERRAL_PERCENT = 0
INVITED_BONUS_DAYS = 3


def get_referral_commission_percent() -> int:
    """درصد کمیسیون رفرال — هد ادمین از پنل تنظیمات قابل تغییره"""
    try:
        return int(get_setting("referral_commission_percent", "0") or "0")
    except (ValueError, TypeError):
        return 0


def rows_to_dicts(cursor, rows):
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in rows]


def get_user(telegram_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT *
    FROM users
    WHERE telegram_id = ?
    """, (telegram_id,))

    row = cursor.fetchone()

    if not row:
        conn.close()
        return None

    user = rows_to_dicts(cursor, [row])[0]
    conn.close()
    return user


def set_referrer(invited_id: int, inviter_id: int):
    if invited_id == inviter_id:
        return False

    invited_user = get_user(invited_id)

    if not invited_user:
        return False

    if invited_user.get("referrer_id"):
        return False

    inviter_user = get_user(inviter_id)

    if not inviter_user:
        return False

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    UPDATE users
    SET referrer_id = ?
    WHERE telegram_id = ? AND referrer_id IS NULL
    """, (
        inviter_id,
        invited_id
    ))

    cursor.execute("""
    INSERT OR IGNORE INTO referrals (
        inviter_id,
        invited_id
    )
    VALUES (?, ?)
    """, (
        inviter_id,
        invited_id
    ))

    conn.commit()
    conn.close()

    return True


def get_referrer_id(telegram_id: int):
    user = get_user(telegram_id)

    if not user:
        return None

    return user.get("referrer_id")


def get_referral_count(inviter_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT COUNT(*)
    FROM referrals
    WHERE inviter_id = ?
    """, (inviter_id,))

    count = cursor.fetchone()[0]

    conn.close()
    return count


def get_referral_rewards(inviter_id: int, limit: int = 10):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT *
    FROM referral_rewards
    WHERE inviter_id = ?
    ORDER BY id DESC
    LIMIT ?
    """, (
        inviter_id,
        limit
    ))

    rows = cursor.fetchall()
    rewards = rows_to_dicts(cursor, rows)

    conn.close()
    return rewards


def is_referral_processed(order_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT referral_processed
    FROM orders
    WHERE id = ?
    """, (order_id,))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return True

    return bool(row[0])


def mark_referral_processed(order_id: int):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE orders SET referral_processed = 1 WHERE id = ?", (order_id,))
        conn.commit()
        conn.close()
    except Exception:
        pass


def process_referral_reward(order: dict):
    order_id = order["id"]

    if is_referral_processed(order_id):
        return None

    invited_id = order["telegram_id"]
    inviter_id = get_referrer_id(invited_id)

    if not inviter_id:
        mark_referral_processed(order_id)
        return None

    order_amount = order.get("final_price_toman") or order.get("price_toman") or 0
    commission_percent = get_referral_commission_percent()
    reward_amount = int(order_amount * commission_percent / 100) if commission_percent > 0 else 0
    bonus_days = INVITED_BONUS_DAYS

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO referral_rewards (
        inviter_id,
        invited_id,
        order_id,
        reward_amount,
        bonus_days
    )
    VALUES (?, ?, ?, ?, ?)
    """, (
        inviter_id,
        invited_id,
        order_id,
        reward_amount,
        bonus_days,
    ))

    conn.commit()
    conn.close()

    mark_referral_processed(order_id)

    # واریز کمیسیون نقدی به کیف‌پول معرّف (در صورت فعال بودن درصد کمیسیون)
    if reward_amount > 0:
        try:
            from database.wallet import add_to_wallet
            add_to_wallet(
                inviter_id,
                reward_amount,
                f"کمیسیون رفرال (سفارش #{order_id})",
            )
        except Exception:
            pass

    return {
        "inviter_id": inviter_id,
        "invited_id": invited_id,
        "reward_amount": reward_amount,
        "bonus_days": bonus_days,
    }


async def notify_referral_reward(bot, reward_data: dict):
    """اطلاع به معرف در صورت دریافت کمیسیون"""
    if not reward_data or not reward_data.get("inviter_id"):
        return
    reward_amount = reward_data.get("reward_amount", 0)
    if reward_amount <= 0:
        return
    try:
        await bot.send_message(
            chat_id=reward_data["inviter_id"],
            text=(
                "🎁 کمیسیون رفرال دریافت کردید!\n\n"
                "مبلغ: " + "{:,}".format(reward_amount) + " تومان\n"
                "به کیف\u200cپول شما اضافه شد."
            )
        )
    except Exception:
        pass
