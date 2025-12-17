// src/index.js
import React from "react";
import ReactDOM from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import App from "./App";
import "./index.css"; // ✅ これが超重要（body margin:0 を確実に効かせる）

// ✅ 直打ち対策：URLに何が入っても / に戻す
if (window.location.pathname !== "/") {
  window.history.replaceState({}, "", "/");
}

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <MemoryRouter initialEntries={["/"]}>
      <App />
    </MemoryRouter>
  </React.StrictMode>
);
