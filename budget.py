from datetime import date

from db import get_connection


def load_budget_categories():
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM budget_categories ORDER BY rowid").fetchall()
        return {
            row["key"]: {"label": row["label"], "type": row["type"], "monthly_target": row["monthly_target"]}
            for row in rows
        }
    finally:
        conn.close()


def save_budget_categories(categories):
    conn = get_connection()
    try:
        conn.execute("DELETE FROM budget_categories")
        conn.executemany(
            "INSERT INTO budget_categories (key, label, type, monthly_target) VALUES (?, ?, ?, ?)",
            [(key, c["label"], c["type"], c["monthly_target"]) for key, c in categories.items()],
        )
        conn.commit()
    finally:
        conn.close()


def load_budget_actuals():
    """{month: {category_key: total}} — one hand-entered total per category per
    month (e.g. copied from a bank app's spending-insights tab), not a
    transaction-level ledger."""
    conn = get_connection()
    try:
        rows = conn.execute("SELECT month, category_key, amount FROM budget_actuals").fetchall()
        actuals = {}
        for row in rows:
            actuals.setdefault(row["month"], {})[row["category_key"]] = row["amount"]
        return actuals
    finally:
        conn.close()


def save_budget_actuals(actuals):
    conn = get_connection()
    try:
        conn.execute("DELETE FROM budget_actuals")
        conn.executemany(
            "INSERT INTO budget_actuals (month, category_key, amount) VALUES (?, ?, ?)",
            [
                (month, category_key, amount)
                for month, values in actuals.items()
                for category_key, amount in values.items()
            ],
        )
        conn.commit()
    finally:
        conn.close()


def shift_month(month, delta):
    """`month` (YYYY-MM) shifted by `delta` months, e.g. shift_month('2026-01', -1) == '2025-12'."""
    year, mon = (int(p) for p in month.split("-"))
    mon += delta
    year += (mon - 1) // 12
    mon = (mon - 1) % 12 + 1
    return f"{year:04d}-{mon:02d}"


def month_label(month):
    return date.fromisoformat(f"{month}-01").strftime("%B %Y")


def monthly_summary(actuals, categories, month):
    """Actual vs target per category for `month` (YYYY-MM), plus income/expense/
    net totals. Every category appears even with nothing entered yet (actual 0),
    so the form always has a row to fill in."""
    month_actuals = actuals.get(month, {})

    rows = []
    total_income = total_expense = 0.0
    target_income = target_expense = 0.0
    for key, cat in categories.items():
        actual = round(month_actuals.get(key, 0.0), 2)
        target = cat["monthly_target"]
        rows.append({
            "key": key,
            "label": cat["label"],
            "type": cat["type"],
            "target": target,
            "actual": actual,
            "remaining": round(target - actual, 2),
            "pct_of_target": round((actual / target) * 100, 1) if target else None,
        })
        if cat["type"] == "income":
            total_income += actual
            target_income += target
        else:
            total_expense += actual
            target_expense += target

    return {
        "month": month,
        "rows": rows,
        "total_income": round(total_income, 2),
        "total_expense": round(total_expense, 2),
        "net": round(total_income - total_expense, 2),
        "target_income": round(target_income, 2),
        "target_expense": round(target_expense, 2),
        "target_net": round(target_income - target_expense, 2),
    }
