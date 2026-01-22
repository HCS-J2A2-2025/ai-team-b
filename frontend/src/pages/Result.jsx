import { useState, useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";
import AppHeader from "../components/AppHeader";
import "../css/Result.css";
import "../css/Search.css";

export default function Result() {
  const location = useLocation();
  const companyName = (location.state?.companyName ?? "").trim();
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
  const suppressSuggestRef = useRef(false);
  const suggestSeqRef = useRef(0);
  const suggestTimerRef = useRef(null);
  const lastSuggestKeyRef = useRef("");
  const suggestCacheRef = useRef(new Map());
  const composingRef = useRef(false);
  const pendingSelectRef = useRef(null);
  const inputRef = useRef(null);
  const searchWrapperRef = useRef(null);

  const applyPendingSelect = () => {
    if (pendingSelectRef.current) {
      handleSuggestionClick(pendingSelectRef.current);
      pendingSelectRef.current = null;
    }
  };

  useEffect(() => {
    const onDocMouseDown = (e) => {
      const root = searchWrapperRef.current;
      if (!root) return;

      if (!root.contains(e.target)) {
        setSuggestions([]);
        setIsSuggestLoading(false);
        if (suggestAbortRef.current) suggestAbortRef.current.abort();
        if (suggestTimerRef.current) clearTimeout(suggestTimerRef.current);
        suggestSeqRef.current++;
      }
    };

    document.addEventListener("mousedown", onDocMouseDown);
    return () => {
      document.removeEventListener("mousedown", onDocMouseDown);
      if (suggestAbortRef.current) suggestAbortRef.current.abort();
      if (suggestTimerRef.current) clearTimeout(suggestTimerRef.current);
    };
  }, []);

  // オーバーレイ（AIレポート取得中）表示中はサジェストを非表示にする
  // showLoading が true の間は候補リストがモーダルより前に出ないように
  useEffect(() => {
    if (showLoading) {
      setSuggestions([]);
    }
  }, [showLoading]);

  const getReportId = (record, idx) =>
    record?.public_id ||
    record?.id ||
    record?.report_id ||
    record?.reportId ||
    record?.レポートID ||
    String(idx);

  const getFallbackQuestionsFromRecord = (record) => {
    if (!record) return [];
    if (Array.isArray(record.questions) && record.questions.length > 0) {
      return record.questions;
    }
    if (typeof record.question_content === "string" && record.question_content.trim()) {
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
    // =====================================================
    // ✅ 1) まず JSONキャッシュ（POST）を見に行く
    // =====================================================


    // =====================================================
    // ✅ 2) キャッシュが無ければAI生成（POST→request_id→result）
    // =====================================================
    const res = await fetch("/api/company/report", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });

    const postData = await res.json().catch(() => ({}));
    if (!res.ok || postData?.error) {
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

    const res2 = await fetch("/api/company/report/result", {
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

    setRecords(Array.isArray(list) ? list.slice(-10) : []);
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
    if (!reportId) return;
    if (detailsMap[reportId]) return;

    setDetailLoadingMap((p) => ({ ...p, [reportId]: true }));
    setDetailErrorMap((p) => ({ ...p, [reportId]: "" }));

    try {
      const res = await fetch("/api/interview/detail", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ report_id: reportId }),
      });

      const data = await res.json().catch(() => ({}));
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

    // ✅ 詳細APIを使うならここをON
    // await fetchInterviewDetail(idx, record);
  };

  const requestSuggest = async (keyword) => {
    if (suppressSuggestRef.current) return;

    const key = (keyword ?? "").trim();
    if (!key) {
      if (suggestAbortRef.current) suggestAbortRef.current.abort();
      if (suggestTimerRef.current) clearTimeout(suggestTimerRef.current);
      setSuggestions([]);
      setIsSuggestLoading(false);
      return;
    }

    const cached = suggestCacheRef.current.get(key);
    if (Array.isArray(cached)) {
      setSuggestions(cached);
      setIsSuggestLoading(false);
      lastSuggestKeyRef.current = key;
      return;
    }

    if (suggestTimerRef.current) clearTimeout(suggestTimerRef.current);
    if (suggestAbortRef.current) suggestAbortRef.current.abort();
    setIsSuggestLoading(true);

    suggestTimerRef.current = setTimeout(async () => {
      const seq = ++suggestSeqRef.current;

      if (suggestAbortRef.current) suggestAbortRef.current.abort();
      const controller = new AbortController();
      suggestAbortRef.current = controller;

      try {
        const res = await fetch("/api/company/suggest", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ keyword: key }),
          signal: controller.signal,
        });

        const data = await res.json().catch(() => ({}));
        if (seq !== suggestSeqRef.current) return;
        if (suppressSuggestRef.current) return;

        if (!res.ok) {
          setSuggestions([]);
          return;
        }

        const list = data?.candidates || data?.suggestions || [];
        const out = Array.isArray(list) ? list : [];
        suggestCacheRef.current.set(key, out);
        lastSuggestKeyRef.current = key;
        setSuggestions(out);
      } catch (err) {
        if (err?.name !== "AbortError") console.error("候補取得エラー:", err);
        if (seq !== suggestSeqRef.current) return;
        setSuggestions([]);
      } finally {
        if (seq === suggestSeqRef.current) setIsSuggestLoading(false);
      }
    }, 250);
  };

  // 「㈱」を入力欄のカーソル位置に挿入（重複は避ける）
  const handleInsertKabu = () => {
    const kabu = "㈱";
    const el = inputRef.current;
    const v = searchQuery ?? "";

    if (v.includes(kabu)) {
      requestAnimationFrame(() => el?.focus());
      return;
    }

    const start = typeof el?.selectionStart === "number" ? el.selectionStart : v.length;
    const end = typeof el?.selectionEnd === "number" ? el.selectionEnd : v.length;

    const next = v.slice(0, start) + kabu + v.slice(end);
    setSearchQuery(next);
    setApiError(null);
    requestSuggest(next);

    requestAnimationFrame(() => {
      el?.focus();
      try {
        el?.setSelectionRange(start + kabu.length, start + kabu.length);
      } catch {}
    });
  };

  const handleSearchInputChange = (e) => {
    const value = e.target.value;
    setSearchQuery(value);
    requestSuggest(value);
  };

  const handleInputClick = () => {
    requestSuggest(searchQuery);
  };

  const handleSuggestionClick = (name) => {
    suppressSuggestRef.current = true;

    if (suggestAbortRef.current) suggestAbortRef.current.abort();
    suggestSeqRef.current++;

    setSearchQuery(name);
    setSuggestions([]);
    setApiError(null);
    setIsSuggestLoading(false);

    setTimeout(() => {
      suppressSuggestRef.current = false;
    }, 0);
  };

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
    const canonical = (suggestions && suggestions.length > 0) ? suggestions[0] : raw;
    await fetchCompanyReport(canonical);

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
              <div className="search-wrapper" ref={searchWrapperRef}>
                <div
                  className={`search-input-wrapper ${
                    suggestions.length > 0 ? "has-suggest" : ""
                  }`}
                >
                  <span className="search-icon">🔍</span>
                  <button
                    type="button"
                    className="kabu-inline-btn"
                    title="㈱を入力"
                    aria-label="㈱を入力"
                    onMouseDown={(e) => e.preventDefault()}
                    onClick={handleInsertKabu}
                  >
                    ㈱
                  </button>
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
                <p className="result-muted">この企業の面接記録はまだ登録されていません。</p>
              )}

              {records.map((record, idx) => {
                const isOpen = expandedItem === idx;

                const reportId = getReportId(record, idx);
                const detail = reportId ? detailsMap[reportId] : null;
                const isDetailLoading = reportId ? !!detailLoadingMap[reportId] : false;
                const detailErr = reportId ? detailErrorMap[reportId] : "";

                const displayQuestions =
                  Array.isArray(detail?.questions) && detail.questions.length > 0
                    ? detail.questions
                    : getFallbackQuestionsFromRecord(record);

                const displayMemo =
                  typeof detail?.memo === "string" && detail.memo.trim()
                    ? detail.memo
                    : getFallbackMemoFromRecord(record);

                const displayQuestionContent =
                  typeof detail?.question_content === "string" && detail.question_content.trim()
                    ? detail.question_content
                    : "";

                // ✅ 適性検査判定（バックで kind を入れてるならそれが最優先）
                const isAptitude =
                  record?.kind === "aptitude" ||
                  record?.id === "適正検査" ||
                  record?.title === "適正検査";

                return (
                  <div key={`${reportId}-${idx}`} className="result-record-item">
                    <button
                      type="button"
                      onClick={() => toggleExpand(idx)}
                      className="result-record-button"
                    >
                      <div className="result-record-info">
                        <span className="result-record-title">{record?.title ?? ""}</span>
                        <span className="result-record-meta">{record?.year ?? ""}</span>
                        <span className="result-record-meta">{record?.term ?? ""}</span>
                        <span className="result-record-status">{record?.status ?? ""}</span>
                        <span className="result-record-meta">{record?.type ?? ""}</span>
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
                        {isDetailLoading && <p className="result-muted">詳細を読み込み中...</p>}
                        {detailErr && <p className="result-error">{detailErr}</p>}

                        <div className="result-detail-section-title">
                          {isAptitude ? "試験内容" : "質問内容"}
                        </div>

                        {Array.isArray(displayQuestions) && displayQuestions.length > 0 ? (
                          displayQuestions.map((q, i) => (
                            <div key={i} className="result-q-line">
                              {isAptitude ? `・${q}` : `Q${i + 1}. ${q}`}
                            </div>
                          ))
                        ) : displayQuestionContent ? (
                          <div className="result-q-line">{displayQuestionContent}</div>
                        ) : (
                          <div className="result-muted">
                            {isAptitude ? "試験内容が抽出できませんでした" : "質問が抽出できませんでした"}
                          </div>
                        )}

                        <div className="result-detail-section-title">メモ・感想</div>
                        <div className="result-memo-box">{displayMemo || "メモがありません"}</div>
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
