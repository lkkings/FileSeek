export type Theme = "dark" | "light";

/**
 * Initializes the theme state before the first React render.
 * Avoids initial repaint flashes.
 */
export function initTheme(): void {
  const savedTheme = localStorage.getItem("theme") as Theme | null;
  const systemPrefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  const activeTheme: Theme = savedTheme || (systemPrefersDark ? "dark" : "light");
  
  document.documentElement.setAttribute("data-theme", activeTheme);
}

/**
 * Dynamically toggles active application theme.
 */
export function toggleTheme(): Theme {
  const current = document.documentElement.getAttribute("data-theme") as Theme;
  const nextTheme: Theme = current === "dark" ? "light" : "dark";
  
  document.documentElement.setAttribute("data-theme", nextTheme);
  localStorage.setItem("theme", nextTheme);
  return nextTheme;
}

/**
 * Gets currently active theme.
 */
export function getTheme(): Theme {
  return (document.documentElement.getAttribute("data-theme") as Theme) || "dark";
}
