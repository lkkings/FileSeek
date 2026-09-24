import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./styles/tokens.css";
import "./styles/base.css";
import "./styles/utilities.css";
import "./features/library/library.css";
import "./features/search/search.css";
import "./features/settings/settings.css";
import "./features/tasks/tasks.css";
import { initTheme } from "./styles/theme";

// Before the first render, so the palette is in effect for the initial paint rather than
// applied a frame later as a visible flash.
initTheme();

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
