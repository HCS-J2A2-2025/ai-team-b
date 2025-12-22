import { useState, useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";
import AppHeader from "../components/AppHeader";
import "../css/Result.css";
// Use the same search styling as the Search page
import "../css/Search.css";

export default function Result() {
  const location = useLocation();

  const initialCompanyName = (location.state?.companyName ?? "").trim();
  const [searchQuery, setSearchQuery] = useState(initialCompanyName);
  const [fixedCompanyName, setFixedCompanyName] = useState(initialCompanyName);
  const [expandedItem, setExpandedItem] = useState(null);

  const [report, setReport] = useState("");
  const [records, setRecords] = useState([]);
  const [showLoading, setShowLoading] = useState(false);

  const [isLoading, setIsLoading] = useState(false);
  const [suggestions, setSuggestions] = useState([]);
  const [isSuggestLoading, setIsSuggestLoading] = useState(false);
  const [apiError, setApiError] = useState(null);

  const [detailsMap, setDetailsMap] = useState({});
  const [detailLoadingMap, setDetailLoadingMap] = useState({});
  const [detailErrorMap, setDetailErrorMap] = useState({});

  const handleLogout = () => {
    console.log("ログアウトしました");
  };

  const didInitialFetchRef = useRef(false);

  // =========================
  // ✅ Search.jsx と同じサジェスト制御一式
  // =========================
  const suggestAbortRef = useRef(null);
  const suppressSuggestRef = useRef(false); // 候補確定クリック直後の“復活”抑止
  const suggestSeqRef = useRef(0); // 古いレスポンス破棄
  const composingRef = useRef(false);
  const pendingSelectRef = useRef(null);
  const inputRef = useRef(null);

  // 検索バー+サジェスト領域参照（外側クリックで閉じる）
  const searchWrapperRef = useRef(null);

  const applyPendingSelect = () => {
    if (pendingSelectRef.current) {
      handleSuggestionClick(pendingSelectRef.current);
      pendingSelectRef.current = null;
    }
  };

  // 外側クリックでサジェストを閉じる（Search と同じ）
  useEffect(() => {
    const onDocMouseDown = (e) => {
      const root = searchWrapperRef.current;
      if (!root) return;

      if (!root.contains(e.target)) {
        setSuggestions([]);
        setIsSuggestLoading(false);

        // 進行中の通信も止める
        if (suggestAbortRef.current) suggestAbortRef.current.abort();
        suggestSeqRef.current++;
      }
    };

    document.addEventListener("mousedown", onDocMouseDown);
    return () => document.removeEventListener("mousedown", onDocMouseDown);
  }, []);

  // 会社名の比較用（空白差・大小差を吸収）
  const normalizeCompanyName = (s) =>
    String(s ?? "")
      .trim()
      .replace(/\s+/g, " ")
      .toLowerCase();

  const getReportId = (record, idx) =>
    record?.id ||
    record?.report_id ||
    record?.reportId ||
    record?.id ||
    record?.レポートID ||
    String(idx);

  const getFallbackQuestionsFromRecord = (record) => {
    if (!record) return [];
    if (Array.isArray(record.questions) && record.questions.length > 0) {
      return record.questions;
    }
    if (
      typeof record.question_content === "string" &&
      record.question_content.trim()
    ) {
      return [record.question_content.trim()];
    }
    return [];
  };

  const getFallbackMemoFromRecord = (record) =>
    typeof record?.memo === "string" && record.memo.trim() ? record.memo : "";

  const fetchCompanyReport = async (companyName) => {
    const name = (companyName || "").trim();
    if (!name) return;

    setIsLoading(true);
    setApiError(null);
    setExpandedItem(null);

    setDetailsMap({});
    setDetailLoadingMap({});
    setDetailErrorMap({});

    let timerId = null;
    timerId = setTimeout(() => setShowLoading(true), 200);

    try {
      // ① POST：request_id だけ返る
      const res = await fetch("http://localhost:8000/api/company/report", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      });

      const postData = await res.json().catch(() => ({}));

      if (!res.ok || postData?.error) {
        setApiError(
          postData?.error || `取得に失敗しました（HTTP ${res.status}）`
        );
        return;
      }

      const requestId = postData?.request_id;
      if (!requestId) {
        setReport("");
        setRecords([]);
        setApiError("request_id が返ってきませんでした（サーバー実装を確認）");
        return;
      }

      // ② POST：本体データを取得
      const res2 = await fetch("http://localhost:8000/api/company/report/result", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ request_id: requestId }),
      });

      const data = await res2.json().catch(() => ({}));

      if (!res2.ok || data?.error) {
        setApiError(data?.error || `取得に失敗しました（HTTP ${res2.status}）`);
        return;
      }

      setFixedCompanyName(name);

      const reportText = data?.report ?? data?.result?.report ?? "";
      setReport(reportText);

      const list =
        (Array.isArray(data?.records) && data.records) ||
        (Array.isArray(data?.interviews) && data.interviews) ||
        (Array.isArray(data?.result?.records) && data.result.records) ||
        (Array.isArray(data?.result?.interviews) && data.result.interviews) ||
        [];

      setRecords(list.slice(-10));
    } catch (e) {
      setApiError("API 接続エラー：サーバーに接続できませんでした");
    } finally {
      clearTimeout(timerId);
      setShowLoading(false);
      setIsLoading(false);
    }
  };

  const fetchInterviewDetail = async (idx, record) => {
    const reportId = getReportId(record, idx);
    if (detailsMap[reportId]) return;

    setDetailLoadingMap((p) => ({ ...p, [reportId]: true }));
    setDetailErrorMap((p) => ({ ...p, [reportId]: "" }));
    try {
      const res = await fetch("http://localhost:8000/api/interview/detail", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ report_id: reportId }),
      });

      const data = await res.json();

      if (!res.ok || data?.error) {
        setDetailErrorMap((p) => ({
          ...p,
          [reportId]: data?.error || `HTTP ${res.status}`,
        }));
      } else {
        setDetailsMap((p) => ({ ...p, [reportId]: data }));
      }
    } catch (e) {
      setDetailErrorMap((p) => ({
        ...p,
        [reportId]: "詳細の取得に失敗しました",
      }));
    } finally {
      setDetailLoadingMap((p) => ({ ...p, [reportId]: false }));
    }
  };

  const toggleExpand = async (idx) => {
    const willOpen = expandedItem !== idx;
    setExpandedItem(willOpen ? idx : null);

    if (!willOpen) return;
    const record = records[idx];
    if (!record) return;

    // await fetchInterviewDetail(idx, record);
  };

  // =========================
  // ✅ Search.jsx と同じサジェスト取得関数
  // =========================
  const requestSuggest = async (keyword) => {
    if (suppressSuggestRef.current) return;

    const key = (keyword ?? "").trim();

    // 空なら候補消す＆通信止める
    if (!key) {
      if (suggestAbortRef.current) suggestAbortRef.current.abort();
      setSuggestions([]);
      setIsSuggestLoading(false);
      return;
    }

    // この入力に対するリクエスト番号
    const seq = ++suggestSeqRef.current;

    // 前回を中断
    if (suggestAbortRef.current) suggestAbortRef.current.abort();
    const controller = new AbortController();
    suggestAbortRef.current = controller;

    setIsSuggestLoading(true);

    try {
      const res = await fetch("http://localhost:8000/company_suggest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ keyword }),
        signal: controller.signal,
      });

      const data = await res.json().catch(() => ({}));

      // 古い返りは捨てる
      if (seq !== suggestSeqRef.current) return;
      if (suppressSuggestRef.current) return;

      if (!res.ok) {
        setSuggestions([]);
        return;
      }

      const list = data?.candidates || data?.suggestions || [];
      setSuggestions(Array.isArray(list) ? list : []);
    } catch (err) {
      if (err?.name !== "AbortError") console.error("候補取得エラー:", err);
      if (seq !== suggestSeqRef.current) return;
      setSuggestions([]);
    } finally {
      if (seq === suggestSeqRef.current) setIsSuggestLoading(false);
    }
  };

  const handleSearchInputChange = (e) => {
    const value = e.target.value;
    setSearchQuery(value);

    // 入力が変わった兆し → サジェスト更新
    requestSuggest(value);
  };

  // クリックなど「入力する兆し」でサジェストを再表示（Search と同じ）
  const handleInputClick = () => {
    requestSuggest(searchQuery);
  };

  const handleSuggestionClick = (name) => {
    suppressSuggestRef.current = true;

    // 進行中のサジェスト通信を止める
    if (suggestAbortRef.current) suggestAbortRef.current.abort();
    suggestSeqRef.current++; // 遅れて返ったやつは捨てる

    setSearchQuery(name);
    setSuggestions([]);
    setApiError(null);
    setIsSuggestLoading(false);

    // 次にユーザーが入力したら再開
    setTimeout(() => {
      suppressSuggestRef.current = false;
    }, 0);
  };

  // 比較専用：表示/送信には使わない
  const normalizeForCompare = (s) =>
    String(s ?? "")
      .replace(/\u3000/g, " ")
      .trim()
      .replace(/\s+/g, " ")
      .toLowerCase();

  const handleSearchSubmit = async (e) => {
    e.preventDefault();
    if (isLoading) return;

    const raw = searchQuery;
    const nextKey = normalizeForCompare(raw);
    const prevKey = normalizeForCompare(fixedCompanyName);

    if (nextKey && prevKey && nextKey === prevKey) {
      setSuggestions([]);
      setApiError("同一条件のため、AI再生成は行っていません");
      return;
    }

    setApiError(null);
    setSuggestions([]);
    await fetchCompanyReport(raw);
  };

  useEffect(() => {
    if (didInitialFetchRef.current) return;
    didInitialFetchRef.current = true;
    if (initialCompanyName && initialCompanyName !== "会社名が入力されていません") {
      fetchCompanyReport(initialCompanyName);
    }
    // eslint-disable-next-line
  }, []);

  return (
    <div className="result-container">
      <AppHeader title="JobNavi Inteligens" onLogout={handleLogout} />

      <main className="result-main-content">
        {showLoading && (
          <div className="result-overlay">
            <div className="result-loading-box">
              <div>AI要約レポートを取得中です…</div>
              <div className="loading-spinner"></div>
            </div>
          </div>
        )}

        <section className="result-search-area">
          <form className="search-area" onSubmit={handleSearchSubmit}>
            <div className="search-row">
              {/* ✅ Search と同じ：search-wrapper を ref で囲う */}
              <div className="search-wrapper" ref={searchWrapperRef}>
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
                    placeholder="会社名を記入　例）ダイアモンドヘッド"
                    value={searchQuery}
                    onChange={handleSearchInputChange}
                    onClick={handleInputClick}
                    onCompositionStart={() => {
                      composingRef.current = true;
                    }}
                    onCompositionEnd={() => {
                      composingRef.current = false;
                      applyPendingSelect();
                    }}
                    onBlur={() => {
                      composingRef.current = false;
                      applyPendingSelect();
                    }}
                  />
                </div>

                {suggestions.length > 0 && (
                  <div className="suggest-panel">
                    {isSuggestLoading && (
                      <div className="suggest-loading">検索中...</div>
                    )}

                    {suggestions.map((name) => (
                      <div
                        key={name}
                        className="suggest-row"
                        onMouseDown={(e) => {
                          // ✅ Search と同じ：外側クリック判定/blurより先に確定させる
                          e.preventDefault();
                          e.stopPropagation();

                          if (composingRef.current) {
                            pendingSelectRef.current = name;
                            requestAnimationFrame(() => inputRef.current?.blur());
                            return;
                          }

                          handleSuggestionClick(name);
                        }}
                      >
                        <span className="suggest-icon">⏺</span>
                        <span className="suggest-text">{name}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <button type="submit" className="search-button" disabled={isLoading}>
                {isLoading ? "検索中..." : "検　索"}
              </button>
            </div>
          </form>

          {apiError && <div className="result-api-error">{apiError}</div>}
        </section>

        <div className="result-content-grid">
          <div className="result-card">
            <div className="result-ai-report-header">
              <span className="result-ai-icon">✨</span>
              <h3 className="result-ai-report-title">
                AI要約レポート（{fixedCompanyName ? fixedCompanyName.trim() : "未選択"}）
              </h3>
            </div>

            <p className="result-report-body">
              {report || "レポートがまだ取得されていません。検索してください。"}
            </p>
          </div>

          <div className="result-card">
            <h3 className="result-exam-records-title">
              受験記録一覧({records.length}件)
            </h3>

            <div className="result-records-list">
              {records.length === 0 && !isLoading && (
                <p className="result-muted">
                  この企業の面接記録はまだ登録されていません。
                </p>
              )}

              {records.map((record, idx) => {
                const isOpen = expandedItem === idx;

                const reportId = getReportId(record, idx);
                const detail = detailsMap[reportId];
                const isDetailLoading = !!detailLoadingMap[reportId];
                const detailErr = detailErrorMap[reportId];

                const displayQuestions =
                  Array.isArray(detail?.questions) && detail.questions.length > 0
                    ? detail.questions
                    : getFallbackQuestionsFromRecord(record);

                const displayMemo =
                  typeof detail?.memo === "string" && detail.memo.trim()
                    ? detail.memo
                    : getFallbackMemoFromRecord(record);

                const displayQuestionContent =
                  typeof detail?.question_content === "string" &&
                  detail.question_content.trim()
                    ? detail.question_content
                    : "";

                return (
                  <div key={`${reportId}-${idx}`} className="result-record-item">
                    <button
                      type="button"
                      onClick={() => toggleExpand(idx)}
                      className="result-record-button"
                    >
                      <div className="result-record-info">
                        <span className="result-record-title">{record.title}</span>
                        <span className="result-record-meta">{record.year}</span>
                        <span className="result-record-meta">{record.term}</span>
                        <span className="result-record-status">{record.status}</span>
                        <span className="result-record-meta">{record.type}</span>
                      </div>

                      <svg
                        className={
                          isOpen
                            ? "result-chevron-icon result-chevron-rotated"
                            : "result-chevron-icon"
                        }
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                        aria-hidden="true"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M19 9l-7 7-7-7"
                        />
                      </svg>
                    </button>

                    {isOpen && (
                      <div className="result-record-detail">
                        {isDetailLoading && (
                          <p className="result-muted">詳細を読み込み中...</p>
                        )}
                        {detailErr && <p className="result-error">{detailErr}</p>}

                        <div className="result-detail-section-title">質問内容</div>

                        {Array.isArray(displayQuestions) &&
                        displayQuestions.length > 0 ? (
                          displayQuestions.map((q, i) => (
                            <div key={i} className="result-q-line">
                              {`Q${i + 1}. ${q}`}
                            </div>
                          ))
                        ) : displayQuestionContent ? (
                          <div className="result-q-line">{displayQuestionContent}</div>
                        ) : (
                          <div className="result-muted">質問が抽出できませんでした</div>
                        )}

                        <div className="result-detail-section-title">メモ・感想</div>
                        <div className="result-memo-box">
                          {displayMemo || "メモがありません"}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
