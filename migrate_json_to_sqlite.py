"""One-time migration: import existing data/*.json files into data/app.db.

Run this once, manually, in any environment that has real JSON data to carry
over (the Lightsail instance). Not needed for a brand-new environment — plain
app startup (db.init_db()) already seeds sensible defaults for those.

Reuses the real save_*() functions rather than duplicating persistence logic,
so the data ends up exactly as it would via the normal app code path.
"""
import json
from pathlib import Path

from budget import save_budget_actuals, save_budget_categories
from analytics import save_investments, save_strategy, save_tax_settings
from db import init_db

DATA_DIR = Path(__file__).parent / "data"


def _load_json(name):
    path = DATA_DIR / name
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def main():
    init_db()

    investments = _load_json("investments.json")
    if investments is not None:
        save_investments(investments)
        print(f"Migrated {len(investments)} investment transactions.")
    else:
        print("No investments.json found, skipping.")

    strategy = _load_json("strategy.json")
    if strategy is not None:
        save_strategy(strategy)
        print("Migrated strategy buckets.")
    else:
        print("No strategy.json found, skipping.")

    tax_settings = _load_json("tax_settings.json")
    if tax_settings is not None:
        save_tax_settings(tax_settings)
        print("Migrated tax settings.")
    else:
        print("No tax_settings.json found, skipping.")

    budget = _load_json("budget.json")
    if budget is not None:
        save_budget_categories(budget["categories"])
        print("Migrated budget categories.")
    else:
        print("No budget.json found, skipping.")

    budget_actuals = _load_json("budget_actuals.json")
    if budget_actuals is not None:
        save_budget_actuals(budget_actuals)
        print(f"Migrated budget actuals for {len(budget_actuals)} month(s).")
    else:
        print("No budget_actuals.json found, skipping.")

    print("Migration complete.")


if __name__ == "__main__":
    main()
