import json
from datetime import date
from pathlib import Path

BUDGET_PATH = Path(__file__).parent / "data" / "budget.json"
BUDGET_ACTUALS_PATH = Path(__file__).parent / "data" / "budget_actuals.json"


def load_budget_categories():
    with open(BUDGET_PATH) as f:
        return json.load(f)["categories"]


def save_budget_categories(categories):
    with open(BUDGET_PATH, "w") as f:
        json.dump({"categories": categories}, f, indent=2)
        f.write("\n")


def load_budget_actuals():
    """{month: {category_key: total}} — one hand-entered total per category per
    month (e.g. copied from a bank app's spending-insights tab), not a
    transaction-level ledger."""
    with open(BUDGET_ACTUALS_PATH) as f:
        return json.load(f)


def save_budget_actuals(actuals):
    with open(BUDGET_ACTUALS_PATH, "w") as f:
        json.dump(actuals, f, indent=2)
        f.write("\n")


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
