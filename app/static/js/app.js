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

function setupFuelEconomyChart() {
  const canvas = document.querySelector("[data-fuel-economy-chart]");
  if (!canvas || !window.Chart) {
    return;
  }
  const chartPanel = canvas.closest(".panel") || document;

  let chartData;
  try {
    chartData = JSON.parse(canvas.dataset.fuelEconomyChart || "{}");
  } catch (error) {
    return;
  }

  const labels = Array.isArray(chartData.labels) ? chartData.labels : [];
  const values = Array.isArray(chartData.values) ? chartData.values : [];
  const averageValues = Array.isArray(chartData.average_values) ? chartData.average_values : [];
  if (!labels.length || !values.length) {
    return;
  }

  const styles = getComputedStyle(document.documentElement);
  const textColor = styles.getPropertyValue("--text").trim() || "#143043";
  const softTextColor = styles.getPropertyValue("--text-soft").trim() || "#5c7385";
  const borderColor = styles.getPropertyValue("--border").trim() || "rgba(20, 48, 67, 0.1)";
  const accentColor = styles.getPropertyValue("--accent-strong").trim() || "#1b7faf";
  const accentFill = styles.getPropertyValue("--accent-soft").trim() || "rgba(47, 159, 209, 0.14)";
  const averageColor = "#f59e0b";
  const xTickLimit = window.innerWidth < 600 ? 4 : 8;

  function parseLocalDate(label) {
    const parts = String(label).split("-").map((part) => Number.parseInt(part, 10));
    if (parts.length !== 3 || parts.some((part) => Number.isNaN(part))) {
      return null;
    }
    return new Date(parts[0], parts[1] - 1, parts[2]);
  }

  function filterChartData(range) {
    if (range === "all") {
      return { labels, values, averageValues };
    }

    const days = Number.parseInt(range, 10);
    const latestDate = parseLocalDate(labels[labels.length - 1]);
    if (Number.isNaN(days) || !latestDate) {
      return { labels, values, averageValues };
    }

    const startDate = new Date(latestDate);
    startDate.setDate(startDate.getDate() - days);

    const filtered = labels.reduce(
      (accumulator, label, index) => {
        const currentDate = parseLocalDate(label);
        if (currentDate && currentDate >= startDate && currentDate <= latestDate) {
          accumulator.labels.push(label);
          accumulator.values.push(values[index]);
          accumulator.averageValues.push(averageValues[index]);
        }
        return accumulator;
      },
      { labels: [], values: [], averageValues: [] }
    );

    return filtered.labels.length ? filtered : { labels, values, averageValues };
  }

  const chart = new window.Chart(canvas, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "燃費",
          data: values,
          borderColor: accentColor,
          backgroundColor: accentFill,
          borderWidth: 2,
          pointRadius: values.length > 40 ? 0 : 2.5,
          pointHoverRadius: 4,
          tension: 0.25,
          fill: true,
        },
        {
          label: "平均燃費",
          data: averageValues,
          borderColor: averageColor,
          backgroundColor: "transparent",
          borderWidth: 2,
          pointRadius: values.length > 40 ? 0 : 2,
          pointHoverRadius: 4,
          tension: 0.25,
          fill: false,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        intersect: false,
        mode: "index",
      },
      plugins: {
        legend: {
          display: true,
          labels: {
            color: textColor,
            boxWidth: 12,
            boxHeight: 12,
          },
        },
        tooltip: {
          callbacks: {
            label: (context) => `${context.dataset.label}: ${context.parsed.y.toFixed(2)} km/L`,
          },
        },
      },
      scales: {
        x: {
          grid: {
            display: false,
          },
          ticks: {
            color: softTextColor,
            autoSkip: true,
            maxTicksLimit: xTickLimit,
            maxRotation: 0,
            minRotation: 0,
          },
        },
        y: {
          beginAtZero: false,
          title: {
            display: true,
            text: "km/L",
            color: softTextColor,
          },
          grid: {
            color: borderColor,
          },
          ticks: {
            color: textColor,
            callback: (value) => `${value}`,
          },
        },
      },
    },
  });

  chartPanel.querySelectorAll("[data-range]").forEach((button) => {
    button.addEventListener("click", () => {
      const filtered = filterChartData(button.dataset.range || "all");
      chart.data.labels = filtered.labels;
      chart.data.datasets[0].data = filtered.values;
      chart.data.datasets[1].data = filtered.averageValues;
      chart.update();

      chartPanel.querySelectorAll("[data-range]").forEach((rangeButton) => {
        rangeButton.classList.toggle("is-active", rangeButton === button);
      });
    });
  });
}

function setupFuelPriceChart() {
  const canvas = document.querySelector("[data-fuel-price-chart]");
  if (!canvas || !window.Chart) {
    return;
  }
  const chartPanel = canvas.closest(".panel") || document;

  let chartData;
  try {
    chartData = JSON.parse(canvas.dataset.fuelPriceChart || "{}");
  } catch (error) {
    return;
  }

  const labels = Array.isArray(chartData.labels) ? chartData.labels : [];
  const values = Array.isArray(chartData.values) ? chartData.values : [];
  if (!labels.length || !values.length) {
    return;
  }

  const styles = getComputedStyle(document.documentElement);
  const textColor = styles.getPropertyValue("--text").trim() || "#143043";
  const softTextColor = styles.getPropertyValue("--text-soft").trim() || "#5c7385";
  const borderColor = styles.getPropertyValue("--border").trim() || "rgba(20, 48, 67, 0.1)";
  const accentColor = "#16a34a";
  const accentFill = "rgba(22, 163, 74, 0.12)";
  const xTickLimit = window.innerWidth < 600 ? 4 : 8;

  function parseLocalDate(label) {
    const parts = String(label).split("-").map((part) => Number.parseInt(part, 10));
    if (parts.length !== 3 || parts.some((part) => Number.isNaN(part))) {
      return null;
    }
    return new Date(parts[0], parts[1] - 1, parts[2]);
  }

  function filterChartData(range) {
    if (range === "all") {
      return { labels, values };
    }

    const days = Number.parseInt(range, 10);
    const latestDate = parseLocalDate(labels[labels.length - 1]);
    if (Number.isNaN(days) || !latestDate) {
      return { labels, values };
    }

    const startDate = new Date(latestDate);
    startDate.setDate(startDate.getDate() - days);

    const filtered = labels.reduce(
      (accumulator, label, index) => {
        const currentDate = parseLocalDate(label);
        if (currentDate && currentDate >= startDate && currentDate <= latestDate) {
          accumulator.labels.push(label);
          accumulator.values.push(values[index]);
        }
        return accumulator;
      },
      { labels: [], values: [] }
    );

    return filtered.labels.length ? filtered : { labels, values };
  }

  const chart = new window.Chart(canvas, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "燃料単価",
          data: values,
          borderColor: accentColor,
          backgroundColor: accentFill,
          borderWidth: 2,
          pointRadius: values.length > 40 ? 0 : 2.5,
          pointHoverRadius: 4,
          tension: 0.25,
          fill: true,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        intersect: false,
        mode: "index",
      },
      plugins: {
        legend: {
          display: true,
          labels: {
            color: textColor,
            boxWidth: 12,
            boxHeight: 12,
          },
        },
        tooltip: {
          callbacks: {
            label: (context) => `${context.dataset.label}: ${context.parsed.y.toFixed(1)} 円/L`,
          },
        },
      },
      scales: {
        x: {
          grid: {
            display: false,
          },
          ticks: {
            color: softTextColor,
            autoSkip: true,
            maxTicksLimit: xTickLimit,
            maxRotation: 0,
            minRotation: 0,
          },
        },
        y: {
          beginAtZero: false,
          title: {
            display: true,
            text: "円/L",
            color: softTextColor,
          },
          grid: {
            color: borderColor,
          },
          ticks: {
            color: textColor,
            callback: (value) => `${value}`,
          },
        },
      },
    },
  });

  chartPanel.querySelectorAll("[data-range]").forEach((button) => {
    button.addEventListener("click", () => {
      const filtered = filterChartData(button.dataset.range || "all");
      chart.data.labels = filtered.labels;
      chart.data.datasets[0].data = filtered.values;
      chart.update();

      chartPanel.querySelectorAll("[data-range]").forEach((rangeButton) => {
        rangeButton.classList.toggle("is-active", rangeButton === button);
      });
    });
  });
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
setupFuelEconomyChart();
setupFuelPriceChart();
registerServiceWorker();
