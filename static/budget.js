// --- Month picker ---

const monthPicker = document.getElementById("monthPicker");
if (monthPicker) {
  monthPicker.addEventListener("change", () => {
    window.location.href = `/budget?month=${monthPicker.value}`;
  });
}

// --- Save this month's category totals ---

const saveActualsBtn = document.getElementById("saveActualsBtn");
const saveActualsStatus = document.getElementById("saveActualsStatus");
const budgetActualsError = document.getElementById("budgetActualsError");

if (saveActualsBtn) {
  saveActualsBtn.addEventListener("click", async () => {
    budgetActualsError.classList.add("d-none");
    saveActualsStatus.textContent = "";

    const values = {};
    document.querySelectorAll(".budget-actual-input").forEach((el) => {
      values[el.dataset.key] = parseFloat(el.value) || 0;
    });

    saveActualsBtn.disabled = true;
    const response = await fetch("/api/budget_actuals", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ month: monthPicker.value, values }),
    });
    saveActualsBtn.disabled = false;

    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      budgetActualsError.textContent = err.error || "Failed to save totals";
      budgetActualsError.classList.remove("d-none");
      return;
    }

    window.location.reload();
  });
}

// --- Budget settings (category monthly targets) ---

const budgetSettingsModalEl = document.getElementById("budgetSettingsModal");
const budgetSettingsModal = budgetSettingsModalEl ? new bootstrap.Modal(budgetSettingsModalEl) : null;
const budgetSettingsBtn = document.getElementById("budgetSettingsBtn");
const budgetSettingsError = document.getElementById("budgetSettingsError");

if (budgetSettingsBtn) {
  budgetSettingsBtn.addEventListener("click", () => {
    budgetSettingsError.classList.add("d-none");
    budgetSettingsModal.show();
  });
}

const budgetSettingsSaveBtn = document.getElementById("budgetSettingsSaveBtn");
if (budgetSettingsSaveBtn) {
  budgetSettingsSaveBtn.addEventListener("click", async () => {
    const payload = {};
    document.querySelectorAll(".budget-target-input").forEach((el) => {
      payload[el.dataset.key] = { monthly_target: parseFloat(el.value) || 0 };
    });

    const response = await fetch("/api/budget_categories", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      budgetSettingsError.textContent = "Failed to save settings";
      budgetSettingsError.classList.remove("d-none");
      return;
    }

    window.location.reload();
  });
}
