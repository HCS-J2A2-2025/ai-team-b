// src/api.js

export async function fetchCompanyReport(name) {
  try {
    const res = await fetch(`http://localhost:8000/company/${encodeURIComponent(name)}`);

    if (!res.ok) {
      throw new Error("API 接続エラー: " + res.status);
    }

    const data = await res.json();
    return data;

  } catch (err) {
    console.error("API Error:", err);
    return { error: true, message: err.message };
  }
}
