// src/index.js
import React from "react";
import ReactDOM from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import App from "./App";
import "./index.css";

const KEY = "mem_path";

// URLは常に http://localhost:3000/ に固定（絶対条件）
if (window.location.pathname !== "/") {
  window.history.replaceState({}, "", "/");
}

// 更新しても同じ画面に戻る：前回の画面を MemoryRouter の初期値にする
const initialPath = sessionStorage.getItem(KEY) || "/";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <MemoryRouter initialEntries={[initialPath]}>
      <App />
    </MemoryRouter>
  </React.StrictMode>
);
