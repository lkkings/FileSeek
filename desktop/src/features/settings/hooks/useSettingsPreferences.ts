import { useContext } from "react";

import { SettingsPreferencesContext } from "./settingsPreferencesContext";

export function useSettingsPreferences() {
  const context = useContext(SettingsPreferencesContext);
  if (!context) {
    throw new Error("useSettingsPreferences must be used within SettingsPreferencesProvider");
  }
  return context;
}
