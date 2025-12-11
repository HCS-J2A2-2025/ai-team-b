    import React, { useState } from "react";
    import { useNavigate } from "react-router-dom";

    export default function CompanySearch() {
    const [name, setName] = useState("");
    const [result, setResult] = useState("");
    const navigate = useNavigate();

    const handleSearch = async () => {
    const trimmed = name.trim();
    if (!trimmed) return;

    try {
        const res = await fetch("http://localhost:8000/company", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({ name: trimmed }),
        });

        if (!res.ok) {
        setResult("API エラー（HTTP " + res.status + "）");
        return;
        }

        const data = await res.json();

        // バックエンドの返却形式に完全対応
        if (data.error) {
        setResult(data.error);
        } else if (data.report) {
        setResult(data.report);
        } else {
        // 想定外形式
        setResult("予期しないレスポンス: " + JSON.stringify(data));
        }
    } catch (e) {
        console.error(e);
        setResult("API 接続エラー");
    }
    };

    return (
    <div style={{ padding: "40px" }}>
        <h1>企業レポートAI</h1>

        <button
        style={{ marginBottom: "20px", padding: "10px" }}
        onClick={() => navigate("/loginpage")}
        >
        ログインページへ
        </button>

        <br />

        <input
        type="text"
        placeholder="企業名を入力"
        value={name}
        onChange={(e) => setName(e.target.value)}
        style={{ padding: "10px", width: "300px" }}
        />

        <button
        onClick={handleSearch}
        style={{ marginLeft: "10px", padding: "10px" }}
        >
        検索
        </button>

        <pre
        style={{
            marginTop: "20px",
            background: "#eee",
            padding: "20px",
            whiteSpace: "pre-wrap",
        }}
        >
        {result}
        </pre>
    </div>
    );
    }
