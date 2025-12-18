import { useState, useEffect,useRef } from "react";
import { useLocation } from "react-router-dom";
import AppHeader from "../components/AppHeader";
import "../css/Result.css";
// Use the same search styling as the Search page
import "../css/Search.css";

export default function Result() {
  const location = useLocation();

  const initialCompanyName =
    location.state?.companyName || "会社名が入力されていません";

  const [fixedCompanyName, setFixedCompanyName] = useState(initialCompanyName);
  const [expandedItem, setExpandedItem] = useState(null);
  const [searchQuery, setSearchQuery] = useState(initialCompanyName);

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
// 会社名の比較用（空白差・大小差を吸収）
  const normalizeCompanyName = (s) =>
    String(s ?? "")
      .trim()
      .replace(/\s+/g, " ")   // 連続空白を1個に
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
    // 失敗しても既存表示は維持、エラーだけ出す
    setApiError(postData?.error || `取得に失敗しました（HTTP ${res.status}）`);
    return;
  }

  const requestId = postData?.request_id;
  if (!requestId) {
    setReport("");
    setRecords([]);
    setApiError("request_id が返ってきませんでした（サーバー実装を確認）");
    return;
  }

  // ② POST：本体データを取得（GET → POST に変更）
  const res2 = await fetch("http://localhost:8000/api/company/report/result", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ request_id: requestId }),
  });

  const data = await res2.json().catch(() => ({}));

  if (!res2.ok || data?.error) {
    // 失敗しても既存表示は維持
    setApiError(data?.error || `取得に失敗しました（HTTP ${res2.status}）`);
    return;
  } 
  // 成功した時だけ画面に反映
  setFixedCompanyName(name);

const reportText =
  data?.report ??
  data?.result?.report ??
  "";

setReport(reportText);

// どの形でも拾う
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

    //await fetchInterviewDetail(idx, record);
  };

  const handleSearchInputChange = async (e) => {
    const value = e.target.value;
    setSearchQuery(value);

    if (!value.trim()) {
      setSuggestions([]);
      return;
    }

    setIsSuggestLoading(true);
    try {
      const res = await fetch("http://localhost:8000/company_suggest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ q: value, keyword: value }),
      });

      if (!res.ok) {
        setSuggestions([]);
        return;
      }

      const data = await res.json();
      const list = data?.candidates || data?.suggestions || [];
      setSuggestions(Array.isArray(list) ? list : []);
    } catch {
      setSuggestions([]);
    } finally {
      setIsSuggestLoading(false);
    }
  };

  const handleSuggestionClick = (name) => {
    setSearchQuery(name);
    setSuggestions([]);
  };
// 比較専用：表示/送信には使わない
const normalizeForCompare = (s) =>
  String(s ?? "")
    .replace(/\u3000/g, " ")   // 全角スペース→半角
    .trim()
    .replace(/\s+/g, " ")      // 連続スペースを1つに
    .toLowerCase();            // 大小差を吸収（比較だけ）

const handleSearchSubmit = async (e) => {
  e.preventDefault();
  if (isLoading) return;

  // 送信用は “生の入力” を維持（AI要約の中身を変えない）
  const raw = searchQuery;

  // 判定だけ正規化
  const nextKey = normalizeForCompare(raw);
  const prevKey = normalizeForCompare(fixedCompanyName);

  if (nextKey && prevKey && nextKey === prevKey) {
    setSuggestions([]);
    setApiError("同一条件のため、AI再生成は行っていません");
    return;
  }

  setApiError(null);
  setSuggestions([]);
  await fetchCompanyReport(raw); // ←ここは raw のまま
};


  useEffect(() => {
    if (didInitialFetchRef.current) return; // 2回目は無視
    didInitialFetchRef.current = true;
    if (initialCompanyName !== "会社名が入力されていません") {
      fetchCompanyReport(initialCompanyName);
    }
    // eslint-disable-next-line
  }, []);

  // We no longer compute result‑specific class names for the search elements.
  // The search bar and suggestion list now reuse the same classes from Search.css
  // to ensure a consistent look across pages.

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
          {/* Use the same structure and classes as the Search page */}
          <form className="search-area" onSubmit={handleSearchSubmit}>
              <div className="search-row">

              {/* Input field and suggestions */}
              <div className="search-wrapper">
                <div
                  className={`search-input-wrapper ${
                    suggestions.length > 0 ? "has-suggest" : ""
                  }`}
                >
                  <span className="search-icon">🔍</span>
                  <input
                    type="text"
                    className="search-input"
                    placeholder="会社名を記入　例）ダイアモンドヘッド"
                    value={searchQuery}
                    onChange={handleSearchInputChange}
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
                        onClick={() => handleSuggestionClick(name)}
                      >
                        <span className="suggest-icon">⏺</span>
                        <span className="suggest-text">{name}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
              {/* Submit button */}
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
                AI要約レポート（{(fixedCompanyName || "").trim()}）
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

                        {Array.isArray(displayQuestions) && displayQuestions.length > 0 ? (
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
