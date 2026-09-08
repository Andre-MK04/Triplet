(function () {
  try {
    var preference = localStorage.getItem("triplet-theme") || "dark";
    var theme =
      preference === "system"
        ? window.matchMedia("(prefers-color-scheme: dark)").matches
          ? "dark"
          : "light"
        : preference;
    document.documentElement.dataset.theme = theme;
  } catch (_error) {
    document.documentElement.dataset.theme = "dark";
  }
})();
