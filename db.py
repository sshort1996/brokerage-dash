import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "app.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS investments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    ticker TEXT NOT NULL,
    type TEXT NOT NULL,
    account TEXT NOT NULL,
    notes TEXT,
    shares REAL,
    price_eur REAL,
    price_usd REAL,
    total_eur REAL,
    total_usd REAL,
    amount_eur REAL,
    amount_usd REAL
);

CREATE TABLE IF NOT EXISTS strategy_buckets (
    key TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    monthly_amount REAL NOT NULL,
    rate_low REAL NOT NULL,
    rate_average REAL NOT NULL,
    rate_high REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS tax_settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    cgt_rate REAL NOT NULL,
    cgt_annual_exemption REAL NOT NULL,
    exit_tax_rate REAL NOT NULL,
    deemed_disposal_years INTEGER NOT NULL,
    default_asset_class TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS asset_classes (
    ticker TEXT PRIMARY KEY,
    asset_class TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS budget_categories (
    key TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    type TEXT NOT NULL,
    monthly_target REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS budget_actuals (
    month TEXT NOT NULL,
    category_key TEXT NOT NULL,
    amount REAL NOT NULL,
    PRIMARY KEY (month, category_key)
);
"""

# Fallback defaults, used only to seed a brand-new database that has no prior
# JSON files to migrate from (e.g. a fresh clone). Mirrors what the JSON seed
# files used to contain.
DEFAULT_STRATEGY_BUCKETS = [
    ("cash_savings", "Cash Savings", 750.0, 0.03, 0.03, 0.03),
    ("index_etfs", "Index ETFs", 150.0, 0.10, 0.12, 0.14),
    ("stocks", "Individual Stocks", 100.0, 0.05, 0.15, 0.25),
]

DEFAULT_TAX_SETTINGS = (0.33, 1270.0, 0.41, 8, "stock")

DEFAULT_BUDGET_CATEGORIES = [
    ("income", "Income", "income", 3500.0),
    ("home_property", "Home & Property", "expense", 1200.0),
    ("shopping", "Shopping", "expense", 200.0),
    ("leisure", "Leisure", "expense", 150.0),
    ("groceries", "Groceries", "expense", 400.0),
    ("transport", "Transport", "expense", 120.0),
    ("health_beauty", "Health & Beauty", "expense", 80.0),
    ("other_expenses", "Other Expenses", "expense", 100.0),
    ("financial_services", "Financial Services", "expense", 50.0),
]


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Creates the schema if it doesn't exist, then seeds default rows into
    any table that's still empty — so a fresh clone with no prior JSON data
    works immediately. Safe to call on every app startup."""
    conn = get_connection()
    try:
        conn.executescript(SCHEMA)

        if conn.execute("SELECT COUNT(*) FROM strategy_buckets").fetchone()[0] == 0:
            conn.executemany(
                "INSERT INTO strategy_buckets (key, label, monthly_amount, rate_low, rate_average, rate_high) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                DEFAULT_STRATEGY_BUCKETS,
            )

        if conn.execute("SELECT COUNT(*) FROM tax_settings").fetchone()[0] == 0:
            conn.execute(
                "INSERT INTO tax_settings (id, cgt_rate, cgt_annual_exemption, exit_tax_rate, "
                "deemed_disposal_years, default_asset_class) VALUES (1, ?, ?, ?, ?, ?)",
                DEFAULT_TAX_SETTINGS,
            )

        if conn.execute("SELECT COUNT(*) FROM budget_categories").fetchone()[0] == 0:
            conn.executemany(
                "INSERT INTO budget_categories (key, label, type, monthly_target) VALUES (?, ?, ?, ?)",
                DEFAULT_BUDGET_CATEGORIES,
            )

        conn.commit()
    finally:
        conn.close()
