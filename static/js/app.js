function updateRowNumbers() {
  const rows = document.querySelectorAll("#particulars-body tr");
  rows.forEach((row, index) => {
    const number = row.querySelector(".row-number");
    if (number) number.textContent = String(index + 1);
  });
}

function addParticularRow() {
  const body = document.getElementById("particulars-body");
  if (!body) return;
  const row = document.createElement("tr");
  const columns = [
    ["chassis_number", "text"], ["model", "text"], ["invoice_date", "date"],
    ["shipment_number", "text"], ["invoice_number", "text"],
  ];
  row.innerHTML = '<td class="row-number"></td>' + columns.map(([name, type]) =>
    `<td><input type="${type}" name="particular_${name}[]"></td>`
  ).join("") + '<td><button class="icon-button remove-row" type="button" aria-label="Remove row">×</button></td>';
  body.appendChild(row);
  updateRowNumbers();
  row.querySelector("input").focus();
}

function updateTotals() {
  const inputs = document.querySelectorAll(".charge-input");
  if (!inputs.length) return;
  const cents = Array.from(inputs).reduce((sum, input) => {
    const value = Number(input.value || 0);
    return sum + (Number.isFinite(value) && value > 0 ? Math.round(value * 100) : 0);
  }, 0);
  const subtotal = cents / 100;
  const taxRate = Number(document.body.dataset.taxRate || 0);
  const tax = Math.round(subtotal * taxRate) / 100;
  const format = (value) => `₹${value.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  document.getElementById("subtotal-preview").value = format(subtotal);
  document.getElementById("tax-preview").value = format(tax);
  document.getElementById("grand-total-preview").value = format(subtotal + tax);
}

document.addEventListener("click", (event) => {
  if (event.target.closest("#add-particular")) addParticularRow();
  const remove = event.target.closest(".remove-row");
  if (remove) {
    const body = document.getElementById("particulars-body");
    const rows = body.querySelectorAll("tr");
    if (rows.length > 1) remove.closest("tr").remove();
    else remove.closest("tr").querySelectorAll("input").forEach((input) => { input.value = ""; });
    updateRowNumbers();
  }
});

document.addEventListener("input", (event) => {
  if (event.target.matches(".charge-input")) updateTotals();
  if (event.target.matches("[data-party-input]")) {
    const input = event.target;
    const options = document.getElementById(input.getAttribute("list"));
    const option = Array.from(options?.options || []).find((item) => item.value === input.value);
    if (!option) return;
    const details = JSON.parse(option.dataset.party || "{}");
    const prefix = input.dataset.partyInput;
    Object.entries(details).forEach(([field, value]) => {
      const target = document.querySelector(`[name="${prefix}_${field}"]`);
      if (target) target.value = value;
    });
  }
});

document.addEventListener("submit", (event) => {
  if (event.target.id !== "receipt-form") return;
  const button = document.getElementById("save-receipt");
  if (button.disabled) {
    event.preventDefault();
    return;
  }
  button.disabled = true;
  button.textContent = "Saving…";
});

document.addEventListener("DOMContentLoaded", () => {
  updateRowNumbers();
  updateTotals();
});

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/service-worker.js").catch((error) => {
      console.error("Service worker registration failed:", error);
    });
  });
}
