(function () {
  const THEME_STORAGE_KEY = "gnaoi-theme";
  const root = document.documentElement;

  function getPreferredTheme() {
    if (window.matchMedia("(prefers-color-scheme: dark)").matches) {
      return "dark";
    }
    return "light";
  }

  function applyTheme(theme) {
    if (theme === "light" || theme === "dark") {
      root.dataset.theme = theme;
      return;
    }

    root.dataset.theme = getPreferredTheme();
  }

  const savedTheme = window.localStorage.getItem(THEME_STORAGE_KEY);
  applyTheme(savedTheme);
  window.GNAOITheme = { applyTheme, storageKey: THEME_STORAGE_KEY };
})();
