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
  const [showSubmitting, setShowSubmitting] = useState(false);
  const loadingTimerRef = useRef(null);
  const fetchAbortRef = useRef(null);

  // API通信中表示（任意）
  const [isFetching, setIsFetching] = useState(false);

  // エラーは「検索確定時」だけ出す
  const [apiError, setApiError] = useState(null);

  const inputRef = useRef(null);
  const navigate = useNavigate();

  const lastSearchedNoRef = useRef(null);
  const useAiRef = useRef(false);
  const [lastSearchHadData, setLastSearchHadData] = useState(false);
  const [lastSearchNotFound, setLastSearchNotFound] = useState(false);

  // 画面に表示しているデータの学籍番号（=最後に成功した番号）
  const [displayNo, setDisplayNo] = useState("");
  // 検索を1回でもしたかのフラグ
  const [hasSearched, setHasSearched] = useState(false);

  const handleLogout = () => {
    localStorage.removeItem("jobnaviUser");
    navigate("/loginpage");
  };

  useEffect(() => {
    const stored = localStorage.getItem("jobnaviUser");
    if (!stored) {
      navigate("/loginpage");
      return;
    }
    try {
      const user = JSON.parse(stored);
      const role = (user.role || "").toLowerCase();
      if (role !== "teacher" && role !== "admin") {
        navigate("/loginpage"); // または "/search" に戻すでもOK
        return;
      }
      setRole(role);
    } catch {
      navigate("/loginpage");
    }
  }, [navigate]);

  // Search.jsx と同じ「遅延表示ローディング」
  useEffect(() => {
    // isFetching が true になったら「遅延で」表示
    if (isFetching) {
      if (loadingTimerRef.current) clearTimeout(loadingTimerRef.current);
      loadingTimerRef.current = setTimeout(() => setShowSubmitting(true), 200);
      return;
    }

    // isFetching が false になったら必ず非表示
    if (loadingTimerRef.current) {
      clearTimeout(loadingTimerRef.current);
      loadingTimerRef.current = null;
    }
    setShowSubmitting(false);
  }, [isFetching]);

  // 学生分析
  useEffect(() => {
    const fetchOne = async () => {
      if (!searchedNo) {
        setStudentData(null);
        return;
      }

      // 前回の学生分析リクエストをキャンセル
      if (fetchAbortRef.current) {
        fetchAbortRef.current.abort();
      }
      const controller = new AbortController();
      fetchAbortRef.current = controller;

      setApiError(null);
      setIsFetching(true);

      try {
        const res = await fetch("/api/student/analysis", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            student_id: searchedNo,
            use_ai: useAiRef.current,
          }),
          signal: controller.signal,
        });

        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = await res.json();

        const one =
          json?.data && Object.keys(json.data).length > 0 ? json.data : null;

        if (!one) {
          // 該当なし：前回データは維持。エラーだけ出す
          setApiError("該当する学生データがありません");
          setLastSearchHadData(false);
          setLastSearchNotFound(true);
          return;
        }

        // 成功：ここで初めて studentData を更新
        setApiError(null);
        setStudentData(one);
        setDisplayNo(searchedNo);
        setLastSearchHadData(true);
        setLastSearchNotFound(false);
      } catch (err) {
        if (err?.name !== "AbortError") {
          console.error("学生データ取得エラー:", err);
          // 失敗時も「前回の結果を保持」したいなら setStudentData(null) はしない
          setApiError("学生データ取得に失敗しました");
          setLastSearchHadData(false);
          setLastSearchNotFound(false);
        }
      } finally {
        setIsFetching(false);
        useAiRef.current = false;
      }
    };

    fetchOne();

    // searchedNo が変わる/アンマウントでキャンセル
    return () => {
      if (fetchAbortRef.current) fetchAbortRef.current.abort();
    };
  }, [searchedNo]);

  // ===== サジェスト制御（ここが修正ポイント） =====
  const suggestAbortRef = useRef(null);
  const suggestAreaRef = useRef(null);
  const latestSuggestKeyRef = useRef("");
  const suppressSuggestRef = useRef(false);

  // サジェスト取得（古いレスポンスで復活しないようガード）
  const fetchSuggest = async (keyword) => {
    const key = (keyword || "").trim();
    if (!key) {
      setSuggestions([]);
      return;
    }

    // 選択直後など「出してはいけない」タイミング
    if (suppressSuggestRef.current) return;

    // 前回リクエストキャンセル
    if (suggestAbortRef.current) {
      suggestAbortRef.current.abort();
    }
    const controller = new AbortController();
    suggestAbortRef.current = controller;

    latestSuggestKeyRef.current = key;
    setIsSuggestLoading(true);

    try {
      const res = await fetch("/api/student/suggest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ keyword: key }),
        signal: controller.signal,
      });

      if (!res.ok) {
        setSuggestions([]);
        return;
      }

      const json = await res.json();

      // 入力値が変わっていたら（古いレスポンス）反映しない
      if (latestSuggestKeyRef.current !== key) return;
      // 選択直後などに抑止が立っていたら反映しない
      if (suppressSuggestRef.current) return;

      setSuggestions(json.candidates || []);
    } catch (err) {
      if (err?.name !== "AbortError") {
        console.error("学籍番号サジェスト取得エラー:", err);
      }
      setSuggestions([]);
    } finally {
      setIsSuggestLoading(false);
    }
  };

  // 入力変更：サジェストを出すだけ（検索確定はしない）
  const handleInputChange = async (e) => {
    const value = e.target.value;
    setInputNo(value);
    setApiError(null);

    // 入力が始まったら抑止解除（＝またサジェストを出せる）
    suppressSuggestRef.current = false;

    await fetchSuggest(value);
  };

  // 入力欄クリック/フォーカスで、消えていても再度サジェストを出す
  const handleInputFocusOrClick = () => {
    suppressSuggestRef.current = false;
    fetchSuggest(inputNo);
  };

  // サジェストクリック：入力欄に入れるだけ（検索は確定しない）
  const handleSuggestionClick = (sid) => {
    // クリック後に通信の結果で「復活」しないよう抑止
    suppressSuggestRef.current = true;

    // 通信中ならキャンセル
    if (suggestAbortRef.current) suggestAbortRef.current.abort();
    latestSuggestKeyRef.current = "";

    setInputNo(sid);
    setSuggestions([]);
    setApiError(null);
    requestAnimationFrame(() => inputRef.current?.focus());
  };

  // サジェスト以外をクリックしたら閉じる（外側クリック）
  useEffect(() => {
    const onDown = (e) => {
      if (!suggestAreaRef.current) return;
      if (suggestAreaRef.current.contains(e.target)) return;
      setSuggestions([]);
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, []);

  const handleSubmit = (e) => {
    e.preventDefault();
    const v = inputNo.trim();
    if (!v) return;

    setHasSearched(true);

    const isSameAsLast = lastSearchedNoRef.current === v;

    // 直前が「存在しない」で、同じ番号を再検索 → 通信もAIも回さない。エラーだけ再表示
    if (isSameAsLast && lastSearchNotFound) {
      setApiError("該当する学生データがありません");
      return;
    }

    // 直前と同じ学籍番号ならブロック
    if (isSameAsLast && lastSearchHadData) {
      setApiError("直前と同じ学籍番号のため、再検索は行われません");
      return;
    }

    // 検索ボタン押した瞬間から“検索中”にする
    setApiError(null);
    setIsFetching(true);
    setSuggestions([]);

    // 前回結果の判定をいったん未確定にする
    setLastSearchNotFound(false);
    setLastSearchHadData(false);

    // ここは要件次第。毎回AIを回すなら true 固定でOK
    useAiRef.current = true;

    setSearchedNo(v);
    lastSearchedNoRef.current = v;
  };

  return (
    <div className="app-root">
      <AppHeader title="学生受験分析レポート" onLogout={handleLogout} />

      <main className="app-main">
        {showSubmitting && (
          <div className="loading-backdrop">
            <div className="loading-box">
              <div className="loading-text">
                学生分析レポートを生成しています…
              </div>
              <div className="loading-spinner" />
            </div>
          </div>
        )}

        <section>
          <h1 className="main-title">学生受験分析レポート</h1>

          <form className="search-area" onSubmit={handleSubmit}>
            <div className="search-wrapper" ref={suggestAreaRef}>
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
                  onClick={handleInputFocusOrClick}
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

          {apiError && hasSearched && (
            <div className="student-error">
              {apiError}
              {searchedNo && (
                <div className="student-error-sub">入力：{searchedNo}</div>
              )}
            </div>
          )}
        </section>

        <div className="student-page-root">
          {studentData && <h3>📌 表示中の学籍番号：{displayNo}</h3>}

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
