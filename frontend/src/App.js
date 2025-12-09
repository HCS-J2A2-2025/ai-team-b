import React, { useState } from "react";
import { Routes, Route } from "react-router-dom";
import Loginpage from "./Loginpage.jsx";
import Search from "./Search.jsx";
import Result from "./Result.jsx";
export default function App() {
  const [name, setName] = useState("");
  const [result, setResult] = useState("");

  const handleSearch = async () => {
    if (!name) return;

    try {
      const res = await fetch(`http://localhost:8000/company/${name}`);
      const data = await res.json();

      if (data.error) {
        setResult("企業が見つかりません");
      } else {
        setResult(data.report);
      }
    } catch (error) {
      setResult("API 接続エラー");
    }
  };

  return (
  <div style={{ padding: "40px" }}>
    <h1>企業レポートAI</h1>

    <input
      type="text"
      placeholder="企業名を入力"
      value={name}
      onChange={(e) => setName(e.target.value)}
      style={{ padding: "10px", width: "300px" }}
    />
    <button onClick={handleSearch} style={{ marginLeft: "10px", padding: "10px" }}>
      検索
    </button>

    <pre style={{ marginTop: "20px", background: "#eee", padding: "20px", whiteSpace: "pre-wrap" }}>
      {result}
    </pre>
  </div>
  );
}
