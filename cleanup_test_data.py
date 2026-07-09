from database.db import get_connection


TEST_KEYWORDS = [
    "تست",
    "test",
    "vip test",
    "fake",
    "sample",
]


def cleanup_services(cursor):
    for keyword in TEST_KEYWORDS:
        cursor.execute("""
        DELETE FROM services
        WHERE LOWER(name) LIKE ?
        """, (f"%{keyword.lower()}%",))


def cleanup_plans(cursor):
    for keyword in TEST_KEYWORDS:
        cursor.execute("""
        DELETE FROM plans
        WHERE LOWER(title) LIKE ?
        """, (f"%{keyword.lower()}%",))


def cleanup_faq(cursor):
    for keyword in TEST_KEYWORDS:
        cursor.execute("""
        DELETE FROM faq_items
        WHERE LOWER(question) LIKE ?
        """, (f"%{keyword.lower()}%",))


def cleanup_content(cursor):
    for keyword in TEST_KEYWORDS:
        cursor.execute("""
        DELETE FROM content_pages
        WHERE LOWER(content) LIKE ?
        """, (f"%{keyword.lower()}%",))


def cleanup_orders(cursor):
    cursor.execute("""
    DELETE FROM payments
    """)

    cursor.execute("""
    DELETE FROM subscriptions
    """)

    cursor.execute("""
    DELETE FROM orders
    """)


def main():
    conn = get_connection()
    cursor = conn.cursor()

    cleanup_services(cursor)
    cleanup_plans(cursor)
    cleanup_faq(cursor)
    cleanup_content(cursor)
    cleanup_orders(cursor)

    conn.commit()
    conn.close()

    print("================================")
    print("Test data cleaned successfully.")
    print("================================")


if __name__ == "__main__":
    main()