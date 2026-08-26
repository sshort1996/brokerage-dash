let strategyChart = null;
let strategyPieChart = null;
let historyChart = null;

// --- Portfolio performance over time ---

const historyDataEl = document.getElementById("portfolioHistoryData");
const historyCanvas = document.getElementById("historyChart");
if (historyDataEl && historyCanvas) {
  const history = JSON.parse(historyDataEl.textContent);
  historyChart = new Chart(historyCanvas, {
    type: "line",
    data: {
      labels: history.map((p) => p.date),
      datasets: [
        // The three Monthly-Strategy buckets, stacked so their combined shaded
        // area traces the total portfolio value (cash + ETFs + stocks) — drawn
        // first/underneath so the Market Value / Cost Basis lines sit on top.
        {
          label: "Cash Savings",
          data: history.map((p) => p.cash),
          borderColor: "#6c757d",
          backgroundColor: "rgba(108, 117, 125, 0.35)",
          fill: true,
          stack: "buckets",
          pointRadius: 0,
          borderWidth: 1,
          tension: 0.15,
        },
        {
          label: "Index ETFs",
          data: history.map((p) => p.etf_value),
          borderColor: "#20c997",
          backgroundColor: "rgba(32, 201, 151, 0.35)",
          fill: true,
          stack: "buckets",
          pointRadius: 0,
          borderWidth: 1,
          tension: 0.15,
        },
        {
          label: "Individual Stocks",
          data: history.map((p) => p.stock_value),
          borderColor: "#fd7e14",
          backgroundColor: "rgba(253, 126, 20, 0.35)",
          fill: true,
          stack: "buckets",
          pointRadius: 0,
          borderWidth: 1,
          tension: 0.15,
        },
        {
          label: "Market Value",
          data: history.map((p) => p.market_value),
          borderColor: "#0d6efd",
          backgroundColor: "transparent",
          fill: false,
          stack: "market-value",
          tension: 0.15,
        },
        {
          label: "Cost Basis",
          data: history.map((p) => p.cost_basis),
          borderColor: "#adb5bd",
          backgroundColor: "transparent",
          fill: false,
          stack: "cost-basis",
          borderDash: [4, 4],
          pointRadius: 0,
          tension: 0.15,
        },
      ],
    },
    options: {
      responsive: true,
      interaction: { mode: "index", intersect: false },
      plugins: { legend: { position: "bottom" } },
      scales: {
        y: { stacked: true, ticks: { callback: (v) => "€" + v.toLocaleString() } },
      },
    },
  });
}

// --- Transactions: add / edit / delete ---

const txnModalEl = document.getElementById("txnModal");
const txnModal = txnModalEl ? new bootstrap.Modal(txnModalEl) : null;
const txnForm = document.getElementById("txnForm");
const txnFormError = document.getElementById("txnFormError");
const txnTypeSelect = document.getElementById("txnType");

function setTxnFieldsForType(type) {
  const showSharesPrice = type === "buy" || type === "sell";
  const showTicker = type !== "deposit" && type !== "withdrawal";
  document.querySelectorAll(".txn-field-shares").forEach((el) => el.classList.toggle("d-none", !showSharesPrice));
  document.querySelectorAll(".txn-field-price").forEach((el) => el.classList.toggle("d-none", !showSharesPrice));
  document.querySelectorAll(".txn-field-amount").forEach((el) => el.classList.toggle("d-none", showSharesPrice));
  document.querySelectorAll(".txn-field-ticker").forEach((el) => el.classList.toggle("d-none", !showTicker));
}

function resetTxnForm() {
  txnForm.reset();
  document.getElementById("txnId").value = "";
  document.getElementById("txnType").value = "buy";
  setTxnFieldsForType("buy");
  txnFormError.classList.add("d-none");
  txnFormError.textContent = "";
}

function openAddTxnModal() {
  resetTxnForm();
  document.getElementById("txnModalTitle").textContent = "Add Transaction";
  txnModal.show();
}

function openEditTxnModal(txn) {
  resetTxnForm();
  document.getElementById("txnModalTitle").textContent = "Edit Transaction";
  document.getElementById("txnId").value = txn.id;
  document.getElementById("txnDate").value = txn.date;
  document.getElementById("txnTicker").value = txn.ticker;
  document.getElementById("txnType").value = txn.type;
  document.getElementById("txnAccount").value = txn.account;
  document.getElementById("txnNotes").value = txn.notes || "";
  document.getElementById("txnShares").value = txn.shares || "";
  document.getElementById("txnPriceUsd").value = txn.price_usd || "";
  document.getElementById("txnPriceEur").value = txn.price_eur || "";
  document.getElementById("txnTotalEur").value = txn.total_eur || "";
  document.getElementById("txnTotalUsd").value = txn.total_usd || "";
  document.getElementById("txnAmountUsd").value = txn.amount_usd || "";
  document.getElementById("txnAmountEur").value = txn.amount_eur || "";
  setTxnFieldsForType(txn.type);
  txnModal.show();
}

if (txnTypeSelect) {
  txnTypeSelect.addEventListener("change", () => setTxnFieldsForType(txnTypeSelect.value));
}

// "Total spent" is a pure UI helper — it just back-calculates price per share
// (total / shares) and fills that field. Nothing is stored except the price.
function recalcPriceFromTotal(totalInputId, priceInputId) {
  const total = parseFloat(document.getElementById(totalInputId).value);
  const shares = parseFloat(document.getElementById("txnShares").value);
  if (total > 0 && shares > 0) {
    document.getElementById(priceInputId).value = (total / shares).toFixed(4);
  }
}

const txnTotalEur = document.getElementById("txnTotalEur");
const txnTotalUsd = document.getElementById("txnTotalUsd");
const txnSharesInput = document.getElementById("txnShares");

if (txnTotalEur) {
  txnTotalEur.addEventListener("input", () => recalcPriceFromTotal("txnTotalEur", "txnPriceEur"));
}
if (txnTotalUsd) {
  txnTotalUsd.addEventListener("input", () => recalcPriceFromTotal("txnTotalUsd", "txnPriceUsd"));
}
if (txnSharesInput) {
  txnSharesInput.addEventListener("input", () => {
    recalcPriceFromTotal("txnTotalEur", "txnPriceEur");
    recalcPriceFromTotal("txnTotalUsd", "txnPriceUsd");
  });
}

const addTxnBtn = document.getElementById("addTxnBtn");
if (addTxnBtn) {
  addTxnBtn.addEventListener("click", openAddTxnModal);
}

document.querySelectorAll(".edit-txn-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    const row = btn.closest("tr");
    const txn = JSON.parse(row.dataset.txn);
    openEditTxnModal(txn);
  });
});

document.querySelectorAll(".delete-txn-btn").forEach((btn) => {
  btn.addEventListener("click", async () => {
    if (!confirm("Delete this transaction? This cannot be undone.")) return;
    const id = btn.dataset.id;
    const response = await fetch(`/api/investments/${id}`, { method: "DELETE" });
    if (!response.ok) {
      alert("Failed to delete transaction");
      return;
    }
    window.location.reload();
  });
});

function parseOrNull(inputId) {
  const raw = document.getElementById(inputId).value;
  if (raw === "") return null;
  const n = parseFloat(raw);
  return Number.isNaN(n) ? null : n;
}

const txnSaveBtn = document.getElementById("txnSaveBtn");
if (txnSaveBtn) {
  txnSaveBtn.addEventListener("click", async () => {
    const id = document.getElementById("txnId").value;
    const type = document.getElementById("txnType").value;

    const payload = {
      date: document.getElementById("txnDate").value,
      ticker: document.getElementById("txnTicker").value,
      type,
      account: document.getElementById("txnAccount").value,
      notes: document.getElementById("txnNotes").value,
    };

    if (type === "dividend" || type === "deposit" || type === "withdrawal") {
      payload.amount_usd = parseOrNull("txnAmountUsd");
      payload.amount_eur = parseOrNull("txnAmountEur");
    } else {
      payload.shares = parseFloat(document.getElementById("txnShares").value) || 0;
      payload.price_usd = parseOrNull("txnPriceUsd");
      payload.price_eur = parseOrNull("txnPriceEur");
    }

    const url = id ? `/api/investments/${id}` : "/api/investments";
    const method = id ? "PUT" : "POST";

    const response = await fetch(url, {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      txnFormError.textContent = err.error || "Failed to save transaction";
      txnFormError.classList.remove("d-none");
      return;
    }

    window.location.reload();
  });
}

// --- Liquidity planner ---

const liqPlanBtn = document.getElementById("liqPlanBtn");
const liqResults = document.getElementById("liqPlanResults");
const liqError = document.getElementById("liqPlanError");

function fmtEur(n) {
  return "€" + Number(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function renderLiquidityPlan(plan) {
  if (plan.sufficient_without_selling) {
    liqResults.innerHTML = `
      <div class="alert alert-success small mb-0">
        You already have ${fmtEur(plan.current_cash)} in liquid cash — no sales needed to reach
        ${fmtEur(plan.target_amount)} by ${plan.target_date}.
      </div>`;
    return;
  }

  const rows = plan.sales.map((s) => `
    <tr>
      <td>${s.ticker}</td>
      <td>${s.buy_date}</td>
      <td class="text-end">${s.shares_to_sell.toFixed(3)}</td>
      <td class="text-end">${fmtEur(s.gross_proceeds)}</td>
      <td class="text-end">${fmtEur(s.estimated_gain)}</td>
      <td class="text-end text-danger">${fmtEur(s.estimated_tax)}</td>
      <td class="text-end">${fmtEur(s.net_proceeds)}</td>
    </tr>`).join("");

  const shortageNotice = plan.insufficient_holdings
    ? `<div class="alert alert-warning small">Not enough sellable holdings to fully close the gap — this sells
       everything available below, raising ${fmtEur(plan.net_proceeds)} net instead of the full
       ${fmtEur(plan.shortfall)} shortfall.</div>`
    : "";

  liqResults.innerHTML = `
    ${shortageNotice}
    <div class="row g-3 mb-3 text-center">
      <div class="col-6 col-md-3">
        <div class="text-muted small">Shortfall to raise</div>
        <div class="fw-semibold">${fmtEur(plan.shortfall)}</div>
      </div>
      <div class="col-6 col-md-3">
        <div class="text-muted small">Gross proceeds</div>
        <div class="fw-semibold">${fmtEur(plan.gross_proceeds)}</div>
      </div>
      <div class="col-6 col-md-3">
        <div class="text-muted small">Cash lost to tax</div>
        <div class="fw-semibold text-danger">${fmtEur(plan.estimated_tax)}</div>
      </div>
      <div class="col-6 col-md-3">
        <div class="text-muted small">Cash after selling</div>
        <div class="fw-semibold">${fmtEur(plan.final_cash)}</div>
      </div>
    </div>
    <div class="table-responsive">
      <table class="table table-sm">
        <thead>
          <tr>
            <th>Ticker</th>
            <th>Lot bought</th>
            <th class="text-end">Shares to sell</th>
            <th class="text-end">Gross proceeds</th>
            <th class="text-end">Est. gain</th>
            <th class="text-end">Est. tax</th>
            <th class="text-end">Net proceeds</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
}

if (liqPlanBtn) {
  liqPlanBtn.addEventListener("click", async () => {
    liqError.classList.add("d-none");
    liqResults.innerHTML = "";

    const date = document.getElementById("liqTargetDate").value;
    const amount = parseFloat(document.getElementById("liqTargetAmount").value);

    if (!date || !(amount > 0)) {
      liqError.textContent = "Enter a target date and a positive amount.";
      liqError.classList.remove("d-none");
      return;
    }

    const response = await fetch("/api/liquidity_plan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ date, amount }),
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      liqError.textContent = err.error || "Failed to compute plan";
      liqError.classList.remove("d-none");
      return;
    }

    renderLiquidityPlan(await response.json());
  });
}

// --- Tax settings ---

const taxSettingsModalEl = document.getElementById("taxSettingsModal");
const taxSettingsModal = taxSettingsModalEl ? new bootstrap.Modal(taxSettingsModalEl) : null;
const taxSettingsBtn = document.getElementById("taxSettingsBtn");
const taxSettingsError = document.getElementById("taxSettingsError");

if (taxSettingsBtn) {
  taxSettingsBtn.addEventListener("click", () => {
    taxSettingsError.classList.add("d-none");
    taxSettingsModal.show();
  });
}

const taxSettingsSaveBtn = document.getElementById("taxSettingsSaveBtn");
if (taxSettingsSaveBtn) {
  taxSettingsSaveBtn.addEventListener("click", async () => {
    const assetClasses = {};
    document.querySelectorAll(".asset-class-select").forEach((el) => {
      assetClasses[el.dataset.ticker] = el.value;
    });

    const payload = {
      cgt_rate: (parseFloat(document.getElementById("taxCgtRate").value) || 0) / 100,
      cgt_annual_exemption: parseFloat(document.getElementById("taxCgtExemption").value) || 0,
      exit_tax_rate: (parseFloat(document.getElementById("taxExitRate").value) || 0) / 100,
      deemed_disposal_years: parseInt(document.getElementById("taxDeemedYears").value, 10) || 8,
      asset_classes: assetClasses,
    };

    const response = await fetch("/api/tax_settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      taxSettingsError.textContent = "Failed to save tax settings";
      taxSettingsError.classList.remove("d-none");
      return;
    }

    window.location.reload();
  });
}

// --- Monthly strategy: bucket sliders + low/average/high projection ---

const bucketSliders = document.querySelectorAll(".bucket-slider");
const rateInputs = document.querySelectorAll(".rate-input");
const strategyYearsInput = document.getElementById("strategyYears");
const saveStrategyBtn = document.getElementById("saveStrategyBtn");
const fmtMoney = (n) => "€" + Math.round(n).toLocaleString();

function currentBucketAmounts() {
  const buckets = {};
  bucketSliders.forEach((el) => {
    buckets[el.dataset.bucket] = parseFloat(el.value) || 0;
  });
  return buckets;
}

function currentBucketRates() {
  const rates = {};
  rateInputs.forEach((el) => {
    const bucket = el.dataset.bucket;
    const scenario = el.dataset.scenario;
    rates[bucket] = rates[bucket] || {};
    rates[bucket][scenario] = (parseFloat(el.value) || 0) / 100;
  });
  return rates;
}

function renderStrategyPie() {
  const buckets = currentBucketAmounts();
  const canvas = document.getElementById("strategyPieChart");
  if (!canvas) return;

  const labels = [];
  const data = [];
  bucketSliders.forEach((el) => {
    const bucketKey = el.dataset.bucket;
    const labelSpan = document.querySelector(`#bucketValue-${bucketKey}`).previousElementSibling;
    labels.push(labelSpan ? labelSpan.textContent : bucketKey);
    data.push(buckets[bucketKey]);
  });

  if (strategyPieChart) strategyPieChart.destroy();
  strategyPieChart = new Chart(canvas, {
    type: "doughnut",
    data: {
      labels,
      datasets: [{ data, backgroundColor: ["#0d6efd", "#20c997", "#fd7e14"] }],
    },
    options: {
      responsive: true,
      plugins: { legend: { position: "bottom" } },
    },
  });
}

function updateStrategyTable() {
  const buckets = currentBucketAmounts();
  const total = Object.values(buckets).reduce((a, b) => a + b, 0) || 1;

  bucketSliders.forEach((el) => {
    const bucketKey = el.dataset.bucket;
    const amount = buckets[bucketKey];
    const amountCell = document.getElementById(`strategyTableAmount-${bucketKey}`);
    const pctCell = document.getElementById(`strategyTablePct-${bucketKey}`);
    if (amountCell) amountCell.textContent = fmtMoney(amount);
    if (pctCell) pctCell.textContent = Math.round((amount / total) * 100) + "%";
  });

  const totalCell = document.getElementById("strategyTableTotal");
  if (totalCell) totalCell.textContent = fmtMoney(total);
}

function renderStrategyChart(result) {
  const years = result.timeline.map((p) => p.year);
  const low = result.timeline.map((p) => p.low);
  const average = result.timeline.map((p) => p.average);
  const high = result.timeline.map((p) => p.high);
  const contributed = result.timeline.map((p) => p.contributed);

  const ctx = document.getElementById("strategyChart");
  if (strategyChart) strategyChart.destroy();
  strategyChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: years,
      datasets: [
        { label: "High", data: high, borderColor: "#20c997", backgroundColor: "transparent", tension: 0.2 },
        { label: "Average", data: average, borderColor: "#0d6efd", backgroundColor: "transparent", tension: 0.2 },
        { label: "Low", data: low, borderColor: "#fd7e14", backgroundColor: "transparent", tension: 0.2 },
        {
          label: "Contributed",
          data: contributed,
          borderColor: "#adb5bd",
          backgroundColor: "transparent",
          borderDash: [4, 4],
          pointRadius: 0,
        },
      ],
    },
    options: {
      responsive: true,
      interaction: { mode: "index", intersect: false },
      plugins: { legend: { position: "bottom" } },
      scales: {
        x: { title: { display: true, text: "Years" } },
        y: { beginAtZero: true, ticks: { callback: (v) => fmtMoney(v) } },
      },
    },
  });

  document.getElementById("strategyFinalLow").textContent = fmtMoney(result.final.low);
  document.getElementById("strategyFinalAvg").textContent = fmtMoney(result.final.average);
  document.getElementById("strategyFinalHigh").textContent = fmtMoney(result.final.high);
}

async function updateStrategyProjection() {
  const buckets = currentBucketAmounts();
  const rates = currentBucketRates();
  const years = parseInt(strategyYearsInput.value, 10) || 20;

  const total = Object.values(buckets).reduce((a, b) => a + b, 0);
  document.getElementById("bucketTotal").textContent = fmtMoney(total);
  document.getElementById("strategyYearsValue").textContent = years;

  const response = await fetch("/api/strategy_projection", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ buckets, rates, years }),
  });

  if (!response.ok) return;
  const result = await response.json();
  renderStrategyChart(result);
}

async function saveStrategyDefaults() {
  const buckets = currentBucketAmounts();
  const rates = currentBucketRates();
  const status = document.getElementById("saveStrategyStatus");

  saveStrategyBtn.disabled = true;
  const response = await fetch("/api/strategy", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ buckets, rates }),
  });
  saveStrategyBtn.disabled = false;

  if (!response.ok) {
    status.textContent = "Save failed";
    status.classList.replace("text-success", "text-danger");
    return;
  }

  status.classList.remove("text-danger");
  status.classList.add("text-success");
  status.textContent = "Saved";
  setTimeout(() => (status.textContent = ""), 2000);
}

function debounce(fn, delay) {
  let timer = null;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}

const debouncedUpdate = debounce(updateStrategyProjection, 150);

if (bucketSliders.length) {
  bucketSliders.forEach((el) => {
    el.addEventListener("input", () => {
      document.getElementById(`bucketValue-${el.dataset.bucket}`).textContent = fmtMoney(parseFloat(el.value));
      renderStrategyPie();
      updateStrategyTable();
      debouncedUpdate();
    });
  });

  rateInputs.forEach((el) => {
    el.addEventListener("input", debouncedUpdate);
  });

  if (saveStrategyBtn) {
    saveStrategyBtn.addEventListener("click", saveStrategyDefaults);
  }

  strategyYearsInput.addEventListener("input", debouncedUpdate);

  renderStrategyPie();
  updateStrategyTable();
  updateStrategyProjection();
}
