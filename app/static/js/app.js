function setupThemeToggle() {
  const toggle = document.querySelector("[data-theme-toggle]");
  if (!toggle || !window.GNAOITheme) {
    return;
  }

  function syncLabel() {
    const isDark = document.documentElement.dataset.theme === "dark";
    toggle.setAttribute("aria-pressed", isDark ? "true" : "false");
    toggle.setAttribute("title", isDark ? "ライトテーマへ切替" : "ダークテーマへ切替");
  }

  syncLabel();

  toggle.addEventListener("click", () => {
    const current = document.documentElement.dataset.theme || "light";
    const next = current === "dark" ? "light" : "dark";
    window.localStorage.setItem(window.GNAOITheme.storageKey, next);
    window.GNAOITheme.applyTheme(next);
    syncLabel();
  });
}

function setupRecordEditForm() {
  const modal = document.querySelector("[data-record-edit-modal]");
  const form = document.querySelector("[data-record-modal-form]");
  const editButtons = Array.from(document.querySelectorAll("[data-record-edit]"));
  if (!modal || !form || !editButtons.length) {
    return;
  }

  function setField(name, value) {
    const field = form.elements[name];
    if (field) {
      field.value = value || "";
    }
  }

  function openModal(button) {
    setField("record_index", button.dataset.recordIndex);
    setField("row_id", button.dataset.rowId);
    setField("date", button.dataset.date);
    setField("time", button.dataset.time);
    setField("fuel_l", button.dataset.fuelL);
    setField("price_yen", button.dataset.priceYen);
    setField("trip_km", button.dataset.tripKm);
    setField("odd_km", button.dataset.oddKm);
    setField("full", button.dataset.full);
    setField("fuel_type", button.dataset.fuelType);
    setField("note", button.dataset.note);
    modal.hidden = false;
    modal.classList.add("is-open");
    document.body.classList.add("has-modal");
    const firstInput = form.querySelector("input:not([type='hidden']), select, textarea");
    if (firstInput) {
      firstInput.focus();
    }
  }

  function closeModal() {
    if (modal.hidden) {
      return;
    }
    form.reset();
    modal.classList.remove("is-open");
    modal.hidden = true;
    document.body.classList.remove("has-modal");
  }

  editButtons.forEach((button) => {
    button.addEventListener("click", () => openModal(button));
  });

  document.querySelectorAll("[data-record-edit-close]").forEach((button) => {
    button.addEventListener("click", closeModal);
  });

  modal.addEventListener("click", (event) => {
    if (event.target === modal) {
      closeModal();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeModal();
    }
  });

  if (modal.classList.contains("is-open")) {
    modal.hidden = false;
    document.body.classList.add("has-modal");
  }
}

function registerServiceWorker() {
  if (!("serviceWorker" in navigator)) {
    return;
  }

  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/static/pwa/sw.js").catch(() => {
      // Step 2 keeps PWA registration failure silent.
    });
  });
}

setupThemeToggle();
setupRecordEditForm();
registerServiceWorker();
