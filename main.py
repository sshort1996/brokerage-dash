from flask import Flask, jsonify, render_template, request

from analytics import (
    annotate_transactions_display,
    cash_balance,
    compute_tax_summary,
    find_investment,
    load_investments,
    load_strategy,
    load_tax_settings,
    next_investment_id,
    plan_liquidity_sale,
    portfolio_history,
    portfolio_summary,
    project_strategy,
    save_investments,
    save_strategy,
    save_tax_settings,
    summarize_holdings,
)


def _parse_optional_float(payload, key):
    raw = payload.get(key)
    if raw is None or raw == "":
        return None
    return float(raw)

app = Flask(__name__)


def _clean_txn_payload(payload):
    date = str(payload.get("date", "")).strip()
    ticker = str(payload.get("ticker", "")).strip().upper()
    txn_type = str(payload.get("type", "")).strip().lower()
    account = str(payload.get("account", "")).strip()
    notes = str(payload.get("notes", "")).strip()

    if not date:
        raise ValueError("date is required")
    if txn_type not in ("buy", "sell", "dividend", "deposit", "withdrawal"):
        raise ValueError("type must be buy, sell, dividend, deposit, or withdrawal")
    if txn_type in ("buy", "sell", "dividend") and not ticker:
        raise ValueError("ticker is required")
    if not account:
        raise ValueError("account is required")

    # Deposits/withdrawals move cash, not a specific holding — group them under
    # a synthetic "Cash" ticker so they never show up in the tax settings'
    # per-ticker asset-class list, which is only meaningful for real holdings.
    txn = {
        "date": date,
        "ticker": ticker if txn_type in ("buy", "sell", "dividend") else "Cash",
        "type": txn_type,
        "account": account,
    }
    if notes:
        txn["notes"] = notes

    if txn_type in ("dividend", "deposit", "withdrawal"):
        amount_eur = _parse_optional_float(payload, "amount_eur")
        amount_usd = _parse_optional_float(payload, "amount_usd")
        if amount_eur is None and amount_usd is None:
            raise ValueError("provide at least one of amount_eur or amount_usd")
        if amount_eur is not None and amount_eur <= 0:
            raise ValueError("EUR amount must be greater than 0 when provided")
        if amount_usd is not None and amount_usd <= 0:
            raise ValueError("USD amount must be greater than 0 when provided")
        txn["shares"] = 0
        txn["amount_eur"] = amount_eur
        txn["amount_usd"] = amount_usd
    else:
        shares = float(payload.get("shares", 0))
        price_eur = _parse_optional_float(payload, "price_eur")
        price_usd = _parse_optional_float(payload, "price_usd")
        if shares <= 0:
            raise ValueError("shares must be greater than 0")
        if price_eur is None and price_usd is None:
            raise ValueError("provide at least one of price_eur or price_usd")
        if price_eur is not None and price_eur <= 0:
            raise ValueError("EUR price must be greater than 0 when provided")
        if price_usd is not None and price_usd <= 0:
            raise ValueError("USD price must be greater than 0 when provided")
        txn["shares"] = shares
        txn["price_eur"] = price_eur
        txn["price_usd"] = price_usd
        # Derived from shares x price on every save, so it can never drift out of sync.
        # Left null when the corresponding price itself is null (rather than baking
        # in a possibly-inferred rate as if it were user-entered).
        txn["total_eur"] = round(shares * price_eur, 2) if price_eur is not None else None
        txn["total_usd"] = round(shares * price_usd, 2) if price_usd is not None else None

    return txn


@app.route("/")
def dashboard():
    investments = load_investments()
    holdings = summarize_holdings(investments)
    summary = portfolio_summary(holdings)
    tax_settings = load_tax_settings()
    history = portfolio_history(investments, tax_settings)
    liquid_cash = cash_balance(investments)
    transactions = annotate_transactions_display(
        sorted(investments, key=lambda t: (t["date"], t["id"]), reverse=True)
    )
    strategy = load_strategy()
    tax_summary = compute_tax_summary(investments, holdings, tax_settings)
    tickers = sorted({t["ticker"] for t in investments if t["type"] in ("buy", "sell", "dividend")})
    unresolved_tickers = sorted(t for t, h in holdings.items() if h["has_unresolved_currency"])
    return render_template(
        "index.html",
        holdings=holdings,
        summary=summary,
        history=history,
        liquid_cash=liquid_cash,
        transactions=transactions,
        strategy=strategy,
        tax_settings=tax_settings,
        tax_summary=tax_summary,
        tickers=tickers,
        unresolved_tickers=unresolved_tickers,
    )


@app.route("/api/investments", methods=["GET", "POST"])
def api_investments():
    if request.method == "GET":
        return jsonify(load_investments())

    payload = request.get_json(force=True) or {}
    try:
        txn = _clean_txn_payload(payload)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    investments = load_investments()
    txn["id"] = next_investment_id(investments)
    investments.append(txn)
    save_investments(investments)
    return jsonify(txn), 201


@app.route("/api/investments/<int:txn_id>", methods=["PUT", "DELETE"])
def api_investment_detail(txn_id):
    investments = load_investments()
    existing = find_investment(investments, txn_id)
    if existing is None:
        return jsonify({"error": "transaction not found"}), 404

    if request.method == "DELETE":
        investments = [t for t in investments if t["id"] != txn_id]
        save_investments(investments)
        return jsonify({"deleted": txn_id})

    payload = request.get_json(force=True) or {}
    try:
        txn = _clean_txn_payload(payload)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    txn["id"] = txn_id
    investments = [txn if t["id"] == txn_id else t for t in investments]
    save_investments(investments)
    return jsonify(txn)


@app.route("/api/holdings")
def api_holdings():
    holdings = summarize_holdings(load_investments())
    return jsonify(holdings)


@app.route("/api/strategy", methods=["GET", "POST"])
def api_strategy():
    if request.method == "GET":
        return jsonify(load_strategy())

    payload = request.get_json(force=True) or {}
    strategy = load_strategy()
    amounts = payload.get("buckets", {})
    rates = payload.get("rates", {})

    for key, cfg in strategy["buckets"].items():
        if key in amounts:
            cfg["monthly_amount"] = max(float(amounts[key]), 0)
        if key in rates:
            for scenario in ("low", "average", "high"):
                if scenario in rates[key]:
                    cfg["rates"][scenario] = float(rates[key][scenario])

    strategy["monthly_total"] = sum(cfg["monthly_amount"] for cfg in strategy["buckets"].values())
    save_strategy(strategy)
    return jsonify(strategy)


@app.route("/api/tax_summary")
def api_tax_summary():
    investments = load_investments()
    holdings = summarize_holdings(investments)
    tax_settings = load_tax_settings()
    return jsonify(compute_tax_summary(investments, holdings, tax_settings))


@app.route("/api/liquidity_plan", methods=["POST"])
def api_liquidity_plan():
    payload = request.get_json(force=True) or {}
    target_date = str(payload.get("date", "")).strip()
    try:
        target_amount = float(payload.get("amount", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "amount must be a number"}), 400

    if not target_date:
        return jsonify({"error": "date is required"}), 400
    if target_amount <= 0:
        return jsonify({"error": "amount must be greater than 0"}), 400

    investments = load_investments()
    holdings = summarize_holdings(investments)
    tax_settings = load_tax_settings()
    plan = plan_liquidity_sale(investments, holdings, tax_settings, target_date, target_amount)
    return jsonify(plan)


@app.route("/api/tax_settings", methods=["GET", "POST"])
def api_tax_settings():
    if request.method == "GET":
        return jsonify(load_tax_settings())

    payload = request.get_json(force=True) or {}
    settings = load_tax_settings()

    if "cgt_rate" in payload:
        settings["cgt_rate"] = max(float(payload["cgt_rate"]), 0)
    if "cgt_annual_exemption" in payload:
        settings["cgt_annual_exemption"] = max(float(payload["cgt_annual_exemption"]), 0)
    if "exit_tax_rate" in payload:
        settings["exit_tax_rate"] = max(float(payload["exit_tax_rate"]), 0)
    if "deemed_disposal_years" in payload:
        settings["deemed_disposal_years"] = max(int(payload["deemed_disposal_years"]), 1)
    if "asset_classes" in payload:
        settings.setdefault("asset_classes", {})
        for ticker, cls in payload["asset_classes"].items():
            if cls in ("etf", "stock"):
                settings["asset_classes"][str(ticker).strip().upper()] = cls

    save_tax_settings(settings)
    return jsonify(settings)


@app.route("/api/strategy_projection", methods=["POST"])
def api_strategy_projection():
    payload = request.get_json(force=True) or {}
    strategy = load_strategy()
    payload_rates = payload.get("rates", {})

    bucket_amounts = {}
    bucket_rates = {}
    for key, cfg in strategy["buckets"].items():
        raw_amount = payload.get("buckets", {}).get(key, cfg["monthly_amount"])
        bucket_amounts[key] = max(float(raw_amount), 0)

        overrides = payload_rates.get(key, {})
        bucket_rates[key] = {
            scenario: float(overrides.get(scenario, cfg["rates"][scenario]))
            for scenario in ("low", "average", "high")
        }

    years = float(payload.get("years", 20))

    return jsonify(project_strategy(bucket_amounts, bucket_rates, years))


if __name__ == "__main__":
    app.run(debug=True)
