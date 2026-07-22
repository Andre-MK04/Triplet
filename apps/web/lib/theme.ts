export type ThemePreference = "light" | "dark" | "system";

export const THEME_STORAGE_KEY = "triplet-theme";

/** Inline script run before hydration to set data-theme with no flash. */
export const THEME_INIT_SCRIPT = `(function(){try{var t=localStorage.getItem('${THEME_STORAGE_KEY}')||'dark';var m=t==='system'?(window.matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light'):t;document.documentElement.dataset.theme=m;}catch(e){document.documentElement.dataset.theme='dark';}})();`;

export function resolveTheme(pref: ThemePreference): "light" | "dark" {
  if (pref === "system") {
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  return pref;
}

export function applyTheme(pref: ThemePreference): void {
  document.documentElement.dataset.theme = resolveTheme(pref);
}

export function readThemePreference(): ThemePreference {
  if (typeof window === "undefined") return "dark";
  const stored = window.localStorage.getItem(THEME_STORAGE_KEY);
  return stored === "light" || stored === "dark" || stored === "system" ? stored : "dark";
}

export function storeThemePreference(pref: ThemePreference): void {
  window.localStorage.setItem(THEME_STORAGE_KEY, pref);
}
