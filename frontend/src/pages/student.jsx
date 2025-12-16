// student.jsx
import { useEffect, useRef, useState } from "react";
import AppHeader from "../components/AppHeader";
import { useNavigate } from "react-router-dom";

import "../css/Search.css";
import "../css/student.css";

function StudentPage() {
  const [role, setRole] = useState(null);

  const [studentData, setStudentData] = useState(null);
  const [searchedNo, setSearchedNo] = useState(""); // 検索確定の学籍番号

  // 入力中（検索確定ではない）
  const [inputNo, setInputNo] = useState("");

  const [suggestions, setSuggestions] = useState([]);
  const [isSuggestLoading, setIsSuggestLoading] = useState(false);

  // API通信中表示（任意）
  const [isFetching, setIsFetching] = useState(false);

  // エラーは「検索確定時」だけ出す
  const [apiError, setApiError] = useState(null);

  const inputRef = useRef(null);
  const navigate = useNavigate();

  const handleLogout = () => {
    localStorage.removeItem("jobnaviUser");
    navigate("/loginpage");
  };

  // ロール確認（teacher/adminのみ）※今のままだと role を使ってないので警告が気になるなら setRole を消してもOK
  useEffect(() => {
    const stored = localStorage.getItem("jobnaviUser");
    if (!stored) {
      navigate("/loginpage");
      return;
    }
    try {
      const user = JSON.parse(stored);
      if (user.role !== "teacher" && user.role !== "admin") {
        navigate("/loginpage");
        return;
      }
      setRole(user.role);
    } catch {
      navigate("/loginpage");
    }
  }, [navigate]);

useEffect(() => {
  const fetchOne = async () => {
    if (!searchedNo) {
      setStudentData(null);
      return;
    }

    setIsFetching(true);
    try {
      const res = await fetch("http://127.0.0.1:8000/api/student/analysis", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ student_id: searchedNo, use_ai: false }),
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();

      // ✅ APIは「dataが1人分オブジェクト」なので、そのまま使う
      const one = json?.data && Object.keys(json.data).length > 0 ? json.data : null;

      setStudentData(one);
    } catch (err) {
      console.error("学生データ取得エラー:", err);
      setStudentData(null);
    } finally {
      setIsFetching(false);
    }
  };

  fetchOne();
}, [searchedNo]);


  const suggestAbortRef = useRef(null);

  // 入力変更：サジェストを出すだけ（検索確定はしない）
const handleInputChange = async (e) => {
  const value = e.target.value;
  setInputNo(value);
  setApiError(null);

  if (!value.trim()) {
    setSuggestions([]);
    return;
  }

  // 直前の通信があればキャンセル（連打でズレるのを防ぐ）
  if (suggestAbortRef.current) {
    suggestAbortRef.current.abort();
  }
  const controller = new AbortController();
  suggestAbortRef.current = controller;

  setIsSuggestLoading(true);
  try {
    const res = await fetch("http://127.0.0.1:8000/api/student/suggest", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ keyword: value }),
      signal: controller.signal,
    });

    if (!res.ok) {
      setSuggestions([]);
      return;
    }

    const json = await res.json();
    setSuggestions(json.candidates || []);
  } catch (err) {
    // AbortError は無視してOK
    if (err?.name !== "AbortError") {
      console.error("学籍番号サジェスト取得エラー:", err);
    }
    setSuggestions([]);
  } finally {
    setIsSuggestLoading(false);
  }
};

  // サジェストクリック：入力欄に入れるだけ（検索は確定しない）
  const handleSuggestionClick = (sid) => {
    setInputNo(sid);
    setSuggestions([]);
    setApiError(null);
    requestAnimationFrame(() => inputRef.current?.focus());
  };

  // 検索ボタン：ここで初めて検索確定 → API取得が走る
  const handleSubmit = (e) => {
    e.preventDefault();
    const v = inputNo.trim();
    if (!v) return;

    setApiError(null);
    setSuggestions([]);
    setSearchedNo(v);
  };

  return (
    <div className="app-root">
      <AppHeader title="学生受験分析レポート" onLogout={handleLogout} />

      <main className="app-main">
        <section>
          <h1 className="main-title">学生受験分析レポート</h1>

          <form className="search-area" onSubmit={handleSubmit}>
            <div className="search-wrapper">
              <div
                className={`search-input-wrapper ${
                  suggestions.length > 0 ? "has-suggest" : ""
                }`}
              >
                <span className="search-icon">🔍</span>
                <input
                  ref={inputRef}
                  type="text"
                  className="search-input"
                  placeholder="学籍番号を記入　例）S20240001"
                  value={inputNo}
                  onChange={handleInputChange}
                />
              </div>

              {suggestions.length > 0 && (
                <div className="suggest-panel">
                  {isSuggestLoading && (
                    <div className="suggest-loading">検索中...</div>
                  )}
                  {suggestions.map((sid) => (
                    <div
                      key={sid}
                      className="suggest-row"
                      onClick={() => handleSuggestionClick(sid)}
                    >
                      <span className="suggest-icon">⏺</span>
                      <span className="suggest-text">{sid}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <button type="submit" className="search-button">
              検　索
            </button>
          </form>

          {apiError && <div className="student-error">{apiError}</div>}
        </section>

        <div className="student-page-root">
          {searchedNo && <h3>📌 学籍番号：{searchedNo}</h3>}

          {/* API取得中 */}
          {isFetching && (
            <p className="student-notfound">読み込み中...</p>
          )}

          {/* 検索確定後、取得できなかった */}
          {searchedNo && !isFetching && !studentData && !apiError && (
            <p className="student-notfound">該当する学生データがありません</p>
          )}

          {studentData && (
            <>
              <div className="section-card">
                <h3>🏢 受験企業一覧</h3>
                <ul>
                  {(studentData["企業一覧"] ?? []).map((c, idx) => (
                    <li key={idx}>{c}</li>
                  ))}
                </ul>
              </div>

              <div className="section-card">
                <h3>🗓 面接日程</h3>
                <ul>
                  {(studentData["面接日程"] ?? []).map((d, idx) => (
                    <li key={idx}>
                      <strong>{d["企業名"]}</strong>：
                      {d.start_datetime
                        ? new Date(d.start_datetime).toLocaleString()
                        : "日時不明"}
                      ～{" "}
                      {d.終了日時
                        ? new Date(d.終了日時).toLocaleString()
                        : "日時不明"}
                      （結果：{d.result_status ?? "不明"}）
                    </li>
                  ))}
                </ul>
              </div>

              <div className="section-card">
                <h3>📊 基本統計</h3>
                <p>受験回数：{studentData["受験回数"] ?? 0}</p>
                <p>受験期間：{studentData["受験期間"] ?? "不明"}</p>
                <p>合格率：{studentData["合格率"] ?? "不明"}</p>
              </div>

              <div className="section-card">
                <h3>🎤 面接形式の傾向</h3>
                {studentData["形式傾向"] ? (
                  <ul>
                    {Object.entries(studentData["形式傾向"]).map(([key, val]) => (
                      <li key={key}>
                        {key}：{val}回
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p>データなし</p>
                )}
              </div>

              <div className="section-card">
                <h3>👔 面接官の傾向</h3>
                {studentData["面接官傾向"] ? (
                  <ul>
                    {Object.entries(studentData["面接官傾向"]).map(([key, val]) => (
                      <li key={key}>
                        {key}：{val}回
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p>データなし</p>
                )}
              </div>

              <div className="section-card">
                <h3>🤖 AI分析レポート</h3>
                <div className="ai-report">
                  {(studentData["AI分析レポート"] ?? "")
                    .split("\n")
                    .map((line, idx) => (
                      <p key={idx}>{line}</p>
                    ))}
                </div>
              </div>
            </>
          )}
        </div>
      </main>
    </div>
  );
}

export default StudentPage;
