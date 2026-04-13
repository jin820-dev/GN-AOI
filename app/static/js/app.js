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
registerServiceWorker();
