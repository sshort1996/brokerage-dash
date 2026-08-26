import json
from collections import defaultdict, deque
from datetime import date
from pathlib import Path

DATA_PATH = Path(__file__).parent / "data" / "investments.json"
STRATEGY_PATH = Path(__file__).parent / "data" / "strategy.json"
TAX_SETTINGS_PATH = Path(__file__).parent / "data" / "tax_settings.json"


def load_investments():
    with open(DATA_PATH) as f:
        return json.load(f)


def save_investments(investments):
    investments = sorted(investments, key=lambda t: (t["date"], t["id"]))
    with open(DATA_PATH, "w") as f:
        json.dump(investments, f, indent=2)
        f.write("\n")


def next_investment_id(investments):
    return max((t["id"] for t in investments), default=0) + 1


def find_investment(investments, txn_id):
    return next((t for t in investments if t["id"] == txn_id), None)


def load_strategy():
    with open(STRATEGY_PATH) as f:
        return json.load(f)


def save_strategy(strategy):
    with open(STRATEGY_PATH, "w") as f:
        json.dump(strategy, f, indent=2)
        f.write("\n")


def _txn_currency_pair(txn):
    """The (eur, usd) per-share values a transaction carries — either may be None.
    Falls back to total_eur/total_usd divided by shares when the per-share price
    wasn't set directly but the total was — the total is just as much a "known"
    value and shouldn't be ignored in favor of inferring a rate from elsewhere."""
    if txn["type"] in ("dividend", "deposit", "withdrawal"):
        return txn.get("amount_eur"), txn.get("amount_usd")

    eur, usd = txn.get("price_eur"), txn.get("price_usd")
    shares = txn.get("shares")
    if shares:
        if eur is None and txn.get("total_eur") is not None:
            eur = txn["total_eur"] / shares
        if usd is None and txn.get("total_usd") is not None:
            usd = txn["total_usd"] / shares
    return eur, usd


def known_fx_rates(investments):
    """[(date, eur_per_usd), ...] from every transaction where both currencies were
    entered directly — the pool of "known" rates used to infer any missing side."""
    rates = []
    for txn in investments:
        eur, usd = _txn_currency_pair(txn)
        if eur is not None and usd is not None and usd != 0:
            rates.append((txn["date"], eur / usd))
    return rates


def _nearest_fx_rate(known_rates, target_date):
    """The known rate whose transaction date is closest to target_date — rates
    drift over time, so "nearest" is more accurate than "most recent overall"."""
    if not known_rates:
        return None
    target = date.fromisoformat(target_date)
    return min(known_rates, key=lambda r: abs((date.fromisoformat(r[0]) - target).days))[1]


def resolve_currency_pair(txn, known_rates):
    """Resolves a transaction's EUR/USD values, inferring whichever side is None
    from the nearest known EUR-per-USD rate. If no rate exists yet to infer from
    (no transaction anywhere has both currencies filled in), the missing side is
    left unresolved rather than silently defaulting to a number — 0.0 would look
    like a real, if oddly cheap, gain/loss instead of "we don't actually know"."""
    eur, usd = _txn_currency_pair(txn)
    eur_inferred = usd_inferred = False
    eur_unresolved = usd_unresolved = False

    if eur is None or usd is None:
        rate = _nearest_fx_rate(known_rates, txn["date"])
        if eur is None and usd is not None:
            if rate:
                eur = round(usd * rate, 4)
                eur_inferred = True
            else:
                eur_unresolved = True
        if usd is None and eur is not None:
            if rate:
                usd = round(eur / rate, 4)
                usd_inferred = True
            else:
                usd_unresolved = True

    return {
        "eur": eur if eur is not None else 0.0,
        "usd": usd if usd is not None else 0.0,
        "eur_inferred": eur_inferred,
        "usd_inferred": usd_inferred,
        "eur_unresolved": eur_unresolved,
        "usd_unresolved": usd_unresolved,
    }


def annotate_transactions_display(investments):
    """Each transaction plus its resolved display_eur/display_usd (possibly
    FX-inferred), and flags for whether a side was inferred or is unresolved."""
    known_rates = known_fx_rates(investments)
    annotated = []
    for txn in investments:
        resolved = resolve_currency_pair(txn, known_rates)
        t = dict(txn)
        t["display_eur"] = resolved["eur"]
        t["display_usd"] = resolved["usd"]
        t["eur_inferred"] = resolved["eur_inferred"]
        t["usd_inferred"] = resolved["usd_inferred"]
        t["eur_unresolved"] = resolved["eur_unresolved"]
        t["usd_unresolved"] = resolved["usd_unresolved"]
        annotated.append(t)
    return annotated


def summarize_holdings(investments):
    """All money is normalized to EUR for aggregation, using the price_eur/amount_eur
    the user entered directly on each transaction — or, if one side was left null,
    the value inferred from the nearest transaction where both currencies are known.
    If no such transaction exists anywhere yet, that ticker's cost basis is flagged
    incomplete rather than silently computed as if the missing price were 0."""
    holdings = defaultdict(lambda: {
        "shares": 0.0, "cost_basis": 0.0, "last_price": 0.0, "dividends": 0.0, "has_unresolved_currency": False,
    })
    known_rates = known_fx_rates(investments)

    for txn in sorted(investments, key=lambda t: t["date"]):
        h = holdings[txn["ticker"]]
        resolved = resolve_currency_pair(txn, known_rates)
        eur = resolved["eur"]
        if resolved["eur_unresolved"]:
            h["has_unresolved_currency"] = True

        if txn["type"] == "buy":
            h["shares"] += txn["shares"]
            h["cost_basis"] += txn["shares"] * eur
            h["last_price"] = eur
        elif txn["type"] == "sell":
            h["shares"] -= txn["shares"]
            h["cost_basis"] -= txn["shares"] * eur
            h["last_price"] = eur
        elif txn["type"] == "dividend":
            h["dividends"] += eur

    result = {}
    for ticker, h in holdings.items():
        if h["shares"] <= 0:
            continue
        market_value = h["shares"] * h["last_price"]
        result[ticker] = {
            "shares": round(h["shares"], 4),
            "cost_basis": round(h["cost_basis"], 2),
            "last_price": h["last_price"],
            "market_value": round(market_value, 2),
            "has_unresolved_currency": h["has_unresolved_currency"],
            "gain_loss": round(market_value - h["cost_basis"], 2),
            "dividends": round(h["dividends"], 2),
        }
    return result


def cash_balances_by_account(investments):
    """Uninvested cash in EUR, kept separate per account — money deposited into
    a savings account isn't available to cover a buy made from a brokerage
    account, so those two ledgers shouldn't net against each other. Buys/sells
    use the resolved per-share EUR price x shares; deposits/withdrawals/
    dividends carry their EUR amount directly (inferred from the nearest known
    rate if only the USD side was entered, same as everywhere else)."""
    known_rates = known_fx_rates(investments)
    balances = defaultdict(float)
    for txn in sorted(investments, key=lambda t: t["date"]):
        eur = resolve_currency_pair(txn, known_rates)["eur"]
        account = txn["account"]
        if txn["type"] == "buy":
            balances[account] -= txn["shares"] * eur
        elif txn["type"] == "sell":
            balances[account] += txn["shares"] * eur
        elif txn["type"] in ("dividend", "deposit"):
            balances[account] += eur
        elif txn["type"] == "withdrawal":
            balances[account] -= eur
    return {account: round(bal, 2) for account, bal in balances.items()}


def cash_balance(investments):
    """Total liquid cash across all accounts. Each account's balance is floored
    at 0 before summing — a negative balance just means a buy/sell in that
    account isn't backed by a recorded deposit there (incomplete data), not a
    real debt that should eat into cash actually sitting in a different
    account."""
    return round(sum(max(0.0, b) for b in cash_balances_by_account(investments).values()), 2)


def portfolio_history(investments, tax_settings):
    """Cumulative portfolio cost basis / market value snapshotted at each date a
    transaction occurred, plus a breakdown into the three "buckets" used in the
    Monthly Strategy section (cash savings, index ETFs, individual stocks) —
    cash from the liquid cash ledger, holdings split by each ticker's tax
    asset_class. Market value uses the same "last transaction price" convention
    as summarize_holdings (no live quotes), so this tracks growth from trades
    and price updates you've entered — not day-to-day price movement."""
    dates = sorted({t["date"] for t in investments})
    history = []
    for d in dates:
        txns_so_far = [t for t in investments if t["date"] <= d]
        holdings = summarize_holdings(txns_so_far)
        summary = portfolio_summary(holdings)
        cash = cash_balance(txns_so_far)
        etf_value = sum(
            h["market_value"] for ticker, h in holdings.items()
            if asset_class(ticker, tax_settings) == "etf"
        )
        stock_value = sum(
            h["market_value"] for ticker, h in holdings.items()
            if asset_class(ticker, tax_settings) == "stock"
        )
        history.append({
            "date": d,
            "cost_basis": summary["total_cost"],
            "market_value": summary["total_value"],
            "gain_loss": summary["total_gain_loss"],
            "cash": cash,
            "etf_value": round(etf_value, 2),
            "stock_value": round(stock_value, 2),
            "total_portfolio_value": round(cash + etf_value + stock_value, 2),
        })
    return history


def portfolio_summary(holdings):
    total_cost = sum(h["cost_basis"] for h in holdings.values())
    total_value = sum(h["market_value"] for h in holdings.values())
    total_dividends = sum(h["dividends"] for h in holdings.values())
    return {
        "total_cost": round(total_cost, 2),
        "total_value": round(total_value, 2),
        "total_gain_loss": round(total_value - total_cost, 2),
        "total_dividends": round(total_dividends, 2),
        "holding_count": len(holdings),
    }


def _future_value(monthly_amount, annual_rate, months):
    if months <= 0:
        return 0.0
    monthly_rate = annual_rate / 12
    if monthly_rate == 0:
        return monthly_amount * months
    return monthly_amount * (((1 + monthly_rate) ** months - 1) / monthly_rate)


def project_strategy(bucket_amounts, bucket_rates, years):
    """Project growth of a fixed monthly savings/investment split under three
    return scenarios (low / average / high), one year at a time.

    bucket_amounts: {bucket_key: monthly_amount}
    bucket_rates: {bucket_key: {"low": rate, "average": rate, "high": rate}}
    """
    scenarios = ["low", "average", "high"]
    years_int = int(round(years))
    monthly_total = sum(bucket_amounts.values())

    timeline = []
    for year in range(0, years_int + 1):
        months = year * 12
        point = {"year": year, "contributed": round(monthly_total * months, 2)}
        for scenario in scenarios:
            total_fv = sum(
                _future_value(amount, bucket_rates.get(bucket, {}).get(scenario, 0), months)
                for bucket, amount in bucket_amounts.items()
            )
            point[scenario] = round(total_fv, 2)
        timeline.append(point)

    return {
        "years": years_int,
        "monthly_total": round(monthly_total, 2),
        "timeline": timeline,
        "final": timeline[-1],
    }


# --- Irish tax estimate: CGT (stocks) + deemed disposal / exit tax (ETFs) ---
#
# Simplification: share lots are matched FIFO. Real Irish CGT share identification
# rules (same-day acquisitions first, then a 4-week "bed and breakfast" rule, then
# FIFO) are not modeled. This is an estimate for planning purposes, not tax advice.


def load_tax_settings():
    with open(TAX_SETTINGS_PATH) as f:
        return json.load(f)


def save_tax_settings(settings):
    with open(TAX_SETTINGS_PATH, "w") as f:
        json.dump(settings, f, indent=2)
        f.write("\n")


def asset_class(ticker, tax_settings):
    return tax_settings.get("asset_classes", {}).get(ticker, tax_settings.get("default_asset_class", "stock"))


def build_lots(investments):
    """FIFO share lots per ticker from buy/sell transactions (EUR cost basis).

    Returns (open_lots, realized_sales):
      open_lots: [{ticker, date, shares, cost_per_share}] — unsold shares remaining
      realized_sales: [{ticker, buy_date, sell_date, shares, cost_per_share,
                         proceeds_per_share, gain}] — one entry per lot matched to a sale
    """
    lots_by_ticker = defaultdict(deque)
    realized = []
    known_rates = known_fx_rates(investments)

    for txn in sorted(investments, key=lambda t: t["date"]):
        ticker = txn["ticker"]
        eur = resolve_currency_pair(txn, known_rates)["eur"]
        if txn["type"] == "buy":
            lots_by_ticker[ticker].append({
                "date": txn["date"],
                "shares": txn["shares"],
                "cost_per_share": eur,
            })
        elif txn["type"] == "sell":
            shares_to_sell = txn["shares"]
            proceeds_per_share = eur
            queue = lots_by_ticker[ticker]
            while shares_to_sell > 1e-9 and queue:
                lot = queue[0]
                matched = min(lot["shares"], shares_to_sell)
                realized.append({
                    "ticker": ticker,
                    "buy_date": lot["date"],
                    "sell_date": txn["date"],
                    "shares": matched,
                    "cost_per_share": lot["cost_per_share"],
                    "proceeds_per_share": proceeds_per_share,
                    "gain": matched * (proceeds_per_share - lot["cost_per_share"]),
                })
                lot["shares"] -= matched
                shares_to_sell -= matched
                if lot["shares"] <= 1e-9:
                    queue.popleft()

    open_lots = [
        {"ticker": ticker, **lot}
        for ticker, queue in lots_by_ticker.items()
        for lot in queue
        if lot["shares"] > 1e-9
    ]

    return open_lots, realized


def _cgt_summary(open_lots, realized, holdings, tax_settings, tax_year):
    rate = tax_settings.get("cgt_rate", 0.33)
    exemption = tax_settings.get("cgt_annual_exemption", 1270)

    realized_gain_ytd = sum(
        r["gain"] for r in realized
        if asset_class(r["ticker"], tax_settings) == "stock" and r["sell_date"].startswith(str(tax_year))
    )
    net_gain = max(0.0, realized_gain_ytd)
    exemption_used = min(exemption, net_gain)
    exemption_remaining = max(0.0, exemption - net_gain)
    tax_due = round(max(0.0, net_gain - exemption) * rate, 2)

    candidates = []
    for lot in open_lots:
        if asset_class(lot["ticker"], tax_settings) != "stock":
            continue
        current_price = holdings.get(lot["ticker"], {}).get("last_price", 0)
        gain_per_share = current_price - lot["cost_per_share"]
        if gain_per_share <= 0:
            continue
        candidates.append({**lot, "current_price": current_price, "gain_per_share": gain_per_share})

    # Sell the highest gain-per-share lots first: reaches the allowance target
    # while selling the fewest shares, leaving the rest of the position intact.
    candidates.sort(key=lambda c: c["gain_per_share"], reverse=True)

    suggestions = []
    remaining = exemption_remaining
    for c in candidates:
        if remaining <= 1e-9:
            break
        shares_to_sell = min(c["shares"], remaining / c["gain_per_share"])
        if shares_to_sell <= 1e-9:
            continue
        gain = shares_to_sell * c["gain_per_share"]
        suggestions.append({
            "ticker": c["ticker"],
            "buy_date": c["date"],
            "shares_to_sell": round(shares_to_sell, 4),
            "gain_per_share": round(c["gain_per_share"], 4),
            "estimated_gain": round(gain, 2),
            "estimated_proceeds": round(shares_to_sell * c["current_price"], 2),
        })
        remaining -= gain

    return {
        "rate": rate,
        "annual_exemption": exemption,
        "realized_gain_ytd": round(realized_gain_ytd, 2),
        "exemption_used": round(exemption_used, 2),
        "exemption_remaining": round(exemption_remaining, 2),
        "tax_due_ytd": tax_due,
        "suggested_sales": suggestions,
    }


def _exit_tax_summary(open_lots, holdings, tax_settings, tax_year):
    rate = tax_settings.get("exit_tax_rate", 0.41)
    years = tax_settings.get("deemed_disposal_years", 8)
    today = date.today()

    schedule = []
    for lot in open_lots:
        if asset_class(lot["ticker"], tax_settings) != "etf":
            continue

        buy_date = date.fromisoformat(lot["date"])
        try:
            deemed_date = buy_date.replace(year=buy_date.year + years)
        except ValueError:
            deemed_date = buy_date.replace(month=2, day=28, year=buy_date.year + years)

        current_price = holdings.get(lot["ticker"], {}).get("last_price", 0)
        gain_per_share = max(0.0, current_price - lot["cost_per_share"])
        gain = gain_per_share * lot["shares"]

        schedule.append({
            "ticker": lot["ticker"],
            "buy_date": lot["date"],
            "shares": round(lot["shares"], 4),
            "deemed_disposal_date": deemed_date.isoformat(),
            "estimated_gain": round(gain, 2),
            "estimated_tax": round(gain * rate, 2),
            "overdue": deemed_date <= today,
            "due_this_year": deemed_date.year == tax_year,
        })

    schedule.sort(key=lambda s: s["deemed_disposal_date"])
    tax_due_this_year = sum(s["estimated_tax"] for s in schedule if s["overdue"] or s["due_this_year"])

    return {
        "rate": rate,
        "deemed_disposal_years": years,
        "schedule": schedule,
        "tax_due_this_year": round(tax_due_this_year, 2),
    }


def compute_tax_summary(investments, holdings, tax_settings, tax_year=None):
    if tax_year is None:
        tax_year = date.today().year

    open_lots, realized = build_lots(investments)
    cgt = _cgt_summary(open_lots, realized, holdings, tax_settings, tax_year)
    exit_tax = _exit_tax_summary(open_lots, holdings, tax_settings, tax_year)

    return {
        "tax_year": tax_year,
        "cgt": cgt,
        "exit_tax": exit_tax,
        "total_tax_due_estimate": round(cgt["tax_due_ytd"] + exit_tax["tax_due_this_year"], 2),
    }


def plan_liquidity_sale(investments, holdings, tax_settings, target_date, target_amount):
    """A simplified, tax-aware plan for raising target_amount (EUR) of cash on top
    of what's already sitting uninvested, by target_date. Greedily sells the
    lowest (or most negative) gain-per-share lots first, across both stock and
    ETF holdings, since those add proceeds while realizing the least taxable
    gain — a reasonable heuristic for minimizing tax, not a true optimizer (it
    doesn't weigh stock's exemption advantage over ETF's flat rate, and it uses
    each ticker's last transaction price throughout rather than projecting a
    future price — same "not a live quote" convention as the rest of the app).
    The CGT exemption is assumed fully available unless target_date falls in the
    current tax year, in which case whatever this year's real sales have already
    used is carried in. Estimate for planning purposes, not tax advice."""
    current_cash = cash_balance(investments)
    shortfall = round(target_amount - current_cash, 2)

    if shortfall <= 0:
        return {
            "current_cash": current_cash,
            "target_amount": round(target_amount, 2),
            "target_date": target_date,
            "shortfall": 0.0,
            "sufficient_without_selling": True,
            "insufficient_holdings": False,
            "sales": [],
            "gross_proceeds": 0.0,
            "estimated_tax": 0.0,
            "net_proceeds": 0.0,
            "final_cash": current_cash,
        }

    tax_year = date.fromisoformat(target_date).year
    open_lots, realized = build_lots(investments)

    rate_cgt = tax_settings.get("cgt_rate", 0.33)
    exemption = tax_settings.get("cgt_annual_exemption", 1270)
    rate_exit = tax_settings.get("exit_tax_rate", 0.41)

    stock_gain_running = sum(
        r["gain"] for r in realized
        if asset_class(r["ticker"], tax_settings) == "stock" and r["sell_date"].startswith(str(tax_year))
    )

    candidates = []
    for lot in open_lots:
        current_price = holdings.get(lot["ticker"], {}).get("last_price", 0)
        candidates.append({
            **lot,
            "current_price": current_price,
            "gain_per_share": current_price - lot["cost_per_share"],
            "asset_class": asset_class(lot["ticker"], tax_settings),
        })
    candidates.sort(key=lambda c: c["gain_per_share"])

    def tax_for_stock(gain_delta):
        nonlocal stock_gain_running
        before = rate_cgt * max(0.0, stock_gain_running - exemption)
        stock_gain_running += gain_delta
        after = rate_cgt * max(0.0, stock_gain_running - exemption)
        return after - before

    sales = []
    gross_total = tax_total = net_total = 0.0

    for c in candidates:
        if net_total >= shortfall - 1e-9:
            break

        shares_available = c["shares"]
        full_gross = shares_available * c["current_price"]
        full_gain = shares_available * c["gain_per_share"]
        full_tax = tax_for_stock(full_gain) if c["asset_class"] == "stock" else rate_exit * max(0.0, full_gain)
        full_net = full_gross - full_tax

        remaining_needed = shortfall - net_total
        if full_net <= remaining_needed or full_net <= 0:
            shares_to_sell, gross, gain, tax, net = shares_available, full_gross, full_gain, full_tax, full_net
        else:
            frac = remaining_needed / full_net
            shares_to_sell = shares_available * frac
            gross = full_gross * frac
            gain = full_gain * frac
            if c["asset_class"] == "stock":
                stock_gain_running -= (full_gain - gain)  # trim the running total back to the partial sale
                tax = full_tax * frac
            else:
                tax = rate_exit * max(0.0, gain)
            net = gross - tax

        sales.append({
            "ticker": c["ticker"],
            "buy_date": c["date"],
            "shares_to_sell": round(shares_to_sell, 4),
            "current_price": round(c["current_price"], 4),
            "gross_proceeds": round(gross, 2),
            "estimated_gain": round(gain, 2),
            "estimated_tax": round(tax, 2),
            "net_proceeds": round(net, 2),
        })
        gross_total += gross
        tax_total += tax
        net_total += net

    return {
        "current_cash": current_cash,
        "target_amount": round(target_amount, 2),
        "target_date": target_date,
        "shortfall": shortfall,
        "sufficient_without_selling": False,
        "insufficient_holdings": net_total < shortfall - 1e-6,
        "sales": sales,
        "gross_proceeds": round(gross_total, 2),
        "estimated_tax": round(tax_total, 2),
        "net_proceeds": round(net_total, 2),
        "final_cash": round(current_cash + net_total, 2),
    }
